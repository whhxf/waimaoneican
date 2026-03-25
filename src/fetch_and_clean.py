"""
步骤 2：根据 data/urls/ 中的 URL 列表，用 Playwright 直接访问并提取标题和正文（精准选择器），
去噪后按日 + 来源写入 data/markdown/YYYY-MM-DD_来源.md。

选择器规则：
- 邦阅网：标题 class="indent"，正文 class="article-content"
- 雨果网：标题 class="article-title"，正文 class="article-content article-inner leftcont"
- 米课圈：跳过（已在 fetch_urls 中保留 title，直接复用）

并发抓取：使用 asyncio + async_playwright，每来源并发 20 个页面
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from src.config import MARKDOWN_DIR, MAX_BODY_CHARS, SOURCES, URLS_DIR

# 并发配置
CONCURRENCY_PER_SOURCE = 20  # 每来源同时抓取 20 个页面
PAGE_TIMEOUT_MS = 25000
GOTO_TIMEOUT_MS = 30000

# 各站点的选择器配置
SELECTORS = {
    "52by.com": {
        "title": ".indent",
        "body": ".article-content",
    },
    "cifnews.com": {
        "title": ".article-title",
        "body": ".article-content.article-inner.leftcont, .article-content, .article-inner",
    },
}


async def _extract_with_playwright(page, url: str) -> dict:
    """用 Playwright 打开 URL，根据域名选择对应选择器提取标题和正文。"""
    domain = urlparse(url).netloc.lower()
    config = None
    for key, sel in SELECTORS.items():
        if key in domain:
            config = sel
            break

    if not config:
        return {"title": "", "body": ""}

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
        await page.wait_for_timeout(2000)

        # 提取标题
        title = ""
        try:
            title_el = page.locator(config["title"]).first
            if await title_el.is_visible(timeout=3000):
                title = (await title_el.text_content() or "").strip()[:200]
        except Exception:
            pass

        # 提取正文
        body = ""
        try:
            selectors = [s.strip() for s in config["body"].split(",")]
            for sel in selectors:
                try:
                    body_el = page.locator(sel).first
                    if await body_el.is_visible(timeout=3000):
                        body = (await body_el.text_content() or "").strip()
                        if body:
                            break
                except Exception:
                    continue
        except Exception:
            pass

        return {"title": title, "body": body}
    except Exception as e:
        print(f"  [ERR] 抓取失败 {url}: {e}")
        return {"title": "", "body": ""}


def _clean_body(raw: str) -> str:
    """简单清洗：去空行、保留完整段落。"""
    if not raw:
        return ""
    lines = raw.split("\n")
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if len(line) > 5000:
            line = line[:5000] + "\n…"
        out.append(line)
    text = "\n".join(out).strip()
    if len(text) > MAX_BODY_CHARS:
        cut_pos = MAX_BODY_CHARS
        newline_pos = text.rfind("\n", MAX_BODY_CHARS - 1000, MAX_BODY_CHARS)
        if newline_pos > 0:
            cut_pos = newline_pos
        text = text[:cut_pos] + "\n\n（内容过长，已截断）"
    return text


def _build_markdown(source_name: str, date: str, items: list[dict]) -> str:
    """生成单来源的 Markdown 文档。"""
    lines = [
        f"# {source_name} - {date}",
        "",
        f"抓取时间：{datetime.now().isoformat()}",
        f"共 {len(items)} 条",
        "",
        "---",
        "",
    ]
    for i, item in enumerate(items, 1):
        title = (item.get("title") or "无标题").replace("\n", " ")
        url = item.get("url", "")
        body = item.get("body") or ""
        fetched_at = item.get("fetched_at", datetime.now().isoformat())
        lines.append(f"## {i}. {title}")
        lines.append("")
        lines.append(f"- **链接**: [原文]({url})")
        lines.append(f"- **抓取时间**: {fetched_at}")
        lines.append("")
        lines.append("**正文**:")
        lines.append("")
        lines.append(body if body else "_（未能抓取正文）_")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


async def _fetch_single(page, item: dict, is_imiker: bool, semaphore: asyncio.Semaphore) -> dict:
    """抓取单个 URL（带信号量控制并发）。"""
    async with semaphore:
        url = item.get("url", "")
        if not url:
            item["body"] = ""
            item["fetched_at"] = datetime.now().isoformat()
            return item

        if is_imiker:
            item["body"] = item.get("title", "")
            item["fetched_at"] = datetime.now().isoformat()
            return item

        try:
            extracted = await _extract_with_playwright(page, url)
            item["title"] = extracted["title"] or item.get("title", "")
            item["body"] = _clean_body(extracted["body"])
            item["fetched_at"] = datetime.now().isoformat()
        except Exception as e:
            print(f"  [ERR] {url}: {e}")
            item["body"] = ""
            item["fetched_at"] = datetime.now().isoformat()

        return item


async def _fetch_source(browser, src: dict, date: str, test_limit: int | None = None) -> tuple[str, list[dict]]:
    """抓取单个来源的所有 URL。"""
    name = src["name"]
    path = URLS_DIR / f"{date}_{name}.json"
    if not path.exists():
        print(f"[SKIP] 未找到 URL 列表：{path}")
        return name, []

    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)
    if test_limit:
        items = items[:test_limit]

    is_imiker = "米课" in name or "imiker" in src.get("url", "").lower()

    # 创建多个页面并发抓取
    semaphore = asyncio.Semaphore(CONCURRENCY_PER_SOURCE)
    pages = [await browser.new_page() for _ in range(CONCURRENCY_PER_SOURCE)]

    try:
        tasks = [_fetch_single(pages[i % len(pages)], item, is_imiker, semaphore) for i, item in enumerate(items)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"  [ERR] {items[i].get('url', 'unknown')}: {result}")

        print(f"[OK] {name}: {len(items)} 条")
        return name, items
    finally:
        for page in pages:
            await page.close()


async def run_async(date: str | None = None, test_limit: int | None = None) -> dict[str, Path]:
    """异步版本：读取当日 URL 列表，拉正文、清洗、写 Markdown。"""
    import os

    date = date or datetime.now().strftime("%Y-%m-%d")
    URLS_DIR.mkdir(parents=True, exist_ok=True)
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    result = {}

    if test_limit is None and os.environ.get("NEICAN_TEST"):
        test_limit = int(os.environ.get("NEICAN_TEST", "0")) or None
    if test_limit:
        print(f"[TEST] 每来源仅处理前 {test_limit} 条")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            for src in SOURCES:
                name, items = await _fetch_source(browser, src, date, test_limit)
                if not items:
                    continue

                md_content = _build_markdown(name, date, items)
                out_path = MARKDOWN_DIR / f"{date}_{name}.md"
                out_path.write_text(md_content, encoding="utf-8")
                result[name] = out_path
                print(f"[OK] {name}: {len(items)} 条 -> {out_path}")
        finally:
            await browser.close()

    return result


def run(date: str | None = None, test_limit: int | None = None) -> dict[str, Path]:
    """同步入口：调用异步版本。"""
    return asyncio.run(run_async(date, test_limit))


if __name__ == "__main__":
    run()
