# GitHub 自然語言搜尋工具

這個專案把自然語言問題轉成 GitHub Search API 查詢，先找出合適的 repository，再針對單一 repo 做進一步分析。

## 需求

- Python 3.10 以上
- OpenRouter API key
- GitHub token

## 安裝

```bash
pip install -r requirements.txt
```

## 環境變數

可以放在專案根目錄的 `.env`，或直接用系統環境變數設定：

- `OPENROUTER_API_KEY`：OpenRouter 金鑰
- `GITHUB_TOKEN`：GitHub personal access token

`.env` 已經被 `.gitignore` 排除，不會一起提交。

## 執行方式

直接互動執行：

```bash
python3 tool.py
```

帶入查詢內容：

```bash
python3 tool.py "找近期還有維護的 Python 安全工具"
```

## 功能流程

1. 選擇要使用的模型
2. 將自然語言轉成 GitHub Search query
3. 列出搜尋結果
4. 選擇單一 repo 深入查詢
5. 根據問題補抓 README、語言比例、release 或 repo 資訊

## Promptfoo 測試

`promptfooconfig.yaml` 內含 GitHub query 轉換的評估案例，可用來比較不同模型輸出是否穩定。

```bash
promptfoo eval
promptfoo view
```
