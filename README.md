# GitHub CLI搜尋工具
<img width="569" height="311" alt="image" src="https://github.com/user-attachments/assets/ac7f09d1-3621-43f0-a240-a8f4cf0e7ef2" />


## 需求

- Python 3.10 以上
- Node.js
- OpenRouter API key
- GitHub personal access token

## 安裝

```bash
pip install -r requirements.txt
```

## 環境變數

可放在專案根目錄的 `.env`，或直接使用系統環境變數：
請修改下列API KEY
```bash
OPENROUTER_API_KEY=sk-xxx 
GITHUB_TOKEN=github_xxx
```

- `OPENROUTER_API_KEY`：OpenRouter 金鑰
- `GITHUB_TOKEN`：GitHub personal access token

`.env` 已被 `.gitignore` 排除，不會提交到 repo。`tool.py` 支援：

- `KEY=value`
- `export KEY=value`
- 帶單引號或雙引號的值

## 互動式 CLI 工具

### 執行

```bash
python3 tool.py
python3 tool.py "找近期還有維護的 Python 安全工具"
```

### 流程

1. 選擇要使用的模型。
2. 將自然語言轉成 GitHub Search query。
3. 呼叫 GitHub Search API 並列出 repo。
4. 讓使用者選一個 repo 做深入查詢。
5. 根據 follow-up 問題補抓 README、語言比例、release 或 repo 基本資訊，再整理成繁中回答。

### 已修補的 failure modes

涵蓋題目點名的四類 break-testing（typos / conflicting constraints / non-English / ambiguous），以及開發過程中遇到的其他 code-side 問題：

- **Typos**：query 含 `pythn`、`securty`、`mroe`、`starrs` 等拼錯的 keyword 時，prompt 會先校正再組 query；eval 用 `not-icontains` 驗證誤拼字不會洩漏到最終輸出。
- **Conflicting constraints**：遇到互相矛盾的 qualifier（例：同時 `language:rust` 與 `language:go`，或 `stars:>1000` 與 `stars:<10`）時，依 prompt 規則只保留先出現或較合理的那一個，避免產生 0 筆結果。
- **Non-English**：中、日、混語輸入會把技術名詞翻成英文 keyword（如 `機器學習` → `machine learning`、`可視化` → `visualization`），`golang` / `node.js` 等別稱也會正規化到 `language:go` / `language:javascript`。
- `.env` 解析支援 `export` 與 quoted values，避免本地設定格式稍有不同就讀不到 key。
- OpenRouter / GitHub API 的 401、403、網路失敗都有明確錯誤訊息，不會直接 crash。
- 模型輸出會清除 code fence、多餘空白，以及部分 open-weight 模型洩漏的 reasoning control token。
- `INVALID_QUERY`、`CLARIFY_NEEDED`、空結果、repo 沒有 release 等情況都有對應分支處理。

### 仍然困難、而且本質上不容易完全解掉的部分

- **語意模糊**：像「找一些好工具」這類輸入，本質上缺少可落地成 GitHub qualifier 的約束；即使用更強的模型，也只能要求使用者補充條件。
- **跨語言翻譯細節**：多語混雜時，像「可視化」應該翻成 `visualization`、還是保留原文當自由文字，並沒有唯一正解；不同模型會在翻譯與保留原詞之間做不同取捨。
- **GitHub Search 的排序與索引限制**：即使 query 本身是合理的，GitHub 搜尋結果仍受索引、stars 排序、topic 標註品質影響，所以「最想找的 repo」不一定總在前幾筆。

## 多模型評估（promptfoo）

評估流程完全由 `promptfoo` 驅動，repo 內的 eval artifact 僅保留 [`eval/ground_truth.jsonl`](./eval/ground_truth.jsonl)（canonical query 清單）與 [`promptfooconfig.yaml`](./promptfooconfig.yaml)。

### 目前設計

每題都先在 [`eval/ground_truth.jsonl`](./eval/ground_truth.jsonl) 寫下 canonical GitHub Search query 作為 ground truth，實際評估再轉成 constraint-based oracle（`icontains` 必要 token、`not-icontains` 禁止 token、`regex` 等價寫法），避免模型用合法但不同的寫法被誤判為錯誤。這讓 ground truth 以獨立檔案存在、可被直接檢視，但不會被綁死在單一字串上。

- 30 筆 adversarial test cases 直接內嵌在 [`promptfooconfig.yaml`](./promptfooconfig.yaml)，每題對應 `ground_truth.jsonl` 同 `id` 的 canonical query。
- assert 使用 `equals`、`icontains`、`not-icontains`、`regex` 組合，容許語法等價但表達不同的 query。
- `defaultTest.options.transform` 會先清掉 control token、code fence 與多餘空白，再進行 assertions。
- provider 全部走 OpenRouter，方便用同一份 config 比較不同模型。

### 30 題設計方法

本專案採 taxonomy-driven curation：先固定題目點名的四類 break-testing 情境（ambiguous / conflicting constraints / typos / non-English），再依 GitHub Search qualifier 空間擴充為 8 個類別，每個類別下的測資都刻意針對該類別的核心規則設計，不堆 happy path。這比從公開 corpus 亂抓更能精準命中 failure mode。每題對應的 canonical query 記錄在 [`eval/ground_truth.jsonl`](./eval/ground_truth.jsonl)。類別分布如下：

| 類別 | 題數 | 目的 |
| --- | --- | --- |
| simple | 8 | 基本 language + 關鍵字對應，檢驗 happy path |
| filters | 8 | star / fork / license / date comparator / N+ vs >N 等 qualifier |
| multilingual | 4 | 中、日、中英混雜輸入，含專有名詞翻譯與別稱 |
| typos | 1 | 故意拼錯的 keyword，驗證修正規則 |
| contradiction | 1 | 同時給兩個矛盾 qualifier，驗證第一出現優先規則 |
| clarify | 3 | 資訊量不足，必須輸出 `CLARIFY_NEEDED` |
| invalid | 3 | 與軟體/程式碼無關，必須輸出 `INVALID_QUERY` |
| injection | 2 | 提示詞注入攻擊，必須輸出 `INVALID_QUERY`，不得洩漏 system prompt |

### 如何執行

```bash
promptfoo eval ＃進行測試
promptfoo view ＃查看結果
```

`view` 介面可以直接檢查每一題的原始輸出、assert 通過情況、token 統計與 latency。  
promptfoo 的執行歷史會存放在本地 `.promptfoo/`，該目錄已被 `.gitignore` 排除。

## 模型選擇
透過觀察https://artificialanalysis.ai/models
篩選出7 個候選模型

<img width="1402" height="489" alt="image" src="https://github.com/user-attachments/assets/2dba6ee8-7893-4d12-bcaa-ff6f3da40be0" />


這次把 7 個候選模型都放進同一輪 promptfoo sweep，比較它們在「GitHub query 生成」這個任務上的穩定度：

| Model | 選入理由 |
| --- | --- |
| gpt-oss-120b | 快、便宜、開源，但要自己維護設備，適合作為 open-weight baseline |
| grok-4.20 | 中間值參考，用來看非三巨頭 closed model 的表現 |
| claude-opus-4.7 | 頂尖模型，當作高能力上限對照組 |
| deepseek-v3.2 | 目前非常便宜的 hosted 模型，適合觀察高性價比選手 |
| gemini-3.1-pro-preview | 三巨頭之一，代表 Google 系列 |
| gpt-5.4 (xhigh) | 三巨頭之一，代表 OpenAI 高推理設定 |
| kimi-k2.5 | 前陣子在 OpenClaw agent 討論中很熱門，拿來做額外 open-style 候選比較 |

## promptfoo 實跑結果

這一輪是用同一份 `promptfooconfig.yaml` 跑 **30 題 × 7 個 providers**。  
下面數字直接整理自 promptfoo UI：

| Model                  | Cases | Asserts | Accuracy | Total Tokens | Avg Tokens | Avg Latency | Tokens/Sec | Est. Cost (USD) |
| ---------------------- | ----- | ------- | -------- | ------------ | ---------- | ----------- | ---------- | --------------- |
| gpt-oss-120b           | 29/30 | 84/86   | 96.67%   | 35,185       | 1,173      | 7,664 ms    | 21         | **$0.0040**     |
| grok-4.20              | 29/30 | 85/86   | 96.67%   | 31,783       | 1,059      | 764 ms      | 11         | **$0.1271**     |
| claude-opus-4.7        | 30/30 | 86/86   | 100.00%  | 43,568       | 1,452      | 1,478 ms    | 12         | **$0.6535**     |
| deepseek-v3.2          | 30/30 | 86/86   | 100.00%  | 29,794       | 993        | 2,032 ms    | 5          | **$0.0094**     |
| gemini-3.1-pro-preview | 30/30 | 86/86   | 100.00%  | 39,370       | 1,312      | 8,549 ms    | 38         | **$0.2756**     |
| gpt-5.4-xhigh          | 30/30 | 86/86   | 100.00%  | 28,844       | 961        | 1,465 ms    | 9          | **$0.2527**     |
| kimi-k2.5              | 20/30 | 52/86   | 66.67%   | 40,260       | 1,342      | 14,523 ms   | 26         | **$0.0491**     |

<img width="1440" height="779" alt="image" src="https://github.com/user-attachments/assets/626d4599-36fd-46f0-b19d-09fe66a9a128" />


### 哪些模型達到門檻

這次 sweep 中，以下 6 個模型都達成門檻，可以作為最後採用的模型集合：

- gpt-oss-120b
- grok-4.20
- claude-opus-4.7
- deepseek-v3.2
- gemini-3.1-pro-preview
- gpt-5.4-xhigh

`kimi-k2.5` 則保留在 config 裡做透明比較，但 **不納入最終達標模型集合**，因為這次只達到 66.67%。

## 觀察到的表現差異

- `claude-opus-4.7`、`deepseek-v3.2`、`gemini-3.1-pro-preview`、`gpt-5.4-xhigh` 在這輪都跑到 30/30。
- `gpt-oss-120b` 與 `grok-4.20` 都只差 1 題，代表它們大多能遵守 prompt 中對 qualifier、sentinel 與 comparator 的規則。
- `kimi-k2.5` 的失誤明顯更多，從 promptfoo UI 來看，主要是 qualifier-heavy case 比較容易漏掉 `language:` 或其他 required tokens，因此沒能過 85%。

## 學到的事

- **promptfoo 很適合做 structured-output regression**：一旦把 output normalize 與 asserts 定義清楚，重跑不同模型非常快，也很適合直接在 UI 看哪一題出錯。
- **規則密度夠高時，較弱模型很容易漏 qualifier**：`language:`、`fork:false`、日期 comparator、sentinel handling 這些都要在 prompt 裡講得非常硬，不然模型會退回比較鬆散的自然語言關鍵字。
- **把探索用的 sweep 結果和最後採用的模型集合分開寫會更清楚**：這輪 7 模型 sweep 幫助我看出 Kimi 在這個任務上明顯不穩定，但真正適合放進最終結論的，是那 6 個超過 85% 的模型。
