---
name: tavily-search
description: "通过 Tavily API 进行网络搜索。当用户要求搜索网络 / 查找来源 / 查找链接，且没有或不希望使用 Brave web_search 时使用。返回少量相关结果（标题，URL，摘要），并可选地包含简短的答案总结。"
---

# Tavily 搜索

使用绑定的脚本通过 Tavily 进行网络搜索。

## 网络搜索执行命令

```bash
# 原始 JSON（默认）
python skills/tavily-search/scripts/tavily_search.py --query "..." --max-results 5

# 包含简短的答案总结（如果可用）
python skills/tavily-search/scripts/tavily_search.py --query "..." --max-results 5 --include-answer

# 稳定的返回结构（更接近 web_search）：{query, results:[{title,url,snippet}], answer?}
python skills/tavily-search/scripts/tavily_search.py --query "..." --max-results 5 --format brave

# 易于阅读的 Markdown 列表
python skills/tavily-search/scripts/tavily_search.py --query "..." --max-results 5 --format md
```

## 输出

### raw（默认）
- JSON: `query`，可选的 `answer`，`results: [{title,url,content}]`

### brave
- JSON: `query`，可选的 `answer`，`results: [{title,url,snippet}]`

### md
- 一个包含标题/链接/摘要的紧凑 Markdown 列表。

## 注意事项

- 默认保持较小的 `max-results`（3-5 个），以减少 Token 消耗和阅读负担。
- 优先返回 URL + 摘要；仅在必要时才抓取获取完整的网页内容。