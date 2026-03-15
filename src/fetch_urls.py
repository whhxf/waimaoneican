"""
步骤1：抓取雨果网 50 条、邦阅网 50 条、米课圈 100 条文章 URL 列表，保存到 data/urls/YYYY-MM-DD_来源.json。
使用 Playwright 处理动态加载（滚动/加载更多）。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

from src.config import URLS_DIR, SOURCES


def _normalize_url(url: str, base: str) -> str:
    u = urljoin(base, url)
    parsed = urlparse(u)
    if not parsed.netloc:
        return ""
    return u.split("#")[0].rstrip("/")


def _is_article_url(url: str, url_contains: list[str]) -> bool:
    if not url or url.startswith("javascript:") or url.startswith("#"):
        return False
    lower = url.lower()
    return any(part in lower for part in url_contains)


def _extract_links(page, url_contains: list[str], base_url: str) -> list[dict]:
    """从当前页面提取文章链接，去重，返回 [{title, url}]。"""
    links = page.evaluate(
        """() => {
        const a = document.querySelectorAll('a[href]');
        return Array.from(a).map(el => ({
            title: (el.textContent || '').trim(),
            url: el.href || ''
        }));
    }"""
    )
    seen = set()
    out = []
    for item in links:
        title = (item.get("title") or "").strip()
        url = _normalize_url(item.get("url") or "", base_url)
        if not url or not _is_article_url(url, url_contains):
            continue
        if len(title) < 5 or url in seen:
            continue
        # 排除登录、注册、首页等
        if re.search(r"/(login|register|signin|#)$", url, re.I):
            continue
        seen.add(url)
        out.append({"title": title[:200], "url": url})
    return out


def fetch_cifnews(page, limit: int, scroll_times: int) -> list[dict]:
    """雨果网：首页文章链接，可滚动几次以加载更多。"""
    base = "https://www.cifnews.com"
    page.goto(base, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    for _ in range(scroll_times):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
    links = _extract_links(page, ["cifnews.com"], base)
    # 优先保留带 /article/ 的
    with_article = [x for x in links if "/article/" in x["url"]]
    rest = [x for x in links if x not in with_article]
    merged = with_article + rest
    return merged[:limit]


def fetch_52by(page, limit: int, load_more_text: str | None, scroll_times: int) -> list[dict]:
    """邦阅网：只保留路径为 /article/ 的文章链接，排除 author、faq、offline、tag 等；不足 50 条则继续滚动/加载更多。"""
    base = "https://www.52by.com"
    page.goto(base, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    seen = set()
    article_links = []
    max_rounds = 15
    for round_idx in range(max_rounds):
        if load_more_text:
            try:
                btn = page.get_by_text(load_more_text, exact=False).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
        links = _extract_links(page, ["52by.com"], base)
        for x in links:
            path = urlparse(x["url"]).path.lower()
            if "/article/" not in path:
                continue
            if path.startswith("/author/") or "/faq/" in path or "/offline/" in path or "/tag/" in path or "/vip" in path:
                continue
            if x["url"] in seen:
                continue
            seen.add(x["url"])
            article_links.append(x)
        if len(article_links) >= limit:
            break
    return article_links[:limit]


def _extract_imiker_questions(page, base: str) -> list[dict]:
    """
    从米课圈页面源码中提取 onclick="window.open('/question/xxx')" 中的路径，
    同时提取邻近 p 标签里的文本作为 title，拼接完整 URL。
    """
    html = page.content()
    # 匹配完整的 onclick 片段，同时捕获路径和邻近文本
    # 例：<p onclick="window.open('/question/946383')" class="ellipsis">😄😄菠萝炒饭</p>
    pattern = r'<p[^>]*onclick=["\']window\.open\(["\'&quot;]*(/question/\d+)["\'&quot;]*\)["\'][^>]*>([^<]+)</p>'
    matches = re.findall(pattern, html)
    seen = set()
    out = []
    for path, title in matches:
        url = urljoin(base, path)
        if url in seen:
            continue
        seen.add(url)
        clean_title = title.strip()[:200] if title else ""
        out.append({"title": clean_title, "url": url})
    return out


def fetch_imiker(page, limit: int, scroll_times: int) -> list[dict]:
    """米课圈：从源码 onclick 提取 /question/ 路径，拼接完整 URL，滚动直到凑够 limit 条。"""
    base = "https://ask.imiker.com"
    page.goto("https://ask.imiker.com/explore/find/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    seen = set()
    question_links = []
    for _ in range(scroll_times):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
        items = _extract_imiker_questions(page, base)
        for x in items:
            if x["url"] in seen:
                continue
            seen.add(x["url"])
            question_links.append(x)
        if len(question_links) >= limit:
            break
    return question_links[:limit]


def run(date: str | None = None) -> dict[str, list[dict]]:
    """抓取所有来源，返回 {来源名: [{title, url}, ...]}。"""
    date = date or datetime.now().strftime("%Y-%m-%d")
    URLS_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for src in SOURCES:
                name = src["name"]
                limit = src["limit"]
                url_contains = src.get("url_contains", [])
                scroll_times = src.get("scroll_times", 2)
                load_more_text = src.get("load_more_text")

                page = browser.new_page()
                page.set_default_timeout(25000)
                try:
                    if "雨果" in name or "cifnews" in src["url"]:
                        items = fetch_cifnews(page, limit, scroll_times)
                    elif "邦阅" in name or "52by" in src["url"]:
                        items = fetch_52by(page, limit, load_more_text, scroll_times)
                    else:
                        items = fetch_imiker(page, limit, scroll_times)
                finally:
                    page.close()

                results[name] = items
                path = URLS_DIR / f"{date}_{name}.json"
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(items, f, ensure_ascii=False, indent=2)
                print(f"[OK] {name}: {len(items)} 条 -> {path}")
        finally:
            browser.close()

    return results


if __name__ == "__main__":
    run()
