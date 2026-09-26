# Flutter × Jev — 兩個對照實驗

目標：兩個可上台 demo + 一篇文章。用自製 demo app 當靶子（可開源、觀眾可重現）。

## 專案 A：E2E 測試三種寫法
同一個流程（登入 → 瀏覽訂單 → 發起退貨），三種實作並列計時計價：
1. `patrol` 手寫 selector（傳統基準線）
2. `marionette` + LLM（慢、貴）
3. `marionette` + Jev（快、便宜）

## 專案 B：GenUI 兩種寫法
同一個對話式訂單客服，左右雙欄同畫面：
1. Gemini 逐 token 串 A2UI JSON（現況）
2. Jev 從 catalog 選 surface，本機組 A2uiMessage

參照實作：`vercel-labs/json-render`（React 版，同架構）

## 已驗證
- [x] `TYPESAFE_API_KEY` 可用：`jev-1.13.0`，noul 0.98，302 in / 21 out tokens
- [x] `marionette_cli` 0.6.0 已安裝（`~/.pub-cache/bin/marionette`）
- [x] Flutter 3.47.1 / Dart 3.13.1；iPhone 17 Pro 模擬器 (iOS 26.5) 可用
- [x] `GEMINI_API_KEY` 在環境中（專案 B 的對照組不缺鑰匙）

## 已驗證（實測數字，我自己機器跑的）
- [x] **Jev choice wire format**：`criteria` = option_id → 描述；回傳帶 `confidence` + 全選項 `probabilities`
- [x] **一次呼叫可問多題**（choice + noul 並行），不加延遲
- [x] **decision loop 5/5 決策正確**（fixture：登入 → 填密碼 → Sign in → Orders → pass）
  - 中位延遲 **309ms**（首次 779ms 是 TLS 冷啟）；台灣 → 美西
  - `taskComplete` noul 從 0.02 爬到 0.84，訊號乾淨
  - 整段 3506 in / 467 out tokens = **$0.0001**
- [x] 磁碟：9.5GB → **24GB** free（舊 iOS 18.1/18.2 runtime 已刪，26.5 保留）

## 已知風險（要實測，不要假設）
1. ~~磁碟~~ 已處理
2. **marionette CLI 是 stateless**，每次呼叫開新連線。若 per-call overhead 吃掉 Jev 的 200ms，就改走
   `marionette mcp` 常駐 或 直接用 `vm_service` 打 `ext.flutter.marionette.*`。**要先量再決定**
3. **binding 衝突**：`MarionetteBinding` 必須是唯一 binding，patrol 的 `IntegrationTestWidgetsFlutterBinding`
   會撞。解法是 `kDebugMode` 閘門跳過（見 marionette flutter-setup.md），但這是 live demo 地雷，要先踩
4. `genui` 套件標 alpha / Experimental；Jev early access
5. Jev 不會生成字串 → 要打字的欄位得由程式碼提供值，或照 `jev-ultrafast` 的混合法叫小模型

## 交付物
- [ ] demo app（Flutter，可開源）
- [ ] 專案 A runner + patrol 對照測試 + 實測數據
- [ ] 專案 B 雙欄對照 + 延遲數據
- [ ] 比較報告（自己機器量的數字，不引用他人 demo 數字）
- [ ] 文章（article-writer）
- [ ] vault 筆記 + wiki-ingest
- [ ] 社群文案（依 feedback_writing_voice_exemplar 基準）
