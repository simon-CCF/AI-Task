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

## 歷史調整

- 將模型設定 `gpt-oss-120b` 與 `Minimax M2.5` 兩個主要使用的模型
- 修正 OpenRouter model id 格式，避免把 prompt 測試用格式直接送到 API
- 補強查詢、深入分析與 GitHub 呼叫的錯誤處理，避免 401、403 或網路問題直接中斷
- 整理模型輸出解析，避免被 code fence、換行或多餘標點影響
- 查無結果、模糊輸入與無關輸入時，改成輸出對應提示，不再一律導向 API key 或網路問題
- `.env` 現在支援 `export KEY=value` 與帶引號的值，降低手動貼上設定時出錯的機率
- repo 沒有 release 時，深入查詢會回傳「目前沒有 release」，不會因為 GitHub 404 中斷整段流程

## 功能流程

1. 選擇要使用的模型
2. 將自然語言轉成 GitHub Search query
3. 列出搜尋結果
4. 選擇單一 repo 深入查詢
5. 根據問題補抓 README、語言比例、release 或 repo 資訊

## Promptfoo 測試

`promptfooconfig.yaml` 內含一組 smoke test，用來確認目前 prompt 規則有沒有維持在可接受範圍。

```bash
promptfoo eval
```

如果你想直接用目前 `tool.py` 的 prompt 跑實際 smoke test，也可以執行：

```bash
python3 tests/prompt_smoke.py
```

## 邏輯測試

```bash
python3 -m unittest discover -s tests -v
```

目前測試涵蓋：

- `.env` 載入
- query 輸出正規化
- endpoint 解析與 fallback
- 無關輸入攔截
- 查無結果分支
- 深入查詢 fallback 路徑

## 驗證結果

- `python3 -m unittest discover -s tests -v`：11/11 通過
- `python3 tests/prompt_smoke.py --json-out artifacts/prompt_smoke.json --svg-out artifacts/prompt_smoke.svg`：12/12 通過

驗證輸出位置：

- `artifacts/prompt_smoke.json`
- `artifacts/prompt_smoke.png`
- `artifacts/prompt_smoke.svg`
