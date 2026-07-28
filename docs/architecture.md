# 아키텍처 다이어그램

`app.py`와 `templates/`에 직접 정의된 함수·템플릿만을 대상으로 합니다. Flask/OpenAI/Supabase 등 외부 라이브러리 호출은 표현하지 않았습니다.

## 1. 함수 호출 관계도

```mermaid
flowchart TD
    subgraph Routes["라우트 핸들러"]
        index
        recognize
        confirm
        options
        recipes
        recipe_detail
        save_recipe
        signup
        login
        logout
        profile
        my_recipes
        my_recipe_detail
        delete_recipe
        too_large
    end

    subgraph Helpers["헬퍼 함수"]
        get_client
        ensure_profile
        login_required
        allowed_file
        parse_ingredients
        normalize_recipe
        parse_recipes
        build_recipe_prompt
        as_str_list["_as_str_list"]
    end

    recognize --> allowed_file
    recognize --> parse_ingredients

    recipes --> get_client
    recipes --> build_recipe_prompt
    recipes --> parse_recipes
    parse_recipes --> normalize_recipe
    normalize_recipe --> as_str_list

    save_recipe --> get_client
    signup --> get_client
    signup --> ensure_profile
    login --> get_client
    login --> ensure_profile
    profile --> get_client
    profile --> ensure_profile
    my_recipes --> get_client
    my_recipe_detail --> get_client
    delete_recipe --> get_client

    login_required -.감쌈.-> save_recipe
    login_required -.감쌈.-> profile
    login_required -.감쌈.-> my_recipes
    login_required -.감쌈.-> my_recipe_detail
    login_required -.감쌈.-> delete_recipe
```

## 2. 라우트 → 템플릿 렌더링 & 템플릿 상속 구조

```mermaid
flowchart LR
    subgraph R["라우트 핸들러"]
        index
        recognize
        confirm
        options
        recipes
        recipe_detail
        signup
        login
        profile
        my_recipes
        my_recipe_detail
    end

    subgraph T["템플릿(컴포넌트)"]
        base["base.html"]
        indexHtml["index.html"]
        reviewHtml["review.html"]
        optionsHtml["options.html"]
        recipesHtml["recipes.html"]
        recipeDetailHtml["recipe_detail.html"]
        signupHtml["signup.html"]
        loginHtml["login.html"]
        profileHtml["profile.html"]
        myRecipesHtml["my_recipes.html"]
        myRecipeDetailHtml["my_recipe_detail.html"]
    end

    index --> indexHtml
    recognize --> reviewHtml
    confirm --> optionsHtml
    options --> optionsHtml
    recipes --> recipesHtml
    recipe_detail --> recipeDetailHtml
    signup --> signupHtml
    login --> loginHtml
    profile --> profileHtml
    my_recipes --> myRecipesHtml
    my_recipe_detail --> myRecipeDetailHtml

    indexHtml -.extends.-> base
    reviewHtml -.extends.-> base
    optionsHtml -.extends.-> base
    recipesHtml -.extends.-> base
    recipeDetailHtml -.extends.-> base
    signupHtml -.extends.-> base
    loginHtml -.extends.-> base
    profileHtml -.extends.-> base
    myRecipesHtml -.extends.-> base
    myRecipeDetailHtml -.extends.-> base
```

`save_recipe`, `logout`, `delete_recipe`, `too_large`는 `render_template`을 호출하지 않고 `redirect`만 수행하므로 다이어그램 2에서 제외했습니다.
