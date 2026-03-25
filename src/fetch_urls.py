"""
步骤1：抓取雨果网 30 条、邦阅网 30 条、米课圈 140 条文章 URL 列表，保存到 data/urls/YYYY-MM-DD_来源.json。
使用 Playwright 处理动态加载（滚动/加载更多）。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
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


def _strip_tracking_params(url: str) -> str:
    """去除 URL 追踪参数（如 ?origin=yggw_pc_ptqb_N），返回规范化 URL。"""
    if "?" not in url:
        return url
    base = url.split("?")[0]
    return base


def _has_timestamp(title: str) -> bool:
    """检查标题是否包含时间戳（动态内容特征）。"""
    import re
    # 匹配：昨天 XX:XX、X 天前 XX:XX、YYYY-MM-DD、MM 月 DD 日、MM/DD 等
    patterns = [
        r'昨天\s*\d{1,2}:\d{2}',           # 昨天17:17 或 昨天 17:17
        r'\d+\s*天前\s*\d{1,2}:\d{2}',     # 5 天前17:36 或 5 天前 17:36
        r'\d{4}-\d{2}-\d{2}',              # 2026-03-17
        r'\d{2}月\d{2}日',                  # 03 月 17 日
        r'\d{1,2}/\d{1,2}',                # 8/12 生效
        r'\d{2}\.\d{2}',                   # 03.27
    ]
    for p in patterns:
        if re.search(p, title):
            return True
    return False


def _parse_days_ago(title: str) -> int | None:
    """从标题解析文章是几天前发布的，返回天数（整数）。无法解析返回 None。"""
    # X 小时前 = 0 天
    if re.search(r'\d+\s*小时前', title):
        return 0
    # 昨天 = 1 天前
    if re.search(r'昨天\s*\d{1,2}:\d{2}', title):
        return 1
    # X 天前
    m = re.search(r'(\d+)\s*天前\s*\d{1,2}:\d{2}', title)
    if m:
        return int(m.group(1))
    # YYYY-MM-DD（计算与今天的天数差）
    m = re.search(r'(\d{4}-\d{2}-\d{2})', title)
    if m:
        try:
            article_date = datetime.strptime(m.group(1), "%Y-%m-%d")
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            delta = (today - article_date).days
            return max(0, delta)
        except ValueError:
            pass
    return None


def _extract_publish_date(title: str) -> str | None:
    """从标题提取文章发布日期，返回 YYYY-MM-DD 格式。无法解析返回 None。"""
    from datetime import timedelta
    
    # 昨天 XX:XX
    if re.search(r'昨天\s*\d{1,2}:\d{2}', title):
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # X 天前 XX:XX
    m = re.search(r'(\d+)\s*天前\s*\d{1,2}:\d{2}', title)
    if m:
        days = int(m.group(1))
        return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # YYYY-MM-DD
    m = re.search(r'(\d{4}-\d{2}-\d{2})', title)
    if m:
        return m.group(1)
    
    return None


def _fetch_cifnews_publish_date(page, url: str) -> str | None:
    """访问雨果网文章页面，从 class='date' 元素提取发布时间。"""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)
        
        pub_date = page.evaluate('''() => {
            const el = document.querySelector('.cif-article__binfo .date, .date');
            if (el) {
                const text = (el.textContent || '').trim();
                // 匹配 YYYY-MM-DD HH:mm 格式
                const match = text.match(/(\\d{4}-\\d{2}-\\d{2})/);
                if (match) {
                    return match[1];
                }
            }
            return null;
        }''')
        
        return pub_date
    except Exception as e:
        print(f"  [WARN] 提取发布日期失败 {url}: {e}")
        return None


def fetch_cifnews(page, limit: int, scroll_times: int, recent_days: int = 2, max_days: int = 7) -> list[dict]:
    """雨果网：首页文章链接，滚动加载更多，抓取最近的文章。
    
    策略：
    - 优先抓取最近 recent_days 天的文章（默认 2 天）
    - 如果不足 limit 条，放宽到 max_days 天（默认 7 天）
    - 如果 max_days 天内仍不足 limit 条，返回实际数量（不继续放宽）
    - 最多返回 limit 条（默认 30 条）
    - 去除 ?origin= 追踪参数避免重复
    - 按发布时间从新到旧排序
    """
    from datetime import timedelta
    
    base = "https://www.cifnews.com"
    page.goto(base, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    
    # 增加滚动次数：从 2 次改为 5 次，确保加载足够多的动态内容
    effective_scroll_times = max(scroll_times, 5)
    for i in range(effective_scroll_times):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
    
    # 提取文章列表，同时提取时间信息
    print("  正在提取文章列表和时间信息...")
    items = page.evaluate("""() => {
        const results = [];
        const articleLinks = document.querySelectorAll('a[href*="/article/"]');
        
        articleLinks.forEach(a => {
            const title = (a.textContent || '').trim();
            const url = a.href || '';
            
            if (title.length < 5 || !url) return;
            
            // 找父容器中的时间信息（作者 · 时间格式）
            let timeText = '';
            let parent = a.parentElement;
            
            for (let i = 0; i < 5 && parent; i++) {
                const metaEl = parent.querySelector('[class*="meta"], [class*="info"], [class*="binfo"]');
                if (metaEl) {
                    const text = (metaEl.textContent || '').trim();
                    const parts = text.split('·');
                    if (parts.length >= 2) {
                        timeText = parts[parts.length - 1].trim();
                    }
                    if (timeText) break;
                }
                
                const timeEl = parent.querySelector('[class*="time"], .date');
                if (timeEl) {
                    timeText = (timeEl.textContent || '').trim();
                    if (timeText) break;
                }
                
                parent = parent.parentElement;
            }
            
            results.push({
                title: title,
                url: url,
                timeText: timeText.replace(/\\n/g, ' ').replace(/\\s+/g, ' ').trim()
            });
        });
        
        return results;
    }""")
    
    # 规范化 URL：去除追踪参数
    for item in items:
        item["url"] = _strip_tracking_params(item["url"])
    
    # 去重
    seen = set()
    unique_links = []
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique_links.append(item)
    
    # 只保留带 /article/ 的文章
    with_article = [x for x in unique_links if "/article/" in x["url"]]
    print(f"  首页共 {len(with_article)} 条唯一文章")
    
    # 计算日期阈值
    cutoff_date_2days = (datetime.now() - timedelta(days=recent_days)).strftime("%Y-%m-%d")
    cutoff_date_7days = (datetime.now() - timedelta(days=max_days)).strftime("%Y-%m-%d")
    
    # 辅助函数：从时间文本解析天数
    def get_days_ago_from_time(time_str: str) -> float | None:
        if not time_str:
            return None
        # 先提取时间部分（去掉后面的标签）
        # 例如："3 小时前 亚马逊 欧盟 欧洲" → "3 小时前"
        time_part = time_str.split()[0] if time_str else ""
        
        # X 小时前（今天）
        m = re.search(r'(\d+)\s*小时前', time_part)
        if m:
            return int(m.group(1)) / 24.0
        
        # 昨天 XX:XX（只有在标题中也有"昨天"时才可信）
        # 因为首页显示的"昨天 17:17"可能是作者最后更新时间，不是文章发布日期
        if re.search(r'昨天\s*\d{1,2}:\d{2}', time_part):
            # 检查标题中是否也包含"昨天"
            if "昨天" in time_str:
                return 1.0
            # 否则不信任这个时间，返回 None
            return None
        
        # X 天前 XX:XX
        m = re.search(r'(\d+)\s*天前\s*\d{1,2}:\d{2}', time_part)
        if m:
            return float(m.group(1))
        
        # YYYY-MM-DD
        m = re.search(r'(\d{4}-\d{2}-\d{2})', time_part)
        if m:
            try:
                article_date = datetime.strptime(m.group(1), "%Y-%m-%d")
                return (datetime.now() - article_date).days
            except ValueError:
                pass
        return None
    
    # 解析每篇文章的时间
    for item in with_article:
        time_str = item.get("timeText", "")
        if not time_str:
            time_str = item["title"]
        days_ago = get_days_ago_from_time(time_str)
        if days_ago is not None:
            item["_days_ago"] = days_ago
            item["_pub_date"] = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    
    # 统计
    with_time = [x for x in with_article if x.get("_days_ago") is not None]
    print(f"  解析到时间信息：{len(with_time)} 条")
    
    # 第一步：只保留最近 2 天的文章
    # 优先使用从页面提取的 publish_date，其次使用从时间文本推算的日期
    cutoff_date = (datetime.now() - timedelta(days=recent_days)).strftime("%Y-%m-%d")
    recent_2days = []
    for item in with_article:
        pub_date = item.get("publish_date") or item.get("_pub_date")
        if pub_date and pub_date >= cutoff_date:
            recent_2days.append(item)
    print(f"  最近 {recent_days} 天：{len(recent_2days)} 条")
    
    if len(recent_2days) >= limit:
        print(f"  ✅ 最近 2 天已足够 {limit} 条")
        recent_2days.sort(key=lambda x: x["_days_ago"])
        for item in recent_2days:
            del item["_pub_date"]
            del item["_days_ago"]
        return recent_2days[:limit]
    
    # 第二步：不足 30 条，放宽到 7 天
    print(f"  ⚠️  最近 2 天不足 {limit} 条，放宽到 {max_days} 天...")
    
    cutoff_date_7days = (datetime.now() - timedelta(days=max_days)).strftime("%Y-%m-%d")
    recent_7days = []
    for item in with_article:
        pub_date = item.get("publish_date") or item.get("_pub_date")
        if pub_date and pub_date >= cutoff_date_7days:
            recent_7days.append(item)
    print(f"  最近 {max_days} 天：{len(recent_7days)} 条")
    
    # 按发布时间从新到旧排序
    recent_7days.sort(key=lambda x: x["_days_ago"])
    
    # 移除临时字段
    for item in recent_7days:
        del item["_pub_date"]
        del item["_days_ago"]
    
    # 返回 7 天内的文章，最多 limit 条（不足则返回实际数量）
    return recent_7days[:limit]


def fetch_52by(page, limit: int, load_more_text: str | None, scroll_times: int) -> list[dict]:
    """邦阅网：只保留路径为 /article/ 的文章链接。"""
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
    # 添加空的 publish_date
    for item in article_links:
        item["publish_date"] = None
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
                        # 雨果网：对于相对时间（X 小时前/昨天/X 天前）使用计算日期，其他从页面提取
                        print(f"  正在处理 {len(items)} 篇文章的发布日期...")
                        for i, item in enumerate(items):
                            time_text = item.get("timeText", "")
                            # 检查是否是相对时间（X 小时前、昨天、X 天前）
                            is_relative = bool(re.search(r'\d+\s*小时前|\d+\s*天前\s*\d{1,2}:\d{2}|昨天\s*\d{1,2}:\d{2}', time_text))
                            
                            if is_relative:
                                # 相对时间：从 timeText 计算日期
                                days_ago = _parse_days_ago(time_text)
                                if days_ago is not None:
                                    item["publish_date"] = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                                else:
                                    # 如果解析失败，尝试从标题解析
                                    item["publish_date"] = _extract_publish_date(item["title"])
                            else:
                                # 绝对时间（YYYY-MM-DD）：从页面提取或标题解析
                                pub_date = _fetch_cifnews_publish_date(page, item["url"])
                                if pub_date:
                                    item["publish_date"] = pub_date
                                else:
                                    item["publish_date"] = _extract_publish_date(item["title"])
                            
                            if (i + 1) % 10 == 0:
                                print(f"    已处理 {i+1}/{len(items)} 条")
                    elif "邦阅" in name or "52by" in src["url"]:
                        items = fetch_52by(page, limit, load_more_text, scroll_times)
                        # 邦阅网：从标题解析（首页不显示日期）
                        for item in items:
                            item["publish_date"] = _extract_publish_date(item["title"])
                    else:
                        items = fetch_imiker(page, limit, scroll_times)
                        # 米课圈：从标题解析（首页不显示日期）
                        for item in items:
                            item["publish_date"] = _extract_publish_date(item["title"])
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
