"""
步骤2：根据 data/urls/ 中的 URL 列表，用 Playwright 直接访问并提取标题和正文（精准选择器），
去噪后按日+来源写入 data/markdown/YYYY-MM-DD_来源.md。

选择器规则：
- 邦阅网：标题 class="indent"，正文 class="article-content"
- 雨果网：标题 class="article-title"，正文 class="article-content article-inner leftcont"
- 米课圈：跳过（已在 fetch_urls 中保留 title，直接复用）
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from src.config import MARKDOWN_DIR, MAX_BODY_CHARS, SOURCES, URLS_DIR


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


def _extract_with_playwright(page, url: str) -> dict:
    """用 Playwright 打开 URL，根据域名选择对应选择器提取标题和正文。"""
    domain = urlparse(url).netloc.lower()
    # 匹配选择器配置
    config = None
    for key, sel in SELECTORS.items():
        if key in domain:
            config = sel
            break

    if not config:
        # 无配置则返回空
        return {"title": "", "body": ""}

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # 提取标题
        title = ""
        try:
            title_el = page.locator(config["title"]).first
            if title_el.is_visible(timeout=3000):
                title = (title_el.text_content() or "").strip()[:200]
        except Exception:
            pass

        # 提取正文
        body = ""
        try:
            # 尝试多个可能的选择器（逗号分隔）
            selectors = [s.strip() for s in config["body"].split(",")]
            for sel in selectors:
                try:
                    body_el = page.locator(sel).first
                    if body_el.is_visible(timeout=3000):
                        body = (body_el.text_content() or "").strip()
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
    """简单清洗：去空行、截断。"""
    if not raw:
        return ""
    lines = raw.split("\n")
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if len(line) > 1200:
            line = line[:1200] + "\n…"
        out.append(line)
    text = "\n".join(out).strip()
    if len(text) > MAX_BODY_CHARS:
        text = text[:MAX_BODY_CHARS] + "\n\n…"
    return text


def _build_markdown(source_name: str, date: str, items: list[dict]) -> str:
    """生成单来源的 Markdown 文档。"""
    lines = [
        f"# {source_name} - {date}",
        "",
        f"抓取时间: {datetime.now().isoformat()}",
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


def run(date: str | None = None, test_limit: int | None = None) -> dict[str, Path]:
    """读取当日 URL 列表，拉正文、清洗、写 Markdown。返回 {来源名: 文件路径}。
    test_limit: 若设置，每来源只处理前 N 条（用于快速自测）。
    """
    import os

    date = date or datetime.now().strftime("%Y-%m-%d")
    URLS_DIR.mkdir(parents=True, exist_ok=True)
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    result = {}
    if test_limit is None and os.environ.get("NEICAN_TEST"):
        test_limit = int(os.environ.get("NEICAN_TEST", "0")) or None
    if test_limit:
        print(f"[TEST] 每来源仅处理前 {test_limit} 条")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for src in SOURCES:
                name = src["name"]
                path = URLS_DIR / f"{date}_{name}.json"
                if not path.exists():
                    print(f"[SKIP] 未找到 URL 列表: {path}")
                    continue

                with open(path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                if test_limit:
                    items = items[:test_limit]

                # 米课圈特殊处理：直接用已有的 title，不抓正文
                is_imiker = "米课" in name or "imiker" in src.get("url", "").lower()

                for i, item in enumerate(items):
                    url = item.get("url", "")
                    if not url:
                        item["body"] = ""
                        item["fetched_at"] = datetime.now().isoformat()
                        continue

                    if is_imiker:
                        # 米课圈：title 已在 fetch_urls 时提取，直接复用，正文留空
                        item["body"] = item.get("title", "")
                        item["fetched_at"] = datetime.now().isoformat()
                        if (i + 1) % 10 == 0:
                            print(f"  {name} 已处理 {i + 1}/{len(items)}")
                    else:
                        # 邦阅网、雨果网：Playwright 抓取
                        page = browser.new_page()
                        page.set_default_timeout(25000)
                        try:
                            extracted = _extract_with_playwright(page, url)
                            item["title"] = extracted["title"] or item.get("title", "")
                            item["body"] = _clean_body(extracted["body"])
                            item["fetched_at"] = datetime.now().isoformat()
                        finally:
                            page.close()
                        if (i + 1) % 10 == 0:
                            print(f"  {name} 已拉取 {i + 1}/{len(items)}")

                md_content = _build_markdown(name, date, items)
                out_path = MARKDOWN_DIR / f"{date}_{name}.md"
                out_path.write_text(md_content, encoding="utf-8")
                result[name] = out_path
                print(f"[OK] {name}: {len(items)} 条 -> {out_path}")
        finally:
            browser.close()

    return result


if __name__ == "__main__":
    run()
