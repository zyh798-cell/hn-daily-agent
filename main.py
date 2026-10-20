#!/usr/bin/env python3
"""Daily Hacker News AI digest generator.

Uses the public Hacker News Firebase API. An OpenAI-compatible model API is optional:
without credentials, the script still creates a useful digest using titles and metadata.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

HN_BASE = "https://hacker-news.firebaseio.com/v0"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
MAX_STORIES = int(os.getenv("MAX_STORIES", "200"))
DIGEST_LIMIT = int(os.getenv("DIGEST_LIMIT", "10"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "large language model", "language model", "gpt", "claude",
    "openai", "anthropic", "deepseek", "gemini", "agent", "agents",
    "inference", "neural network", "transformer", "rag", "embedding",
    "computer vision", "speech model", "generative", "diffusion model",
    "ai coding", "coding assistant", "model training", "hugging face",
]
AI_RE = re.compile(r"\b(?:" + "|".join(re.escape(x) for x in sorted(AI_KEYWORDS, key=len, reverse=True)) + r")\b", re.I)


def fetch_json(url: str) -> Any:
    request = Request(url, headers={"User-Agent": "hn-daily-agent/0.1 (personal learning project)"})
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_story(story_id: int) -> dict[str, Any] | None:
    try:
        item = fetch_json(f"{HN_BASE}/item/{story_id}.json")
        if not isinstance(item, dict) or item.get("type") != "story" or item.get("dead") or item.get("deleted"):
            return None
        return item
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"[WARN] Could not fetch story {story_id}: {exc}", file=sys.stderr)
        return None


def is_ai_related(story: dict[str, Any]) -> bool:
    text = f"{story.get('title', '')} {story.get('text', '')} {story.get('url', '')}"
    return bool(AI_RE.search(text))


def safe_url(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} else ""


def get_stories() -> list[dict[str, Any]]:
    ids = fetch_json(f"{HN_BASE}/topstories.json")
    if not isinstance(ids, list):
        raise RuntimeError("Hacker News API did not return a list of story IDs.")
    stories: list[dict[str, Any]] = []
    for index, story_id in enumerate(ids[:MAX_STORIES], start=1):
        item = fetch_story(int(story_id))
        if item and is_ai_related(item):
            item["url"] = safe_url(item.get("url"))
            stories.append(item)
        if index % 25 == 0:
            print(f"[INFO] Checked {index}/{min(len(ids), MAX_STORIES)} stories; AI-related: {len(stories)}")
        # Keep API traffic polite; GitHub Actions runs this once daily.
        time.sleep(0.05)
    stories.sort(key=lambda x: (int(x.get("score", 0)), int(x.get("time", 0))), reverse=True)
    return stories[:DIGEST_LIMIT]


def call_llm(stories: list[dict[str, Any]]) -> list[dict[str, str]] | None:
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        print("[INFO] LLM_API_KEY is not set; using metadata-only summaries.")
        return None

    endpoint = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    prompt_items = [
        {
            "title": s.get("title", ""),
            "url": s.get("url", ""),
            "score": s.get("score", 0),
            "comments": s.get("descendants", 0),
            "hn_url": f"https://news.ycombinator.com/item?id={s.get('id')}",
            "text": re.sub(r"<[^>]+>", " ", s.get("text", ""))[:1500],
        }
        for s in stories
    ]
    system = (
        "你是技术情报编辑。根据给定的 Hacker News 条目生成中文简报。"
        "只能依据提供的标题、链接、分数和文本，不要编造文章内容。"
        "如果信息不足，请明确说标题层面判断。输出严格 JSON 数组，每项包含 "
        "title_zh、summary_zh、why_follow、difficulty（入门/中等/进阶）。"
        "不要输出 Markdown 代码围栏。"
    )
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(prompt_items, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
    }
    # Some OpenAI-compatible providers require a JSON object rather than a bare array.
    body["messages"][0]["content"] += " 请将结果放在名为 items 的 JSON 数组字段中。"
    request = Request(
        f"{endpoint}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        items = parsed.get("items", parsed if isinstance(parsed, list) else [])
        if not isinstance(items, list):
            raise ValueError("LLM response did not contain an items array.")
        normalized = []
        for i, item in enumerate(items[:len(stories)]):
            if isinstance(item, dict):
                normalized.append({
                    "title_zh": str(item.get("title_zh") or stories[i].get("title", "")),
                    "summary_zh": str(item.get("summary_zh") or "暂未生成摘要。"),
                    "why_follow": str(item.get("why_follow") or "可根据原文进一步判断。"),
                    "difficulty": str(item.get("difficulty") or "中等"),
                })
        if len(normalized) == len(stories):
            return normalized
        print("[WARN] LLM returned an incomplete list; falling back to metadata-only summaries.")
    except Exception as exc:
        print(f"[WARN] LLM request failed; falling back to metadata-only summaries: {exc}", file=sys.stderr)
    return None


def build_records(stories: list[dict[str, Any]], llm_items: list[dict[str, str]] | None) -> list[dict[str, Any]]:
    records = []
    for index, story in enumerate(stories):
        enrichment = llm_items[index] if llm_items and index < len(llm_items) else {}
        title = story.get("title", "(untitled)")
        hn_url = f"https://news.ycombinator.com/item?id={story.get('id')}"
        records.append({
            "rank": index + 1,
            "title": title,
            "title_zh": enrichment.get("title_zh", title),
            "summary_zh": enrichment.get("summary_zh", f"当前为标题与社区数据摘要：{title}。建议打开原文核实具体内容。"),
            "why_follow": enrichment.get("why_follow", "该条目命中了 AI 相关关键词，可作为技术趋势线索；请阅读原文后再判断价值。"),
            "difficulty": enrichment.get("difficulty", "中等"),
            "score": int(story.get("score", 0)),
            "comments": int(story.get("descendants", 0)),
            "url": story.get("url", ""),
            "hacker_news_url": hn_url,
            "published_at": datetime.fromtimestamp(int(story.get("time", 0)), tz=timezone.utc).isoformat() if story.get("time") else None,
        })
    return records


def write_outputs(records: list[dict[str, Any]]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    date_str = now.strftime("%Y-%m-%d")
    md_path = OUTPUT_DIR / f"digest-{date_str}.md"
    json_path = OUTPUT_DIR / f"digest-{date_str}.json"

    lines = [
        f"# Hacker News 每日 AI 简报 — {date_str}",
        "",
        f"> 生成时间：{now.isoformat()}  ",
        f"> 数据来源：Hacker News 官方 Firebase API；共整理 {len(records)} 条。  ",
        "> 说明：关键词筛选可能漏掉或误判内容；摘要仅供快速浏览，请以原文为准。",
        "",
    ]
    if not records:
        lines += ["今天没有筛选到符合关键词的条目。", ""]
    for record in records:
        lines += [
            f"## {record['rank']}. {record['title_zh']}",
            "",
            f"- **原始标题：** {record['title']}",
            f"- **热度：** {record['score']} points · **评论：** {record['comments']}",
            f"- **难度：** {record['difficulty']}",
            f"- **关注理由：** {record['why_follow']}",
            f"- **摘要：** {record['summary_zh']}",
            f"- **原文：** {record['url'] or '无外部链接'}",
            f"- **HN 讨论：** {record['hacker_news_url']}",
            "",
        ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps({
        "generated_at": now.isoformat(),
        "source": "Hacker News Firebase API",
        "count": len(records),
        "items": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path


def main() -> int:
    try:
        print("[INFO] Fetching Hacker News top stories...")
        stories = get_stories()
        print(f"[INFO] Selected {len(stories)} AI-related stories.")
        llm_items = call_llm(stories) if stories else None
        records = build_records(stories, llm_items)
        md_path, json_path = write_outputs(records)
        print(f"[OK] Markdown digest: {md_path}")
        print(f"[OK] JSON data: {json_path}")
        return 0
    except Exception as exc:
        print(f"[ERROR] Digest generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
