# Failure Log

本檔案依 `CLAUDE.md` 規範，紀錄 break-testing 過程中觀察到的 failure case，
分成「已修補」與「本質上仍困難、只能 mitigate」兩類。

---

## 已修補

### Failure: `.env` 解析對格式變體太嚴格
Input: `.env` 內容為 `export OPENROUTER_API_KEY="sk-..."`
Expected: 正常讀到 key
Actual: 早期版本只吃 `KEY=value`，遇到 `export` 前綴或含引號的值會整行讀錯
Severity: Critical
Fixed: Yes
Fix: `tool.py` 的 `.env` loader 支援 `export KEY=value`、單引號與雙引號三種常見寫法

### Failure: OpenRouter / GitHub 的 401、403、網路錯誤直接噴 stack trace
Input: 任何 query（當 `OPENROUTER_API_KEY` 失效或 `GITHUB_TOKEN` 權限不足時）
Expected: 給使用者一行清楚的錯誤訊息
Actual: `requests` 直接 raise，CLI 使用者看到一整段 traceback
Severity: Critical
Fixed: Yes
Fix: 集中捕捉 HTTP 錯誤與連線錯誤，轉成含狀態碼與可能原因的簡短訊息再印出，不讓例外直接冒到最外層

### Failure: 模型輸出夾帶 code fence 或 reasoning control token
Input: "Find Python web frameworks"（部分 open-weight 模型）
Expected: `language:python web framework`
Actual: 輸出為 ```` ```\nlanguage:python web framework\n``` ````，或前綴含 `<|channel|>final<|message|>`
Severity: Medium
Fixed: Yes
Fix: CLI 與 `promptfooconfig.yaml` 的 `defaultTest.options.transform` 都套同一套清洗：先取 `<|channel|>final` 之後的段落，再剝掉 code fence 與多餘空白

### Failure: sentinel / 空結果分支缺失
Input: "幫我一下"、"How do I cook pasta carbonara?"、正常 query 但 GitHub 回 0 筆、或選到的 repo 沒有 release
Expected: 分別走 `CLARIFY_NEEDED`、`INVALID_QUERY`、空結果提示、「此 repo 尚無 release」提示
Actual: 早期會把 sentinel 字串當成一般關鍵字送去 GitHub Search，或在 follow-up 取 release 時 crash
Severity: Critical
Fixed: Yes
Fix: 送 API 前先比對 sentinel 走 clarify / reject 分支；follow-up 對空 releases 與空 results 都加 guard

---

## 本質上仍困難（已 mitigate，未完全解掉）

### Failure: 高度模糊的自然語言輸入無法落地成 qualifier
Input: "找一些好用的工具"
Expected: 一個有意義的 GitHub Search query
Actual: 句子本身沒有 language / topic / 任何可量化 filter，模型若硬猜只會產生雜訊
Severity: Medium
Fixed: No
Fix: 走 `CLARIFY_NEEDED` 請使用者補條件。根本原因是輸入缺資訊，屬於 mitigation 而非 solution

### Failure: 跨語言名詞沒有唯一正解
Input: "資料可視化工具"
Expected: 穩定的英文關鍵字（`visualization` / `dataviz` / `visualize` 擇一）
Actual: 不同模型在「保留 可視化」「翻成 visualization」「翻成 data visualization」之間搖擺
Severity: Low
Fixed: No
Fix: prompt 已加上常見映射（機器學習 → machine learning、可視化 → visualization 等）；eval 端改用 regex 允許多種等價寫法，降低誤判但沒有消除模糊性

### Failure: GitHub Search 本身的排序與索引限制
Input: 任何語法正確的 query（例：`language:python stars:>500 security`）
Expected: 「最對的 repo」出現在前幾筆
Actual: 結果受 GitHub 索引延遲、stars 排序、topic 標註品質影響，理想目標可能被排到後面
Severity: Low
Fixed: No
Fix: 工具本身無法改變 GitHub Search 行為。目前的 mitigation 是讓使用者選 repo 後做 deep dive（讀 README、語言比例、release）再由模型重新整理回答
