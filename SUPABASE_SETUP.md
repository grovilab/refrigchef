# Supabase 프로젝트 설정 가이드 (Step 3)

Step 3(회원가입/로그인/레시피 저장)는 Supabase를 데이터 저장소 + 인증으로 사용합니다. 아래 순서대로 진행해주세요.

## 1. 프로젝트 생성
1. https://supabase.com 접속 후 로그인/가입
2. "New project" 클릭 → 조직 선택 → 프로젝트 이름(예: `fridge-recipe`), 데이터베이스 비밀번호, 리전 설정 후 생성
3. 생성 완료까지 1~2분 정도 소요

## 2. 이메일 인증 설정 (로컬 테스트 편의를 위해)
1. 좌측 메뉴 `Authentication` → `Providers` → `Email` 클릭
2. "Confirm email" 옵션을 꺼주세요 (켜두면 가입 후 이메일 인증 전까지 로그인이 안 됩니다. 로컬 개발 단계에서는 꺼두는 걸 추천드려요)

## 3. 테이블 생성
좌측 메뉴 `SQL Editor` → "New query"에 아래 SQL을 붙여넣고 실행(Run)하세요.

```sql
create table public.profiles (
  id uuid references auth.users on delete cascade primary key,
  nickname text not null default '',
  allergies text[] not null default '{}',
  disliked_ingredients text[] not null default '{}',
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "Users can view own profile"
  on public.profiles for select
  using (auth.uid() = id);

create policy "Users can insert own profile"
  on public.profiles for insert
  with check (auth.uid() = id);

create policy "Users can update own profile"
  on public.profiles for update
  using (auth.uid() = id);

create table public.saved_recipes (
  id bigint generated always as identity primary key,
  user_id uuid references auth.users on delete cascade not null,
  name text not null,
  have_ingredients text[] not null default '{}',
  missing_ingredients text[] not null default '{}',
  steps text[] not null default '{}',
  estimated_minutes int,
  saved_at timestamptz not null default now()
);

alter table public.saved_recipes enable row level security;

create policy "Users can view own saved recipes"
  on public.saved_recipes for select
  using (auth.uid() = user_id);

create policy "Users can insert own saved recipes"
  on public.saved_recipes for insert
  with check (auth.uid() = user_id);

create policy "Users can delete own saved recipes"
  on public.saved_recipes for delete
  using (auth.uid() = user_id);
```

## 4. API 키 확인
1. 좌측 메뉴 `Project Settings` → `API`
2. `Project URL`과 `anon public` 키를 복사

## 5. .env에 값 채우기
프로젝트 루트의 `.env` 파일을 열어 아래 두 줄의 값을 채워주세요 (키 이름은 이미 만들어뒀습니다).

```
SUPABASE_URL=여기에_Project_URL_붙여넣기
SUPABASE_KEY=여기에_anon_public_키_붙여넣기
```

값을 채우신 뒤 알려주시면, 회원가입 → 로그인 → 레시피 저장 → 조회까지 이어서 테스트하겠습니다.
