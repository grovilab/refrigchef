import base64
import json
import os
import re
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from openai import APIError, OpenAI
from supabase import create_client

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def get_client():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    if session.get("access_token") and session.get("refresh_token"):
        supabase.auth.set_session(session["access_token"], session["refresh_token"])
    return supabase


def ensure_profile(supabase, user_id, nickname=""):
    result = supabase.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
    if result and result.data:
        return result.data

    inserted = supabase.table("profiles").insert(
        {
            "id": user_id,
            "nickname": nickname,
            "allergies": [],
            "disliked_ingredients": [],
        }
    ).execute()
    return inserted.data[0]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("로그인이 필요합니다.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped

VISION_MODEL = "google/gemma-4-26b-a4b-it:free"
TEXT_MODEL = "openai/gpt-oss-20b:free"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
MIME_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
TIME_LIMIT_CHOICES = ["15", "30", "60", ""]

RECOGNITION_PROMPT = (
    "이 이미지에 보이는 식재료 이름을 한국어로 알려줘. "
    '다른 설명 없이 JSON 배열 형태로만 답해줘. 예: ["양파", "계란", "우유"]'
)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_ingredients(text):
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
        except json.JSONDecodeError:
            pass

    fallback = re.split(r"[,\n]", text)
    cleaned = [re.sub(r"^[\-\*\d\.\)\s]+", "", item).strip() for item in fallback]
    return [item for item in cleaned if item]


def _as_str_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def normalize_recipe(raw):
    if not isinstance(raw, dict):
        return None
    estimated = raw.get("estimated_minutes")
    try:
        estimated = int(estimated)
    except (TypeError, ValueError):
        estimated = None
    return {
        "name": str(raw.get("name") or "이름 없는 레시피").strip(),
        "have_ingredients": _as_str_list(raw.get("have_ingredients")),
        "missing_ingredients": _as_str_list(raw.get("missing_ingredients")),
        "steps": _as_str_list(raw.get("steps")),
        "estimated_minutes": estimated,
    }


def parse_recipes(text):
    text = text.strip()

    def _normalize_list(data):
        if not isinstance(data, list):
            return None
        recipes = [normalize_recipe(item) for item in data]
        recipes = [r for r in recipes if r]
        return recipes or None

    try:
        result = _normalize_list(json.loads(text))
        if result:
            return result
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            result = _normalize_list(json.loads(match.group(0)))
            if result:
                return result
        except json.JSONDecodeError:
            pass

    # 모델이 배열 중간에 깨진 텍스트를 섞어 보내 전체 파싱이 실패하는 경우,
    # 개별 레시피 객체 단위로라도 최대한 건져낸다.
    salvaged = []
    for obj_match in re.finditer(r"\{(?:[^{}]|\n)*?\}", text, re.DOTALL):
        try:
            obj = json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            continue
        recipe = normalize_recipe(obj)
        if recipe:
            salvaged.append(recipe)

    return salvaged


def build_recipe_prompt(ingredients, servings, time_limit, spicy, excluded=None):
    conditions = [f"{servings}인분"]
    if time_limit:
        conditions.append(f"조리시간 {time_limit}분 이내")
    if spicy:
        conditions.append("매운맛 선호")
    if excluded:
        conditions.append(f"다음 재료는 알레르기/비선호이므로 제외: {', '.join(excluded)}")

    return (
        "아래 재료로 만들 수 있는 요리 레시피를 2~3개 추천해줘.\n"
        f"보유 재료: {', '.join(ingredients)}\n"
        f"조건: {', '.join(conditions)}\n"
        "다른 설명 없이 다음 JSON 배열 형식으로만 답해줘:\n"
        "[\n"
        "  {\n"
        '    "name": "요리명",\n'
        '    "have_ingredients": ["보유 재료 중 사용되는 것"],\n'
        '    "missing_ingredients": ["추가로 필요한 재료"],\n'
        '    "steps": ["1단계 설명", "2단계 설명"],\n'
        '    "estimated_minutes": 20\n'
        "  }\n"
        "]"
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/recognize", methods=["POST"])
def recognize():
    file = request.files.get("image")

    if file is None or file.filename == "":
        flash("이미지를 선택해주세요.")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("PNG 또는 JPEG 이미지만 업로드할 수 있습니다.")
        return redirect(url_for("index"))

    ext = file.filename.rsplit(".", 1)[1].lower()
    image_bytes = file.read()
    data_uri = f"data:{MIME_TYPES[ext]};base64,{base64.b64encode(image_bytes).decode()}"

    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": RECOGNITION_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
        )
    except APIError as e:
        flash(f"이미지 인식 중 오류가 발생했습니다: {e}")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"알 수 없는 오류가 발생했습니다: {e}")
        return redirect(url_for("index"))

    raw_text = response.choices[0].message.content or ""
    ingredients = parse_ingredients(raw_text)

    if not ingredients:
        flash("재료를 인식하지 못했습니다. 아래에서 직접 입력해주세요.")

    return render_template("review.html", ingredients=ingredients, raw_text=raw_text)


@app.route("/confirm", methods=["POST"])
def confirm():
    ingredients = [item.strip() for item in request.form.getlist("ingredient") if item.strip()]

    if not ingredients:
        flash("최종 재료가 없습니다. 최소 1개 이상 선택하거나 추가해주세요.")
        return redirect(url_for("index"))

    session["ingredients"] = ingredients
    return render_template("options.html", ingredients=ingredients)


@app.route("/options")
def options():
    ingredients = session.get("ingredients")
    if not ingredients:
        flash("재료 정보가 없습니다. 처음부터 다시 시도해주세요.")
        return redirect(url_for("index"))
    return render_template("options.html", ingredients=ingredients)


@app.route("/recipes", methods=["GET", "POST"])
def recipes():
    if request.method == "GET":
        recipe_list = session.get("recipes")
        if not recipe_list:
            flash("아직 생성된 레시피가 없습니다. 재료를 먼저 확인해주세요.")
            return redirect(url_for("index"))
        return render_template("recipes.html", recipes=recipe_list, raw_text="")

    ingredients = session.get("ingredients")
    if not ingredients:
        flash("재료 정보가 없습니다. 처음부터 다시 시도해주세요.")
        return redirect(url_for("index"))

    servings = request.form.get("servings", "2").strip() or "2"
    if not servings.isdigit():
        servings = "2"
    time_limit = request.form.get("time_limit", "").strip()
    if time_limit not in TIME_LIMIT_CHOICES:
        time_limit = ""
    spicy = request.form.get("spicy") == "on"

    excluded = []
    if session.get("user_id"):
        supabase = get_client()
        profile = (
            supabase.table("profiles")
            .select("allergies, disliked_ingredients")
            .eq("id", session["user_id"])
            .maybe_single()
            .execute()
        )
        if profile and profile.data:
            excluded = (profile.data.get("allergies") or []) + (profile.data.get("disliked_ingredients") or [])

    prompt = build_recipe_prompt(ingredients, servings, time_limit, spicy, excluded)

    raw_text = ""
    recipe_list = []
    for _ in range(2):
        try:
            response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
        except APIError as e:
            flash(f"레시피 생성 중 오류가 발생했습니다: {e}")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"알 수 없는 오류가 발생했습니다: {e}")
            return redirect(url_for("index"))

        raw_text = response.choices[0].message.content or ""
        recipe_list = parse_recipes(raw_text)
        if recipe_list:
            break

    if not recipe_list:
        flash("레시피를 생성하지 못했습니다. 아래 원본 응답을 확인해주세요.")
        return render_template("recipes.html", recipes=[], raw_text=raw_text)

    session["recipes"] = recipe_list
    return render_template("recipes.html", recipes=recipe_list, raw_text=raw_text)


@app.route("/recipe/<int:index>")
def recipe_detail(index):
    recipe_list = session.get("recipes") or []
    if index < 0 or index >= len(recipe_list):
        flash("존재하지 않는 레시피입니다.")
        return redirect(url_for("index"))

    return render_template(
        "recipe_detail.html",
        recipe=recipe_list[index],
        index=index,
        total=len(recipe_list),
    )


@app.route("/recipe/<int:index>/save", methods=["POST"])
@login_required
def save_recipe(index):
    recipe_list = session.get("recipes") or []
    if index < 0 or index >= len(recipe_list):
        flash("존재하지 않는 레시피입니다.")
        return redirect(url_for("index"))

    recipe = recipe_list[index]
    supabase = get_client()
    supabase.table("saved_recipes").insert(
        {
            "user_id": session["user_id"],
            "name": recipe["name"],
            "have_ingredients": recipe["have_ingredients"],
            "missing_ingredients": recipe["missing_ingredients"],
            "steps": recipe["steps"],
            "estimated_minutes": recipe["estimated_minutes"],
        }
    ).execute()

    flash("레시피가 저장되었습니다.", "success")
    return redirect(url_for("my_recipes"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    nickname = request.form.get("nickname", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not nickname or not email or not password:
        flash("닉네임, 이메일, 비밀번호를 모두 입력해주세요.")
        return redirect(url_for("signup"))

    supabase = get_client()
    try:
        result = supabase.auth.sign_up({"email": email, "password": password})
    except Exception as e:
        flash(f"회원가입 중 오류가 발생했습니다: {e}")
        return redirect(url_for("signup"))

    if result.user is None:
        flash("회원가입에 실패했습니다.")
        return redirect(url_for("signup"))

    if result.session is None:
        flash("가입이 완료됐습니다. 이메일 인증 후 로그인해주세요.", "success")
        return redirect(url_for("login"))

    supabase.auth.set_session(result.session.access_token, result.session.refresh_token)
    ensure_profile(supabase, result.user.id, nickname=nickname)

    session["access_token"] = result.session.access_token
    session["refresh_token"] = result.session.refresh_token
    session["user_id"] = result.user.id
    session["email"] = result.user.email
    session["nickname"] = nickname
    flash("회원가입이 완료됐습니다.", "success")
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    supabase = get_client()
    try:
        result = supabase.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as e:
        flash(f"로그인에 실패했습니다: {e}")
        return redirect(url_for("login"))

    session["access_token"] = result.session.access_token
    session["refresh_token"] = result.session.refresh_token
    session["user_id"] = result.user.id
    session["email"] = result.user.email

    profile_data = ensure_profile(supabase, result.user.id, nickname=result.user.email.split("@")[0])
    session["nickname"] = profile_data.get("nickname", "")

    flash("로그인되었습니다.", "success")
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    flash("로그아웃되었습니다.", "success")
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    supabase = get_client()

    if request.method == "POST":
        nickname = request.form.get("nickname", "").strip()
        allergies = [i.strip() for i in request.form.get("allergies", "").split(",") if i.strip()]
        disliked = [i.strip() for i in request.form.get("disliked_ingredients", "").split(",") if i.strip()]

        supabase.table("profiles").update(
            {
                "nickname": nickname,
                "allergies": allergies,
                "disliked_ingredients": disliked,
            }
        ).eq("id", session["user_id"]).execute()

        session["nickname"] = nickname
        flash("프로필이 저장되었습니다.", "success")
        return redirect(url_for("profile"))

    profile_data = ensure_profile(supabase, session["user_id"], nickname=session.get("nickname", ""))
    return render_template("profile.html", profile=profile_data)


@app.route("/my-recipes")
@login_required
def my_recipes():
    supabase = get_client()
    result = (
        supabase.table("saved_recipes")
        .select("*")
        .eq("user_id", session["user_id"])
        .order("saved_at", desc=True)
        .execute()
    )
    return render_template("my_recipes.html", recipes=result.data)


@app.route("/my-recipes/<int:recipe_id>")
@login_required
def my_recipe_detail(recipe_id):
    supabase = get_client()
    result = (
        supabase.table("saved_recipes")
        .select("*")
        .eq("id", recipe_id)
        .eq("user_id", session["user_id"])
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        flash("존재하지 않는 레시피입니다.")
        return redirect(url_for("my_recipes"))

    return render_template("my_recipe_detail.html", recipe=result.data)


@app.route("/my-recipes/<int:recipe_id>/delete", methods=["POST"])
@login_required
def delete_recipe(recipe_id):
    supabase = get_client()
    supabase.table("saved_recipes").delete().eq("id", recipe_id).eq("user_id", session["user_id"]).execute()
    flash("레시피가 삭제되었습니다.", "success")
    return redirect(url_for("my_recipes"))


@app.errorhandler(413)
def too_large(e):
    flash("이미지 용량이 너무 큽니다 (5MB 이하만 가능).")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
