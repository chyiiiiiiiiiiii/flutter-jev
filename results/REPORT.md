# Flutter × Jev — 兩個對照實驗的結果

日期：2026-09-21，2026-09-26 換品牌後全部重跑（見下一段）
機器：macOS 25.6，Flutter 3.47.1 / Dart 3.13.1，Python 3.13.2
網路位置：台灣 → TypeSafe 美西服務（他們自己的 eval 是在美西本地跑的）
模型：`jev-1.13.0`（TypeSafe early access）、`gemini-3.1-flash-lite`

所有數字都是這台機器上量的。沒有引用任何他人 demo 的數字。

## 2026-09-26：換掉 demo app 的品牌，全部重跑

最早的 demo app 在品牌、配色、商品和訂單號碼上，跟 Abdallah Shaban 在 X 上的
[Flutter GenUI × Jev demo](https://x.com/AbdallahSh07/status/2101719364450046351) 太像了。
那支 demo 是專案 B 這個方向的起點，但 app 不該看起來像是照著做的。所以整個換掉：

- 名稱改成 **Boxtide**（虛構的網購 app），logo、配色（鈷藍、冷白、珊瑚橘）、字型、登入頁與首頁版面全部重做
- 商品、訂單號碼（5184–5226）、地址、物流商全部換掉；service extension 改成 `ext.flutter.boxtide.*`
- 13 個畫面的結構和 widget key 不變，所以判定邏輯和手寫腳本的意義不變
- 商品頁的「加入購物車」「看購物車」移到固定在底部的一列，原本加入後跳出的 SnackBar 會蓋住「看購物車」，
  而 SnackBar 在的時候，底下的按鈕整個不在 widget tree 裡

換完之後，專案 A、B、D、E、F 和所有影片、GIF 全部重跑，舊資料整份刪掉。專案 C 是 Hacker News 選題，
沒有碰到 app，沒有重跑。重跑時處理過的三件事，照實記在這裡：

1. **手寫的購物車腳本裡還留著兩步 `scroll_to`。** 按鈕移到底部固定列之後，捲動什麼都沒做，
   runner 等畫面變化等到 6 秒逾時，腳本每次都慢了 6 秒多。這是腳本跟新 UI 對不上，不是 app 慢。
   刪掉那兩步之後重跑 `compare.py` 全部，以及 `arms.py` 裡 scripted × cart-flow 那三次（資料裡標了 `rerun`）
2. **churn 那一輪有一次跑到一半，API 回了空的 body（`JSONDecodeError`）。** 那不是模型的結果，
   只重跑那一格（seed 55 × hybrid-v2 × 1 次），資料裡標了 `rerun`
3. **新首頁有兩條同樣正確的路到訂單頁**（底部 Orders 分頁、「Your orders」捷徑）。Jev 在這一步的
   信心落在 0.34–0.53，退貨流程走到這一步的 27 次決策裡有 3 次剛好 0.34，低於點擊門檻 0.35，停下。
   這讓 hybrid-v2 從上一輪的 18/18、12/12 變成 17/18、11/12。**我沒有調門檻，也沒有改 UI 去閃這件事**，
   因為這正是風險分級門檻在處理的情況：機率分散在兩個都對的選項上，是誠實的答案

---

## 專案 A：E2E 測試，手寫腳本 vs Jev 決策

### 實驗設計

要比的是**決策層**，所以傳輸層必須完全相同。兩種模式都走同一條常駐 websocket、
同一組 `ext.flutter.marionette.*` service extension、同一套等畫面穩定的邏輯。
唯一的差別是：步驟是人寫的，還是 Jev 每一步現場選的。

拿 patrol 當對照組會同時換掉傳輸層和決策層，兩個變因混在一起，那樣的比較說明不了
任何事情。

靶子是自製的 13 畫面訂單客服 app（`demo_app/`，4,546 行 Dart），
每個可互動元件都帶 `Key` 與 Semantics `identifier`，並且刻意做出載入中、
空清單、載入失敗、按鈕停用、三步表單這些狀態。

### 結果（每條流程各跑 3 次，共 24 次，全綠）

| 流程 | 模式 | 通過 | 步數 | model calls | tokens | 成本 | 牆鐘時間 | 決策中位數 |
|---|---|---|---|---|---|---|---|---|
| return-flow | scripted | 3/3 | 10 | 0 | 0 | $0.0000 | 4.2s | — |
| return-flow | **jev** | 3/3 | 12 | 18 | 19,446 | $0.0008 | 12.8s | 233ms |
| cart-flow | scripted | 3/3 | 7 | 0 | 0 | $0.0000 | 2.9s | — |
| cart-flow | **jev** | 3/3 | 8 | 11 | 11,846 | $0.0005 | 4.4s | 230ms |
| support-flow | scripted | 3/3 | 9 | 0 | 0 | $0.0000 | 3.6s | — |
| support-flow | **jev** | 3/3 | 10 | 15 | 16,247 | $0.0007 | 5.6s | 221ms |
| address-flow | scripted | 3/3 | 10 | 0 | 0 | $0.0000 | 3.9s | — |
| address-flow | **jev** | 3/3 | 10 | 15 | 15,383 | $0.0006 | 5.7s | 236ms |

來源：`comparison-20260926T155645Z.md`、`runs-20260926T155645Z.json`。

**四條流程都是手寫腳本比較快。** 舊版 app 上 agent 在新增地址那條贏過一次，因為腳本得先捲動
再多等一次；新版面那顆按鈕不用捲，這個優勢就沒了。model calls 比步數多，是因為畫面在決策途中
變了會重問一次（「screen moved while deciding」）。

Jev 這邊的輸入是一句英文，例如
`"sign in with the demo account, open order 5207, and submit a return request for it"`。

### 三個可以直接引用的數字

- **一次完整測試跑平均 $0.0007**，約 15,700 input tokens。Jev 的 output token 免費
- **每個決策 221–236ms 中位數**，跨太平洋。TypeSafe 自己報 70–500ms，對得上
- **畫面壓縮 94%**。marionette 回傳每個 widget 的全部屬性，一個 9 元素的登入畫面
  就是 5,488 字元（約 1,370 tokens）；壓成模型看的格式是 337 字元（約 85 tokens）

### 成本換算

Jev input $0.042/MTok。一次跑 ~15,700 tokens。
- 每個 PR 跑四條流程：約 $0.0026
- 一天 20 個 PR：約 $0.05
- 一個月：約 $1.60

這個量級的意思是「不用進預算表」。

### 速度的真相：瓶頸不是模型

| 項目 | 佔一次 12.8s 的 return-flow |
|---|---|
| Jev 決策（18 次 × ~250ms） | 4.4s |
| 傳輸（189 次呼叫 × ~10ms） | 1.9s |
| **等 app 自己的動畫與載入** | **約 6.5s** |

修好傳輸層之後，模型和傳輸加起來不到一半。剩下的是 Flutter 的頁面轉場動畫，
加上我在 demo app 裡故意放的 260ms 假網路延遲。

**「agent 測試夠不夠快」這個問題問錯了。** 它的天花板是你的 app 本來就有多慢。

---

## 專案 B：GenUI，生成 payload vs 挑選 surface

### 實驗設計

被驗證的主張是「LLM 逐 token 串 A2UI JSON 很慢，Jev 只挑組件所以很快」。
直接比這兩個會同時換掉「生成 vs 挑選」和「LLM vs System One」兩個變因，
所以我加了中間那一格：

1. **generate** — Gemini 寫出完整的 A2UI `surfaceUpdate` payload（GenUI 現在的做法）
2. **select** — Gemini 只准回一個 surface 名字
3. **jev** — Jev 從同一份 catalog 挑一個 surface

1 vs 2 量的是「寫 payload」的代價。2 vs 3 量的是「模型類別」的代價。

12 個真實對話輪 × 3 模式 × 3 次重複 = 108 次呼叫。

### 結果

| 模式 | 與設計師預期一致 | 延遲中位數 | p90 | output tokens 中位數 |
|---|---|---|---|---|
| generate | 27/36 (75%) | 1,369ms | 1,792ms | 218 |
| select | 30/36 (83%) | 770ms | 884ms | 3 |
| **jev** | 25/36 (69%) | **225ms** | **257ms** | — |

來源：`genui-20260926T144222Z.md`、`genui-samples-20260926T144222Z.json`。

### 怎麼讀這張表

- **寫 payload 要價 600ms**（1,369 → 770ms），而且在這個樣本上**一致程度還更差**
  （75% 對 83%）。讓模型一邊決定一邊產出 JSON，兩件事都做不好
- **同樣是「挑一個」，Jev 比 flash-lite 快 3.4 倍**（770 → 225ms）
- **從現況到 Jev 是 6.1 倍**（1,369 → 225ms）。這是 GenUI 那個主張真正的數字
- **不要說 Jev 更準，這一輪它反而少對五題。** 25/36 對 30/36，多錯的集中在兩句：
  「where is my refund」選了 `order_list`，「what's in my cart」有兩次選了 `plain_reply`。
  12 句各跑 3 次，實質上是 12 題，分不出誰比較準，但也不能說一樣準
- 上一輪（舊品牌的資料）是 24 / 30 / 27，同一個方向：寫 payload 慢而且不比較準，Jev 最快、一致程度沒有比較好

### 三個模式都答錯的那一題

「I got the wrong size」三個模式都選 `order_list` 而不是 `return_form`。
仔細想它們是對的 —— 使用者沒說哪一張訂單，先給清單讓他挑合理。
是我標的「預期答案」可議。這種分歧本身就該列出來給人看，不該偷偷算成錯。

---

## 過程中踩到的坑（每一個都花掉一次失敗的跑）

這些不是 Jev 的問題，是「把 agent 接到真實 app」這件事的問題。

1. **hot restart 會換掉 isolate。** 常駐連線抓著舊的 isolate ID，查到的是一棵死樹，
   回傳 0 個元素 —— 讀起來像「這個 app 沒有任何 widget」

2. **marionette 回傳每個 widget 的所有屬性。** 不壓縮就是把 controller、decoration、
   colorSpace、textScaler 全部餵給模型。壓縮率 90%

3. **輸入框的現值藏在 controller 的 toString 裡**（`TextEditingValue(text: ┤...├`）。
   不把它挖出來給模型看，模型就不知道自己上一個按鍵有沒有生效

4. **沒有 key 的 InkWell / GestureDetector 會把選項塞滿。** 首頁一度出現八個
   `tap_gesturedetector_x_x_x_x`，把真正的選項擠掉、分布攤平。**那看起來像模型
   在一個顯而易見的選擇上沒信心，其實是我餵了垃圾選項**

5. **「畫面靜止」不等於「畫面到位」。** 按下送出按鈕會讓它變 disabled 並開始非同步
   工作，那個 busy 畫面可以一動不動地停留整個請求時間。等穩定會等在裡面，
   然後拿過期的畫面做下一個決策

6. **畫面外的元素完全不會被回報**，不是 `visible: false`，是根本不在清單裡

7. **marionette 的 `swipe` 配 type 匹配會回報成功但不會捲動。** 座標式 drag 才會

8. **marionette 的 `scrollTo` 一看到目標「技術上可見」就停**，正下方那顆按鈕還在
   畫面外。所以「捲到 A 然後點 A 下面的 B」這種腳本會掛

9. **SnackBar 會把它底下的按鈕從 widget tree 裡整個拿掉**，直到它自己消失

10. **marionette 的 screencast 錄影在這個用途上不可靠。** app 視窗不在前景時 macOS
    停止合成，串流就回舊畫格。==一支 24 秒、走過四個畫面的錄影，全程顯示登入頁==。
    改用每步主動 `takeScreenshots`，那是從當下的樹回答的，每一格都可證明屬於它標的那一步

11. **被殺掉的錄影程序會留下沒關的 screencast。** 一條漏掉的串流讓
    `interactiveElements` 從 4ms 變成 ==350ms（20 倍）==，看起來就像「app 變慢了」，
    而且會汙染之後所有量測。要明確呼叫 `stopScreencast`

12. **大量 screencast 操作之後 app 會卡死**：元素數變 0、截圖凍在同一張。
    重開 `flutter run` 才會好，hot restart 救不回來

13. **ffmpeg 的 `concat` demuxer 不會給靜態圖 wall-clock 時間戳**，所以
    `drawtext ... enable='between(t,a,b)'` 全部失效，每一格只會顯示碰巧符合它自己
    那個小 `t` 的字幕。字幕要**逐格烤進 PNG**，不要靠時間運算式

---

## 最有意思的一次意外

第一輪比較時，我手寫的 support-flow 腳本掛在 `contact_us_button`（在畫面外），
**但 Jev 通過了**。

看 trace 才知道它怎麼做的：第 5 步它在客服搜尋框打了 `refund`，把 FAQ 清單篩短，
`contact_us_button` 就浮上畫面了，第 6 步點下去。

沒有人把這一步寫進任何腳本。

誠實界定：那個 `refund` 字串是我的預設值表提供的（Jev 不能生成字串）。
**決定用搜尋框來推進**這件事是 Jev 做的。

另一邊也要誠實：我手寫的腳本改了四次才全綠 —— 加兩個 `scroll_to`、
再加一個 wait-and-retry。agent 在 scroll 原語修好之後，一次就過。

---

## 設計上學到最多的一件事：confidence 不是一個數字

我一開始設了 `MIN_CONFIDENCE = 0.55` 的全域閘門，結果模型選對了動作卻被我擋掉。

TypeSafe 文件寫得很清楚：

> low confidence on a Choice often means **none of the options are a clear
> winner over the others**

Choice 的 confidence 量的是「機率分布有多平」，也就是**選項互相競爭的程度**，
不是「答案對不對」。兩個動作都能推進時，低 confidence 是誠實的答案，擋掉它是錯的。

改成隨風險分級之後才對：

```python
CONFIDENCE_FLOOR = {
    "scroll": 0.20,   # 捲回去就好
    "fill":   0.30,   # 打字可以重打
    "tap":    0.35,   # 導航可以回上一頁
    "submit": 0.70,   # 會寫進去、使用者會看到
    "finish": 0.60,   # 判錯會讓整個測試在騙人
}
```

閘門是程式碼的責任，判斷才是模型的責任。

---

## 一個我自己出的 bug，剛好是這個專案要抓的那類

subagent 交件時回報：`Store.addresses` 與 `payments` 是 `const` list、沒有 mutator，
所以「新增地址」的 Save 按鈕會驗證、關閉 sheet、跳出「Address added.」的 SnackBar
—— **但什麼都沒存**。

==只驗 SnackBar 的測試會通過。== 這正是 agent 驅動測試要抓的那一類缺陷：
畫面說成功了，資料沒落地。

修法是把 list 改成可增長、加上 `addAddress` / `updateAddress` / `setDefaultAddress` /
`addPayment`，並把 `AddressesScreen` 與 `PaymentsScreen` 包進 `ListenableBuilder`
（它們原本直接讀 store 但不訂閱，存進去也不會重繪）。

然後補三個測試，斷言的是 **store 的狀態**不是 SnackBar：
- 存新地址後 `addresses.length` 要 +1，且 `address_addr_office` 要出現在列表
- 沒填 label 要被擋下來，`addresses.length` 不變
- 存卡片後 `payments.last.label` 要含末四碼

`address-flow` 就是為此加的：一條寫入並驗證的流程，斷言的是資料真的在那裡。

## 專案 C：倍數到底在哪裡（2026-09-22 追加）

### 為什麼要做這個

前兩個專案都沒有重現 TypeSafe 宣稱的 40-200 倍。專案 B 我只量到 3.0-4.7 倍。
原因有兩層，第二層才是關鍵。

**第一層：我的基準線比他們的強太多。** 官方原文寫的是

> LLM: **End-to-end response time is 3 to 329 seconds for frontier models.**
> TypeSafe: 70ms-500ms. This can range from **40x-200x faster**.

他們拿 frontier 模型做完整推理當對手。我拿 `gemini-3.1-flash-lite` 回三個 token
當對手（770ms）。==我的對手比他們的對手快了 4 到 430 倍==，所以倍數自然縮小。

**第二層：在驅動 UI 的用法裡，模型只佔三成多。** 一次乾淨的退貨流程 wall 12.8s，
其中模型 4.4s（重跑後的數字；舊品牌那輪是 14.52s 裡 4.39s，1.43 倍）。

| 模型如果變成 0 秒 | 端到端上限 |
|---|---|
| 12.8s → 8.4s | **1.53 倍** |

==就算 Jev 快到無限，整支測試最多只能快一倍半。== 剩下六成多是 Flutter 轉場動畫、
等畫面穩定、marionette 往返、步數本身。我調了一整輪都調不出倍數，是因為我在優化
一個只佔三成的部分。

### 實驗設計

回到單次呼叫，任務是真正 System One 形狀的：替日報做選題三判（要不要收、屬於哪一類、
技術深度）。三層，任務完全相同，只換模型類別。

- `jev` — 一次 systemOne，三個型別化問題平行作答
- `flash-lite` — 同樣三題，輸出 JSON，thinking 關掉（LLM 的最佳狀態）
- `pro` — 同樣三題，輸出 JSON，thinking 開啟（對得上官方基準線的那一格）

素材是 20 則**真實的 Hacker News 項目**（抓自 firebaseio API），跑 2 輪，每層 40 次呼叫。

### 結果

| 層 | 模型 | n | 中位數 | p90 | output tokens | thinking tokens | $/次 | 倍數 |
|---|---|---|---|---|---|---|---|---|
| jev | `jev-1.13.0` | 40 | **277ms** | 352ms | 90 | 0 | **$0.000025** | — |
| flash-lite | `gemini-3.1-flash-lite` | 40 | 967ms | 1162ms | 17 | 0 | $0.000110 | 3.5x / 4.4x |
| pro | `gemini-3.1-pro-preview` | 40 | 5390ms | 8837ms | 26 | 364 | $0.005552 | **19.5x / 220x** |

定價取自各家官方頁面（2026-09-22 查證）：Gemini flash-lite $0.25/$1.50 per MTok、
Pro Preview $2.00/$12.00（≤200k prompt）、Jev $0.042 input、output 免費。
Pro 的 thinking token 照 output 計價。

### 這張表怎麼讀

- ==對上會推理的 frontier 模型，單次呼叫是 19.5 倍快、220 倍便宜。==
  成本倍數落在官方宣稱的 40-400 倍區間內；速度 19.5 倍低於他們的 40-200 倍，
  但同一個量級（p90 是 352ms vs 8837ms = 25 倍）
- ==倍數跟「LLM 必須寫多少字」成正比。== Pro 吐 26 個 output token 加 **364 個
  thinking token**，那 364 個就是差距的來源
- 對上關掉 thinking 的小模型只有 3.5 倍。**這也是真的**，而且是很多人實際會拿來
  比的對手

### 必須一起講的代價

| 比較 | 一致率 |
|---|---|
| jev vs pro，`include` | 14/20 |
| jev vs pro，`category` | 13/20 |
| jev vs pro，兩者同時一致 | **9/20** |
| jev vs flash-lite，`include` | 16/20 |
| jev vs flash-lite，`category` | 15/20 |

官方寫「same levels of frontier intelligence」，==我量到的不是那樣==。在這個任務上
Jev 和 Pro 只有 9/20 完全一致。

但要公平：**這兩個都不是正確答案**。「資深工程師會不會想看這則」是主觀判斷，
兩個人也不會 100% 一致。所以這是「一致率」不是「準確率」，我沒有 ground truth。
誠實的說法是：==快 19.5 倍、便宜 220 倍，答案有三分之一會不一樣，而哪個對無法從
這個實驗判定。==

### 結論

> Jev 的倍數宣稱在「smart if-statement」那類用法上是真的，
> 在「驅動 UI」那類用法上幾乎看不見。
> 分界線是**模型呼叫佔總時間的比例**。

這也解釋了為什麼官方 demo 看起來都很快：playground、分類、路由那些例子裡，
單次呼叫就是整個任務，所以倍數就是體感。一旦模型只是一個要跟真實 app 來回講話的
迴圈裡的一小步，倍數就被稀釋掉了。

順帶一提，官方那支 Flutter 遊戲 demo（marionette 作者本人）是 **9.7 秒 / $0.0012**,
跟我量到的 4.4–12.8 秒同一個量級，他的成本還高一倍多。==他那支展示的不是「快幾百倍」,
是「一句話讓它贏一個沒見過的遊戲」。==

---

## 專案 D：讓差異看得見（2026-09-22 追加）

### 為什麼要做這個

使用者看完前面所有影片之後說了一句話，我認為那是整個專案最重要的回饋：

> 「連我自己看的時候都不知道 Jev 到底好在哪裡。它速度沒那麼快，就沒有那麼有感。」

他是對的，而且原因不是調參，是**我選錯任務**。

看官方那支最有感的 demo：一句話「win the game」，一個沒見過的遊戲，規則只寫在畫面上。
==你看著它解一件你知道它沒被教過的事。== 9.7 秒在那裡只是「快到你不會失去興趣」，
不是賣點。

再看我的：登入 → 訂單 → 退貨。**任何人看了都會想「這個我十分鐘就寫完腳本了」。**
任務沒有謎團，agent 沒做出觀眾自己指定不出來的事，於是可比的只剩速度，而速度它輸。

==他們展示的是「腳本做不到的事」，我卻拿一個腳本做得很好的任務去比速度。==

### 設計：讓 app 每次跑都不一樣

在 demo app 裡加一個 chaos 模式，用 `registerMarionetteExtension` 註冊成
`ext.flutter.boxtide.setChaos`，runner 可以在執行期設定 seed 而不用重建 app。

一個非零 seed 會：
- **改掉五分之二的 widget key**（用 FNV hash 決定哪些，所以每個 seed 壞在不同的地方）
- 同時改掉 Semantics identifier（==只改 key 不改 identifier 等於沒改==，工具會 fallback）
- 換掉按鈕文案（Sign in → Log in、Continue → Next step）
- 洗掉訂單列表順序
- 有時多插一個確認步驟

這不是人為刁難，==這就是真實的一週==：有人改了名字、有人調了順序、有人加了一道確認。
而那正是 E2E 測試最痛的地方。

### 結果（seed 4，key 尾碼 `_v14`）

| 模式 | 結果 | 步數 | 時間 | 成本 |
|---|---|---|---|---|
| 手寫腳本 | **FAIL 在第 4 步** | 4 | 3.1s | $0.0000 |
| Jev | **PASS** | 13 | 18.7s | $0.0006 |

（重跑後 `ui-churn` 那支影片的那一次跑。）

腳本去找 `nav_orders`，app 現在叫 `nav_orders_v14`，它停在那裡。

Jev 的 trace 是這個專案最有說服力的一段：

```
step 4: Tap @e7, the NavigationDestination nav_orders_v14
step 7: Tap @e2, the FilledButton start_return_button_v14
step 8: Tap @e3, the FilledButton return_next_button_v14
```

==它從畫面上讀到新名字就直接用了，沒有人告訴它發生了什麼事。==

不同 seed 壞在不同步驟（實測）：

| seed | 改掉的 key | 腳本死在 |
|---|---|---|
| 7 | `email_field`、`order_5207` | 第 1 步 |
| 55 | `signin_button`、`order_5207`、`return_confirm` | 第 3 步 |
| 4 | `nav_orders`、`start_return_button`、`return_next_button` | 第 4 步 |
| 91 | `email_field`、`start_return_button` | 第 1 步 |

### 所以凸顯點是什麼

**不是速度。** 是這句：

> ==手寫測試把 UI 的實作細節編碼進測試裡，agent 不編碼。==
> 所以 UI 一變，一邊要改，一邊不用。

這個差異**跟倍數完全無關**，倍數是 0.5 倍它也成立。而且台下每個寫過 E2E 測試的人
都被 selector 維護搞過，不需要解釋。

### 做這支影片時修掉的一個構圖缺陷

第一版做出來，**整支影片最重要的那一格根本沒播出來**：失敗字幕的時間窗寬度接近零
（失敗步驟的時間點就是整跑結束的時間點），結算條立刻蓋掉它。
==我是去截 t=7.0s 的畫面才發現的，不是看影片看出來的。==
現在最後一格保證有 2.8 秒，而且失敗字幕會直接寫出「app 現在叫它什麼」。

---


## 專案 E：誰來決定、誰來寫字（2026-09-25 追加）

### 為什麼要做這個

前四個專案都只比了「手寫腳本 vs Jev」。沒回答的問題是：**換成 LLM 來驅動 E2E 會怎樣，
兩者搭配又會怎樣。** 文章裡關於 LLM 那一側的說法（要 parse、要驗證、要重試、會編出不存在的按鈕）
都是推論，沒有量過。

### 實驗設計

六種做法，同一個 app、同一個傳輸層、同一份畫面壓縮、同一組候選動作：

| 代號 | 誰挑下一步 | 要填的字從哪來 |
|---|---|---|
| `scripted` | 手寫腳本 | 寫死在腳本裡 |
| `jev` | Jev | 手寫預設值表 |
| `lite` | `gemini-3.1-flash-lite`（推理關閉） | 手寫預設值表（只換決策者，隔離變因） |
| `lite-free` | flash-lite | flash-lite 自己寫（純 LLM） |
| `pro-free` | `gemini-3.1-pro-preview`（推理開啟） | Pro 自己寫（純旗艦 LLM） |
| `hybrid` | Jev | flash-lite 只負責寫字，每遇到新的一組欄位才呼叫一次 |

LLM 那一側給的是它最好的條件：`responseSchema` 把 `action` 限制成候選 id 的 enum，
也就是一個認真的團隊會上線的寫法。LLM 沒有機率分布，所以請它自報 confidence，
套用同一張風險分級表。

**判定不看 agent 自己說什麼。** demo app 加了 `boxtide.state` 這個 service extension，
每跑完一次就讀 store：訂單狀態、購物車、地址、客服單。「agent 說 pass 但 store 裡沒發生」
記為 **false pass**，這是整個實驗最重要的一欄，因為一支會說謊的綠燈測試比紅燈還糟。

任務六個，前四個是原本的流程，後兩個是**預設值表沒有涵蓋的新任務**：

- `address-home`：新增標籤 Home、地址 5F, 12 Zhongshan Rd（表裡是 Office / Taiyuan Rd）
- `support-damaged`：回報訂單 5198 到貨損壞（表裡是 5213 / 包裹沒動）

每格 3 次，scripted 只跑原本四條，加上 `hybrid-v2`（見下），共 120 次。

### 一個差點讓整輪作廢的環境問題

第一輪跑到一半，所有做法都在登入後同一個地方死掉：畫面讀出來 0 個元素。
原因是 app 視窗被別的視窗整個蓋住，macOS 對完全被遮住的視窗停止出 frame，
下一頁永遠 build 不出來。==這種失敗在每一種做法上長得一模一樣，很容易被誤讀成模型的結果。==
修法是每次跑前把 app 叫到前景，並把「讀到空畫面」的次數記進每一筆資料。正式那一輪是 0 次，
換品牌後的重跑也是 0 次。第一輪的資料整份丟掉。

### 結果

| 做法 | 真的完成 | false pass | 牆鐘中位數 | 平均每次成本 | 決策中位數 |
|---|---|---|---|---|---|
| scripted（只有原四條） | 12/12 | 0 | 3.8s | $0 | — |
| jev | 12/18 | 0 | 5.4s | $0.00063 | 243ms |
| lite | 12/18 | **6** | 14.9s | $0.00360 | 1006ms |
| lite-free | 18/18 | 0 | 14.5s | $0.00344 | 992ms |
| pro-free | 14/18 | 0 | 49.2s | $0.05339 | 3427ms |
| hybrid | 17/18 | 0 | 8.5s | $0.00091 | 241ms |
| **hybrid-v2** | **17/18** | **0** | **8.6s** | **$0.00094** | 241ms |

逐格明細在 `results/arms-20260926T145308Z.md`，原始資料（含每次跑完的 store 快照）在
`arms-runs-20260926T145308Z.json`。hybrid 和 hybrid-v2 各少的那一次，都是退貨流程在
`nav_orders` 信心 0.34 停下（見文首第 3 點），不是寫錯。

### 怎麼讀這張表

**1. 最重要的一格：同樣餵錯的資料，只有一邊會說謊。**

`support-damaged` 這題，`jev` 和 `lite` 拿到的是同一張錯的預設值表（5213、包裹沒動）。

- `lite`：送出時自報 confidence 0.9，接著以 1.0 宣告 pass。store 裡多了一張
  **訂單 5213、內容是包裹沒動**的客服單。三次都是綠燈，三次都是錯的
- `jev`：填完欄位後，送出按鈕的 confidence 掉到 0.30，或想回報 fail（0.33、0.36）。
  三次都停在門檻前（送出 0.70、判定 0.60），store 裡沒有任何寫入

`address-home` 也一樣：`jev` 填了 Office 之後，儲存的 confidence 掉到 0.28–0.34，停下。
`lite` 這一輪也說謊了：照表存了一筆 Office 地址，以 1.0 宣告 pass，三次都是。
（舊品牌那一輪它沒說謊，而是在既有的 Home 地址之間來回點到 25 步上限。）

==Jev 的機率分布「注意到」填進去的東西跟任務對不上，LLM 自報的 confidence 沒有。==
這是第五節那張風險分級表第一次有實測支撐，而不只是「用起來全綠」。

誠實界定：temperature 0，三次重複不是三個獨立樣本，比較接近「同一個情境看了三遍」。
這是一個情境、兩題，不是校準曲線。

**2. 文章第一節那個「LLM 會編出不存在的按鈕」，在結構化輸出下不成立。**

LLM 那一側 54 次跑、749 次決策，retries 是 **0**。用 enum 限制候選 id 之後，
挑到不存在的動作這件事在 LLM 這邊也被擋掉了。Jev 在這點上的結構優勢，
現代 LLM 的 structured output 也拿得到。剩下的差別在**速度、成本、以及那個機率有沒有意義**，
而第 1 點說明後者是真的差別。

**3. 預設值表是純 Jev 的天花板。**

`jev` 的 6 次失敗全部在兩題新任務上，而且全部是安全地停下，沒有寫錯東西。
表裡沒有的字它打不出來。`lite-free` 和 `pro-free` 在新任務上 12/12。

**4. 搭配是這次最好的組合。**

`hybrid-v2` 17/18、0 false pass、8.6 秒、每次 $0.00094：

- 比純 LLM（lite-free）快 1.7 倍、便宜 3.6 倍；準確率差一次，那一次是安全停下
- 比旗艦 LLM（pro-free）快 5.8 倍、便宜 57 倍，而且更準（Pro 14/18：support-flow 0/3，
  三次都走進訂單 5213 的物流追蹤頁而不是客服分頁，最後自己回報做不到）
- 比純 Jev 多花約 50% 的錢，換到新任務從 0/6 變成 6/6

寫字的呼叫很少：一次跑平均 2.7 次（登入一次、表單一次），其餘步驟都是 Jev。

`hybrid` 第一版在舊品牌那一輪漏過一次（address-flow），是我寫的 prompt 錯：任務沒講街道地址，
我叫 writer「任務不需要的欄位留空」，它就把必填的地址欄留空了。Jev 在儲存時 confidence 0.29，
停下，沒有寫錯東西。v2 加一句「必填但任務沒講的，寫一個合理的值」。這一輪重跑兩版都跑了，
v1 沒有再踩到那個坑，兩版各少的一次都是 `nav_orders` 那個導航停下。

**5. 手寫腳本還是最快，只要它是對的。**

原四條流程 12/12、3.8 秒，沒有任何模型比它快。新任務它根本沒有，得有人去寫。

### 結論

- 驅動 UI 這件事，**讓 Jev 挑、讓 LLM 寫**是最划算的組合：準確率跟純 LLM 差一次安全停下，
  速度、成本好上好幾倍，而且沒有謊報
- Jev 對 LLM 真正的差別不是「不會幻覺」（structured output 也做得到），
  是**它的機率在輸入錯的時候會掉下來**，而 LLM 自報的不會
- 旗艦 LLM 在這種迴圈裡最慢、最貴，而且沒有比較準

## 專案 F：UI 改了之後誰還能跑（2026-09-25 追加）

專案 D 只有一個 seed、一次跑。這裡把它補成 4 個 seed × 4 種做法 × 3 次，一樣讀 store 判定。
任務是退貨流程，seed 7、55、4、91 各自改掉不同的 key（見專案 D 的表）。48 次跑、0 次讀到空畫面。

| 做法 | seed 4 | seed 7 | seed 55 | seed 91 | 合計 | false pass | 牆鐘中位數 | 平均每次成本 |
|---|---|---|---|---|---|---|---|---|
| scripted | 0/3 | 0/3 | 0/3 | 0/3 | **0/12** | 0 | 2.3s | $0 |
| jev（手寫值表） | 3/3 | 0/3 | 3/3 | 0/3 | 6/12 | 0 | 14.0s | $0.00052 |
| lite-free（純 LLM） | 3/3 | 3/3 | 3/3 | 3/3 | 12/12 | 0 | 18.7s | $0.00462 |
| **hybrid-v2** | 2/3 | 3/3 | 3/3 | 3/3 | **11/12** | 0 | **9.6s** | **$0.00108** |

原始資料：`results/arms-runs-20260926T153649Z.json`，表：`arms-20260926T153649Z.md`。
hybrid-v2 在 seed 4 少的那一次，是 `nav_orders_v14` 信心 0.34 停下（見文首第 3 點）。

- 腳本死在第 1 步（seed 7、91 改了 `email_field`）、第 3 步（seed 55）、第 4 步（seed 4），跟專案 D 記錄的一致
- ==「只有 Jev」的 6 次失敗全在 seed 7、91：改到的是 email 欄位，而手寫值表用舊的 key 名查值。==
  查不到值，Jev 只能點那個欄位、打不了字，信心掉到門檻下，停。沒有一次謊報
- ==預設值表也是一種 selector。== UI 改名時它跟腳本一樣會斷，只是斷得安全
- hybrid 讓 LLM 看著當下畫面寫值，在 `email_field_v17` 直接填進 email。對上純 LLM 11/12 對 12/12，快 1.9 倍、便宜 4.3 倍

## 影片與 GIF

`results/media/`，由 `runner/record_steps.py`、`runner/record_gif.py` 產生，可重現。換品牌後全部重錄。

| 檔案 | 內容 |
|---|---|
| `hybrid-run.gif` / `hybrid-run-en.gif` | **一次實際的 hybrid-v2 跑**（回報訂單 5198 損壞）。黑底標籤是 Jev 挑的動作，框線標籤是 LLM 寫的字，最後一格是 app 裡實際收到的客服單。中文版 10 步 7.0s $0.0008，英文版 10 步 7.5s $0.0008。影格和 `sequence.json` 放在同名資料夾 |
| `support-recovery.mp4` / `.gif` | **失敗 vs 復原**。左邊手寫腳本撞到畫面外的 `contact_us_button` 就停（FAIL, 5 步, 3.8s, $0.0000）；右邊 Jev 在搜尋框打 `refund` 把清單篩短、按鈕浮上來，然後走完（PASS, 10 步, 10.0s, $0.0004） |
| `return-both-pass.mp4` / `.gif` | **兩邊都成功**。手寫 10 步 8.3s $0.0000；Jev 12 步 17.7s $0.0005。這支證明 agent 不是只有在腳本壞掉時才有用 |
| `singlecall-race.mp4` / `.gif` | **三方賽跑**（專案 C）。同一個問題、三個模型，進度條按共同時間軸比例，所以 Jev 停在 5% 的位置。收尾是 19.5x faster / 210x cheaper，==下面一行同時標出 9/20 的一致率==，不會只放倍數 |
| `ui-churn.mp4` / `.gif` | **專案 D，我認為這是最該放在文章裡的一支。** 同一個 churn 下手寫腳本 FAIL 在第 4 步、Jev PASS。標頭直接寫「10 selectors, written before someone renamed things」對「reads whatever the screen calls things now」，字幕會顯示 `nav_orders_v14` 這種新名字 |
| `jev-full-comparison.mp4` | **完整版 55.2 秒**，三段接起來，每段前面有一張說明卡寫清楚那一段在回答什麼問題、數字是多少。收尾卡放結論：倍數在「一次呼叫就是整個任務」時是真的，在「呼叫只是迴圈裡一步」時消失。由 `singlecall/stitch.py` 產生，可重現 |

兩支都把**跑錶與累計花費燒在畫面上**，左右共用同一條真實時間軸，所以一邊失敗就停在那裡、
另一邊繼續走。每一格都是那一步的實際截圖，不是螢幕錄影。

一件要誠實說的事：舊品牌那一輪 `return-both-pass` 重錄過一次，第一次 Jev 在第 4 步被 confidence
閘門攔下變成 UNCERTAIN。換品牌後這一步就是文首第 3 點的 `nav_orders`，大約十次會有一次停在 0.34。
這次重錄一次就過，但那是運氣的一部分。==上台講的時候要講這件事，不要只播過的那一支。==

## 還沒做的

- **視覺化的 GenUI 畫面：刻意不做。** 專案 B 是量測，不是畫面。做成畫面就會跟 Abdallah Shaban
  那支 demo 長得一樣，而這個 repo 要講的是 E2E；要看 GenUI 畫面請看他的原作
- **真實產品的對照。** 兩顆地雷還沒拆：測試環境跟正式環境還沒拆開，而 app 已經用了
  `SentryWidgetsFlutterBinding`，會跟 `MarionetteBinding` 撞
- **patrol 對照組。** 現在的基準線是同傳輸層的手寫腳本，那對「隔離決策層」是對的，
  但社群認得的是 patrol，上台講的時候值得補一格
