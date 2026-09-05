# Feedloom

一個內容蒐集器：每天蒐集近期高訊號的 AI 與資料科學動態，也挑出不限新舊、值得真正讀完的內容。正常結果會由 Codex 的每日自動化回覆在此任務；收集沒有回報錯誤，而且兩條線都沒有合格內容時，只回覆 `[SILENT]`。若來源收集出錯，摘要會註明涵蓋範圍不完整；沒有可選內容時則回報收集問題。

## 設計

`scripts/ai_news_collect.py` 只做可重跑的蒐集、正規化、初步評分與去重，並輸出 JSON。候選會標成 `latest` 或 `reading`：前者使用 36 小時窗口，後者從同一批 RSS／TLDR 來源回看 90 天，並要求分析、研究、實作或其他深度訊號。Hacker News 與 GitHub releases 維持近期窗口，避免放大例行更新。

摘要 agent 只可根據該 JSON 選出最多十則，通常保留一至五則最新動態，再加一至兩則值得閱讀的內容；不足時不硬湊數量，不得以即時搜尋補資料。

已涵蓋官方 OpenAI、Google AI、Google DeepMind、Hugging Face RSS、AWS Machine Learning Blog、NVIDIA Blog、TLDR AI（會展開為原文連結）、MIT Technology Review AI、The Verge AI、VentureBeat AI、TechCrunch AI、Hacker News Algolia 與指定 GitHub releases。單一來源錯誤會記錄在 `collection_errors`，不會阻止其餘來源繼續執行。

## 本機使用

```sh
python3 scripts/ai_news_collect.py --state state/ai_news_seen.json > /tmp/ai-news-candidates.json
python3 -m unittest discover -s tests -v
```

可用 `--reading-lookback-days N` 調整值得閱讀的回看窗口；預設為 90 天。

若已選出要推送的項目，把其 `id` 寫進 JSON，例如 `{"selected_ids": ["..."]}`，然後執行：

```sh
python3 scripts/ai_news_collect.py --mark-seen /tmp/selected-ids.json --state state/ai_news_seen.json
```

state 保留最近 14 天的已推送項目。因 Codex 的回覆交付後沒有可執行的 callback，排程會在產生最終報告前記錄已選項；若交付本身失敗，可刪除相應 state 項目讓下次重試。

預覽、草稿與品質檢視只讀取候選，不寄信，也不執行 `--mark-seen`。只有使用者或既有任務明確授權並指定收件者時才使用 Gmail，寄送 inline HTML，確認交付後才記錄已選項。完整的選材、交付與失敗處理規則見 [ai-news-briefing skill](.agents/skills/ai-news-briefing/SKILL.md)。

## 排程

此 repo 由目前 Codex 任務的每日 08:00 HKT heartbeat 使用。排程提示會讀取 `.agents/skills/ai-news-briefing/SKILL.md`，因此品質規則不依賴模型記憶或即時瀏覽。
