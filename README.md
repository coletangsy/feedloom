# AI news automation

每天蒐集、篩選並以繁體中文整理值得留意的 AI 與資料科學新聞。正常結果會由 Codex 的每日自動化回覆在此任務；沒有合格內容時只回覆 `[SILENT]`。

## 設計

`scripts/ai_news_collect.py` 只做可重跑的蒐集、正規化、初步評分與去重，並輸出 JSON。摘要 agent 只可根據該 JSON 選出最多六則新聞，不得以即時搜尋補資料。

已涵蓋官方 OpenAI、Google AI、Google DeepMind、Hugging Face RSS、The Verge AI、VentureBeat AI、TechCrunch AI、NVIDIA Blog、Hacker News Algolia 與指定 GitHub releases。單一來源錯誤會記錄在 `collection_errors`，不會阻止其餘來源繼續執行。

## 本機使用

```sh
python3 scripts/ai_news_collect.py --state state/ai_news_seen.json > /tmp/ai-news-candidates.json
python3 -m unittest discover -s tests -v
```

若已選出要推送的項目，把其 `id` 寫進 JSON，例如 `{"selected_ids": ["..."]}`，然後執行：

```sh
python3 scripts/ai_news_collect.py --mark-seen /tmp/selected-ids.json --state state/ai_news_seen.json
```

state 保留最近 14 天的已推送項目。因 Codex 的回覆交付後沒有可執行的 callback，排程會在產生最終報告前記錄已選項；若交付本身失敗，可刪除相應 state 項目讓下次重試。

## 排程

此 repo 由目前 Codex 任務的每日 08:00 HKT heartbeat 使用。排程提示會讀取 `.agents/skills/ai-news-briefing/SKILL.md`，因此品質規則不依賴模型記憶或即時瀏覽。
