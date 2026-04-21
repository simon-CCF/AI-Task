#!/usr/bin/env python3
"""
GitHub Natural Language Search Tool
NL query → LLM → GitHub Search API → Repo deep dive
"""

import os
import sys
import json
import requests
import argparse
from datetime import datetime
# ── 設定 ──────────────────────────────────────────────────────────────────────

def load_dotenv(path=".env"):
    """手動載入 .env 檔，不需額外套件"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

load_dotenv()  # 載入 .env 檔案

def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    raise RuntimeError(f"缺少 {name}，請先在 .env 或系統環境變數中設定。")

# 可用模型清單，之後新增在這裡
AVAILABLE_MODELS = {
    "1": {
        "id": "openai/gpt-oss-120b:free",
        "name": "gpt-oss-120b (OpenAI)",
    },
    "2": {
        "id": "minimax/minimax-m2.5:free",
        "name": "Minimax M2.5 (Minimax)",
    },
    # 新增模型範例：
    # "3": {
    #     "id": "google/gemini-flash-1.5",
    #     "name": "Gemini 1.5 Flash (Google)",
    # },
}

# ── LLM 呼叫 ──────────────────────────────────────────────────────────────────

def call_llm(model_id: str, system: str, user: str) -> str:
    """透過 OpenRouter 呼叫指定模型"""
    headers = {
        "Authorization": f"Bearer {require_env('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github-nl-search",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
    }
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ── GitHub API ────────────────────────────────────────────────────────────────

def github_headers() -> dict:
    return {
        "Authorization": f"Bearer {require_env('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_search_repos(query: str, per_page: int = 10) -> list[dict]:
    """用 GitHub Search API 搜尋 repo"""
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": per_page}
    resp = requests.get(url, headers=github_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("items", [])


def github_get_repo(owner: str, repo: str) -> dict:
    """取得 repo 基本資訊"""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    resp = requests.get(url, headers=github_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def github_get_readme(owner: str, repo: str) -> str:
    """取得 README 內容（純文字，截前 3000 字）"""
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    headers = {**github_headers(), "Accept": "application/vnd.github.raw+json"}
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code == 404:
        return "（找不到 README）"
    resp.raise_for_status()
    return resp.text[:3000]


def github_get_languages(owner: str, repo: str) -> dict:
    """取得 repo 使用語言"""
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    resp = requests.get(url, headers=github_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def github_get_releases(owner: str, repo: str) -> list[dict]:
    """取得最新 5 個 release"""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    resp = requests.get(url, headers=github_headers(), params={"per_page": 5}, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── 格式化輸出 ────────────────────────────────────────────────────────────────

def fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return iso


def print_repo_list(repos: list[dict]):
    print("\n" + "═" * 60)
    print(f"  搜尋結果（共 {len(repos)} 個）")
    print("═" * 60)
    for i, r in enumerate(repos, 1):
        print(
            f"  [{i:2}] {r['full_name']}\n"
            f"       ⭐ {r['stargazers_count']:,}  "
            f"📅 {fmt_date(r['created_at'])}  "
            f"🗣  {r.get('language') or '未知'}\n"
            f"       {r.get('description') or '（無描述）'}"
        )
        print()


# ── 模型選擇 ──────────────────────────────────────────────────────────────────

def select_models() -> list[dict]:
    print("\n" + "═" * 60)
    print("  可用模型")
    print("═" * 60)
    for k, v in AVAILABLE_MODELS.items():
        print(f"  [{k}] {v['name']}")
    print("\n  輸入編號（逗號分隔多選，或輸入 'all' 全選）")
    choice = input("  > ").strip().lower()

    if choice == "all":
        return list(AVAILABLE_MODELS.values())

    selected = []
    for c in choice.split(","):
        c = c.strip()
        if c in AVAILABLE_MODELS:
            selected.append(AVAILABLE_MODELS[c])
        else:
            print(f"  ⚠️  忽略無效選項：{c}")

    if not selected:
        print("  未選擇任何模型，使用預設gpt-oss-120b (OpenAI)")
        return [AVAILABLE_MODELS["1"]]
    return selected


# ── 核心流程 ──────────────────────────────────────────────────────────────────

NL_TO_SEARCH_SYSTEM = """
你是 GitHub Search API 的 query 生成器。
使用者會用任意語言輸入自然語言描述，你必須：
1. 理解使用者意圖
2. 輸出一個 GitHub Search API 合法的 query 字串

GitHub Search query 語法範例：
- language:python topic:security stars:>100
- machine learning framework language:python stars:>1000 pushed:>2024-01-01
- web scraper language:javascript

規則：
- 只輸出 query 字串，不要有任何解釋或多餘文字
- 不要加引號包住整個 query
- 若輸入有衝突（如同時要 stars>1000 且 stars<10），回傳最合理的一個條件
- 若輸入太模糊，回傳最通用的合理 query
""".strip()

REPO_ENDPOINTS_SYSTEM = """
你是 GitHub API 助理。根據使用者的問題，決定需要查詢哪些 GitHub API endpoint。
可用的 endpoint 如下：
- info      : repo 基本資訊（描述、stars、forks、授權、語言等）
- readme    : README 全文
- languages : 使用語言比例
- releases  : 最新版本列表

只回傳需要的 endpoint 名稱，用逗號分隔，例如：info,readme
不要有任何解釋。
""".strip()

SYNTHESIZE_SYSTEM = """
你是一個專業的技術分析助理，請根據提供的 GitHub repo 資料，
以繁體中文完整且清楚地回答使用者的問題。
回答要有條理，重點清晰，適當使用列點。
""".strip()


def run(model: dict, nl_query: str) -> tuple[str, list[dict]]:
    """單一模型執行完整 Part 1 流程（Step 1-4），回傳 (github_query, repos)"""
    model_name = model["name"]
    model_id = model["id"]

    print(f"\n  🤖 [{model_name}] 正在將問題轉換為 GitHub query...")
    github_query = call_llm(model_id, NL_TO_SEARCH_SYSTEM, nl_query)
    print(f"  🔍 生成的 query：{github_query}")

    print(f"  📡 搜尋 GitHub...")
    repos = github_search_repos(github_query)
    return github_query, repos


def deep_dive(model: dict, owner: str, repo: str, follow_up: str):
    """Step 6-8：深入查詢指定 repo"""
    model_name = model["name"]
    model_id = model["id"]

    print(f"\n  🤖 [{model_name}] 判斷需要查詢哪些資料...")
    endpoints_str = call_llm(model_id, REPO_ENDPOINTS_SYSTEM, follow_up)
    endpoints = [e.strip() for e in endpoints_str.split(",")]
    print(f"  📋 需要查詢：{', '.join(endpoints)}")

    data_parts = []

    if "info" in endpoints:
        info = github_get_repo(owner, repo)
        data_parts.append(f"## Repo 基本資訊\n{json.dumps(info, ensure_ascii=False, indent=2)[:2000]}")

    if "readme" in endpoints:
        readme = github_get_readme(owner, repo)
        data_parts.append(f"## README\n{readme}")

    if "languages" in endpoints:
        langs = github_get_languages(owner, repo)
        data_parts.append(f"## 使用語言\n{json.dumps(langs, ensure_ascii=False)}")

    if "releases" in endpoints:
        releases = github_get_releases(owner, repo)
        release_summary = [{"tag": r["tag_name"], "date": r["published_at"], "name": r["name"]} for r in releases]
        data_parts.append(f"## 最新 Release\n{json.dumps(release_summary, ensure_ascii=False, indent=2)}")

    if not data_parts:
        data_parts.append(github_get_repo(owner, repo).__str__())

    combined_data = "\n\n".join(data_parts)
    user_prompt = f"使用者問題：{follow_up}\n\n---\n\n{combined_data}"

    print(f"\n  🤖 [{model_name}] 整理答案中...\n")
    answer = call_llm(model_id, SYNTHESIZE_SYSTEM, user_prompt)

    print("─" * 60)
    print(f"【{model_name} 的回答】")
    print("─" * 60)
    print(answer)
    print()


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GitHub 自然語言搜尋工具")
    parser.add_argument("query", nargs="?", help="自然語言搜尋問題（可用任何語言）")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  🐙 GitHub 自然語言搜尋工具")
    print("═" * 60)

    # 選模型
    models = select_models()

    # 取得 NL query
    if args.query:
        nl_query = args.query
    else:
        print("\n  輸入你的搜尋問題（支援任何語言）：")
        nl_query = input("  > ").strip()
        if not nl_query:
            print("  未輸入問題，結束。")
            sys.exit(0)

    # 多模型搜尋（如果多個模型，使用第一個做搜尋，其餘做比較）
    all_results = {}
    primary_repos = None

    for model in models:
        try:
            github_query, repos = run(model, nl_query)
            all_results[model["name"]] = {"query": github_query, "repos": repos}
            if primary_repos is None:
                primary_repos = repos
        except Exception as e:
            print(f"  ❌ [{model['name']}] 發生錯誤：{e}")

    if not primary_repos:
        print("  所有模型都失敗了，請檢查 API key 或網路連線。")
        sys.exit(1)

    # 如果多模型，顯示 query 比較
    if len(models) > 1:
        print("\n" + "═" * 60)
        print("  📊 各模型生成的 GitHub Query 比較")
        print("═" * 60)
        for name, result in all_results.items():
            print(f"  [{name}]\n  {result['query']}\n")

    # 顯示搜尋結果（用第一個模型的結果）
    print_repo_list(primary_repos)

    # 使用者選 repo
    print("  輸入 repo 編號進行深入查詢（或按 Enter 結束）：")
    choice = input("  > ").strip()
    if not choice:
        print("  結束。")
        sys.exit(0)

    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(primary_repos)):
            raise ValueError()
    except ValueError:
        print("  無效的編號，結束。")
        sys.exit(1)

    selected_repo = primary_repos[idx]
    owner = selected_repo["owner"]["login"]
    repo_name = selected_repo["name"]
    print(f"\n  ✅ 已選擇：{owner}/{repo_name}")

    # 深入查詢
    print("\n  你想了解這個 repo 的什麼？（例如：這個專案是做什麼的？最新版本是什麼？）")
    follow_up = input("  > ").strip()
    if not follow_up:
        print("  未輸入問題，結束。")
        sys.exit(0)

    for model in models:
        try:
            deep_dive(model, owner, repo_name, follow_up)
        except Exception as e:
            print(f"  ❌ [{model['name']}] 深入查詢失敗：{e}")

    print("═" * 60)
    print("  查詢完成！")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
