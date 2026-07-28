# 냉장고 재료 인식 & 레시피 추천 웹앱

냉장고 사진을 업로드하면 OpenRouter의 비전 모델로 식재료를 인식하고, 그 재료를 바탕으로 텍스트 모델이 레시피를 추천해주는 Flask 웹앱입니다. 회원가입/로그인 후에는 알레르기·비선호 재료를 등록해 추천에 반영하고, 마음에 든 레시피를 저장해 다시 볼 수 있습니다.

## 주요 기능 (Step 1~3)

- **Step 1 — 재료 인식**: 냉장고 사진 업로드 → `google/gemma-4-26b-a4b-it:free` 모델이 식재료 목록 추출 → 체크리스트에서 직접 추가/삭제 가능 ([PRD_step1.md](PRD_step1.md))
- **Step 2 — 레시피 추천**: 확정된 재료 + 인분수/조리시간/매운맛 옵션 → `openai/gpt-oss-20b:free` 모델이 레시피 2~3개 생성, 상세 조리법 확인 ([PRD_step2.md](PRD_step2.md))
- **Step 3 — 회원가입/저장**: Supabase Auth로 회원가입/로그인, 알레르기·비선호 재료를 프로필에 등록(레시피 추천 시 자동 제외), 마음에 든 레시피 저장 및 "내 레시피"에서 조회/삭제 ([PRD_step3.md](PRD_step3.md))

## 기술 스택

- Python, Flask (서버 렌더링 템플릿)
- OpenRouter API (OpenAI 호환) — 이미지 인식 + 레시피 생성
- Supabase (Auth + Postgres) — 회원 인증, 프로필, 저장된 레시피

## 시작하기

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

프로젝트 루트에 `.env` 파일을 만들고 아래 값을 채워주세요.

```
OPENROUTER_API_KEY=your_openrouter_api_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
```

- OpenRouter API 키는 https://openrouter.ai 에서 발급받을 수 있습니다.
- Supabase 프로젝트 생성 및 테이블 설정은 [SUPABASE_SETUP.md](SUPABASE_SETUP.md)를 참고하세요.

### 3. 실행

```bash
python app.py
```

브라우저에서 `http://127.0.0.1:5000` 접속.

## 프로젝트 구조

```
app.py                 Flask 앱 (라우트, 모델 호출, Supabase 연동)
templates/              Jinja2 템플릿
static/                 CSS, JS
PRD_step1~3.md          단계별 제품 요구사항 문서
SUPABASE_SETUP.md       Supabase 프로젝트/테이블 설정 가이드
```

## 참고

- 이미지 인식·레시피 생성 모델은 모두 OpenRouter 무료 티어(`:free`)를 사용합니다. 응답이 느리거나 드물게 형식이 깨질 수 있어, 레시피 생성은 자동 재시도 및 부분 복구 파싱으로 보완되어 있습니다.
