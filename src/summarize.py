"""
步骤3：合并当日三份 Markdown 素材，单次调用环境大模型 API，输出带 source_urls 的 JSON，
并渲染为 HTML 日报到 output/reports/neican-YYYY-MM-DD.html。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from src.config import MARKDOWN_DIR, REPORTS_DIR, SOURCES

load_dotenv(Path(__file__).resolve().parent.parent / "config.env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SYSTEM_PROMPT = """你是资深外贸行业分析师和用户研究专家。我将输入今日从【雨果网、邦阅网、米课圈】抓取并清洗后的文章/帖子正文（已按来源分块，仅含标题、链接、正文，无页头页脚）。

你的任务是输出一份外贸人同理心日报分析报告。请严格按以下要求输出：

1. 仅输出一个合法 JSON 对象，不要输出任何 markdown 代码块包裹或前后废话。
2. JSON 结构必须与约定一致：overall_mood, top_3_pain_points, core_news_impact, workflow_insights, raw_quotes。
3. 每一条结论都必须有 source_urls：从输入正文中出现的【原文链接】里选取与该条结论最相关的 1～3 个 URL，填在对应条目的 source_urls 数组中。若输入里没有合适链接则用空数组 []。

各模块详细要求：

【overall_mood - 今日情绪晴雨表】
- word: 用一个词概括今日外贸人整体情绪（如：焦虑、愤怒、平淡、兴奋、喜悦）
- reason: 用约 50 字说明原因，基于当日 UGC/新闻中的情绪倾向
- source_urls: 支撑该判断的 1～3 条原文链接

【top_3_pain_points - 高频吐槽与痛点雷达】
- 从抱怨/求助/愤怒类内容中聚类出 top 3 痛点，按提及/强度排序
- 每条包含：
  - name: 痛点名称（简短有力，如"开发信退信危机"）
  - scene: 业务员在急什么（具体场景描述，引用原话更好）
  - product_idea: 产品思考（若有产品能解决该痛点，它应该长什么样）
  - source_urls: 相关原文链接数组

【core_news_impact - 今日行业地震带】
- 从雨果、邦阅等硬核资讯中提炼 2 条最重要政策/新闻
- 每条包含：
  - title: 新闻标题（一句话概括）
  - impact_type: 影响类型，只能是 cost（多花钱）、time（多花时间）、opportunity（新机会）三者之一
  - interpretation: 对外贸业务的具体影响解读
  - source_urls: 对应原文链接

【workflow_insights - 搞钱与成单拆解】
- 从米课圈等经验帖中提取 2 个 workflow insights
- 每条包含：
  - title: 案例标题（如"用 LinkedIn 拿下大客户"）
  - detail: 做法描述（具体步骤、破局点）
  - tools: 使用的工具/渠道（如"CRM系统、报价工具"）
  - source_urls: 相关原文链接

【raw_quotes - 原汁原味的呐喊】
- 挑选 3 句最能体现外贸人真实情感、最鲜活的原话
- 每条包含：
  - text: 用户原话，必须来自输入内容，尽量一字不改
  - source_label: 来源简述，如"米课圈 @某某"或"邦阅网"
  - source_urls: 该条金句所在原文链接

输出示例参考：
- overall_mood.reason 示例：红海危机导致欧洲航线海运费再次跳涨，大量业务员面临客户拒付运费、货物压港的窘境。
- pain_points.scene 示例：最近谷歌邮箱是不是又封控了？发出去的邮件全进垃圾箱，一个询盘都没有，老板还在催KPI，快疯了。
- raw_quotes.text 示例：干外贸3年，落下一身颈椎病，今天终于出了个5万美金的柜子，提成够付首付了，想哭！
"""


def _merge_markdown(date: str) -> str:
    """读取当日三份 Markdown，合并为一份带分隔的文本。"""
    parts = []
    for src in SOURCES:
        name = src["name"]
        path = MARKDOWN_DIR / f"{date}_{name}.md"
        if path.exists():
            parts.append(f"\n\n## 来源：{name}\n\n{path.read_text(encoding='utf-8')}\n\n")
        else:
            parts.append(f"\n\n## 来源：{name}\n\n（本日无数据）\n\n")
    return "\n---\n".join(parts)


def _call_llm(merged: str) -> dict:
    """调用环境配置的大模型，返回解析后的 JSON。"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("未设置 OPENAI_API_KEY，请在 config.env 或环境中配置")
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    model = os.environ.get("OPENAI_MODEL", "qwen3.5-plus")

    client = OpenAI(api_key=api_key, base_url=base_url)

    # 阿里云通义千问 qwen3.5-plus 支持 1M tokens 上下文
    # 中文环境下 1 token ≈ 1.5 字符，1M tokens ≈ 1,500,000 字符
    # 预留 50K 字符给 system prompt 和输出响应，输入限制在 1,450,000 字符
    # 当前设置足够容纳约 3 倍于日常抓取量的数据
    MAX_INPUT_CHARS = 1_450_000

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "请根据以下今日抓取的外贸内容，输出一份符合约定结构的 JSON 分析报告。\n\n" + merged[:MAX_INPUT_CHARS]},
        ],
        temperature=0.3,
    )
    text = (resp.choices[0].message.content or "").strip()
    # 去掉可能的 markdown 代码块
    if "```json" in text:
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    if "```" in text:
        text = re.sub(r"^```[^\n]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text)


def _ensure_sources(data: dict) -> None:
    """为各条目补全 source_urls（若无则设 []）。"""
    if "overall_mood" in data and isinstance(data["overall_mood"], dict):
        data["overall_mood"].setdefault("source_urls", [])
    for key in ("top_3_pain_points", "core_news_impact", "workflow_insights", "raw_quotes"):
        for item in data.get(key) or []:
            if isinstance(item, dict):
                item.setdefault("source_urls", [])


def _render_html(date: str, data: dict) -> str:
    """根据 JSON 渲染五大模块 HTML - 全新视觉设计：数字时代的外贸情报简报。"""
    mood = data.get("overall_mood") or {}
    mood_word = mood.get("word", "—")
    mood_reason = mood.get("reason", "")
    mood_urls = mood.get("source_urls") or []

    pain_points = data.get("top_3_pain_points") or []
    news = data.get("core_news_impact") or []
    workflows = data.get("workflow_insights") or []
    quotes = data.get("raw_quotes") or []

    def _source_links(urls):
        if not urls:
            return ""
        links = " · ".join(f'<a href="{u}" target="_blank" rel="noopener">→</a>' for u in urls[:2])
        return f'<span class="source-links">{links}</span>'

    mood_sources = _source_links(mood_urls)

    # 情绪颜色映射 - 更有张力的配色
    mood_colors = {
        "焦虑": "#c0392b",  # 深砖红
        "愤怒": "#8e44ad",  # 深紫
        "喜悦": "#d4a373",  # 琥珀金
        "平静": "#5d6d7e",  # 灰蓝
        "兴奋": "#e67e22",  # 橙色
    }
    mood_color = mood_colors.get(mood_word, "#1a1a2e")

    pain_cards = ""
    for i, p in enumerate(pain_points[:3], 1):
        urls = p.get("source_urls") or []
        pain_cards += f"""
        <article class="pain-card">
            <div class="card-meta">痛点 {i:02d}</div>
            <h3 class="pain-title">{p.get("name", "")}</h3>
            <p class="pain-scene">{p.get("scene", "")}</p>
            <div class="pain-product">
                <strong>产品思考</strong><br>
                {p.get("product_idea", "")}
            </div>
            <footer class="card-footer">
                来源：{_source_links(urls)}
            </footer>
        </article>"""

    news_cards = ""
    for n in news[:3]:
        urls = n.get("source_urls") or []
        url = urls[0] if urls else "#"
        it = n.get("impact_type", "time")
        # 更 subtle 的标签样式
        tag_class = f"tag-{it}"
        tag_text = {"cost": "成本上升", "time": "时间增加", "opportunity": "机遇"}.get(it, "影响")
        news_cards += f"""
        <article class="news-card">
            <div class="news-header">
                <span class="impact-tag {tag_class}">{tag_text}</span>
                <span class="news-date">{date}</span>
            </div>
            <h3 class="news-title">
                <a href="{url}" target="_blank" rel="noopener">{n.get("title", "")}</a>
            </h3>
            <p class="news-interpretation">{n.get("interpretation", "")}</p>
            <footer class="card-footer">
                全文：{_source_links(urls)}
            </footer>
        </article>"""

    workflow_cards = ""
    for i, w in enumerate(workflows[:3], 1):
        urls = w.get("source_urls") or []
        workflow_cards += f"""
        <article class="workflow-card">
            <div class="card-meta">案例 {i:02d}</div>
            <h3 class="workflow-title">{w.get("title", "")}</h3>
            <p class="workflow-detail">{w.get("detail", "")}</p>
            <div class="workflow-tools">
                <span class="tools-label">工具</span>
                {w.get("tools", "")}
            </div>
            <footer class="card-footer">
                来源：{_source_links(urls)}
            </footer>
        </article>"""

    quote_cards = ""
    for i, q in enumerate(quotes[:5], 1):
        urls = q.get("source_urls") or []
        # 金句特殊样式 - 像收集的便签
        rotation = ["-1deg", "1deg", "-0.5deg", "0.5deg", "0deg"][i % 5]
        quote_cards += f"""
        <article class="quote-card" style="transform: rotate({rotation});">
            <blockquote class="quote-text">{q.get("text", "")}</blockquote>
            <footer class="quote-footer">
                <span class="quote-source-label">{q.get("source_label", "")}</span>
                {_source_links(urls)}
            </footer>
        </article>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>外贸内参 · {date}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Playfair+Display:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --color-bg: #faf9f7;
            --color-paper: #ffffff;
            --color-ink: #1a1a2e;
            --color-ink-light: #5d6d7e;
            --color-accent: #d4a373;
            --color-accent-dark: #b8935f;
            --color-pain: #c0392b;
            --color-news: #5d6d7e;
            --color-workflow: #2c3e50;
            --color-quote: #f4f1ea;
            --border-light: #e8e4de;
            --border-medium: #d4cfc7;
            --shadow-subtle: 0 1px 3px rgba(0,0,0,0.04);
            --shadow-card: 0 2px 8px rgba(0,0,0,0.08);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Noto Serif SC', 'Songti SC', Georgia, serif;
            line-height: 1.75;
            color: var(--color-ink);
            background: var(--color-bg);
            font-size: 15px;
        }}

        .container {{
            max-width: 720px;
            margin: 0 auto;
            padding: 60px 24px;
        }}

        /* Header - 报纸头风格 */
        .masthead {{
            text-align: center;
            padding-bottom: 32px;
            border-bottom: 3px double var(--color-ink);
            margin-bottom: 48px;
        }}

        .masthead::before {{
            content: '';
            display: block;
            height: 4px;
            background: linear-gradient(90deg, var(--color-ink) 0%, var(--color-accent) 50%, var(--color-ink) 100%);
            margin: -60px -24px 40px -24px;
        }}

        .publication-title {{
            font-family: 'Playfair Display', 'Noto Serif SC', serif;
            font-size: 42px;
            font-weight: 700;
            letter-spacing: 8px;
            color: var(--color-ink);
            margin-bottom: 8px;
            text-transform: uppercase;
        }}

        .publication-subtitle {{
            font-size: 12px;
            color: var(--color-ink-light);
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 16px;
        }}

        .issue-info {{
            font-size: 13px;
            color: var(--color-ink-light);
            border-top: 1px solid var(--border-light);
            border-bottom: 1px solid var(--border-light);
            padding: 8px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        /* Mood Section - 大字报风格 */
        .mood-section {{
            margin-bottom: 56px;
            background: var(--color-ink);
            color: white;
            padding: 40px;
            position: relative;
        }}

        .mood-section::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 6px;
            background: {mood_color};
        }}

        .mood-label {{
            font-size: 11px;
            letter-spacing: 3px;
            text-transform: uppercase;
            opacity: 0.7;
            margin-bottom: 16px;
        }}

        .mood-word {{
            font-family: 'Playfair Display', serif;
            font-size: 64px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 20px;
            color: {mood_color};
        }}

        .mood-reason {{
            font-size: 16px;
            line-height: 1.6;
            opacity: 0.9;
            max-width: 90%;
        }}

        .mood-sources {{
            margin-top: 24px;
            font-size: 12px;
            opacity: 0.6;
        }}

        .mood-sources a {{
            color: white;
            text-decoration: none;
            border-bottom: 1px dotted rgba(255,255,255,0.4);
            margin-left: 8px;
        }}

        .mood-sources a:hover {{
            border-bottom-color: white;
        }}

        /* Section Headers */
        .section-header {{
            display: flex;
            align-items: baseline;
            margin-bottom: 24px;
            padding-bottom: 8px;
            border-bottom: 2px solid var(--color-ink);
        }}

        .section-number {{
            font-family: 'Playfair Display', serif;
            font-size: 32px;
            font-weight: 700;
            color: var(--color-accent);
            margin-right: 12px;
            line-height: 1;
        }}

        .section-title {{
            font-size: 18px;
            font-weight: 600;
            letter-spacing: 1px;
        }}

        .section-subtitle {{
            font-size: 12px;
            color: var(--color-ink-light);
            margin-left: auto;
            font-weight: 400;
        }}

        /* Cards */
        .pain-card, .news-card, .workflow-card {{
            background: var(--color-paper);
            padding: 24px;
            margin-bottom: 16px;
            box-shadow: var(--shadow-subtle);
            border: 1px solid var(--border-light);
            transition: all 0.2s ease;
        }}

        .pain-card:hover, .news-card:hover, .workflow-card:hover {{
            box-shadow: var(--shadow-card);
            transform: translateY(-1px);
        }}

        .pain-card {{
            border-left: 4px solid var(--color-pain);
        }}

        .card-meta {{
            font-size: 10px;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: var(--color-ink-light);
            margin-bottom: 8px;
        }}

        .pain-title, .news-title, .workflow-title {{
            font-size: 17px;
            font-weight: 600;
            margin-bottom: 12px;
            line-height: 1.4;
        }}

        .pain-title {{
            color: var(--color-pain);
        }}

        .pain-scene {{
            color: var(--color-ink);
            margin-bottom: 16px;
            line-height: 1.7;
        }}

        .pain-product {{
            background: var(--color-bg);
            padding: 16px;
            font-size: 14px;
            color: var(--color-ink-light);
            border-left: 2px solid var(--color-accent);
        }}

        .pain-product strong {{
            color: var(--color-accent-dark);
            font-weight: 600;
        }}

        /* News Cards */
        .news-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}

        .impact-tag {{
            font-size: 10px;
            letter-spacing: 1px;
            text-transform: uppercase;
            padding: 4px 8px;
            border: 1px solid;
        }}

        .tag-cost {{ color: var(--color-pain); border-color: var(--color-pain); }}
        .tag-time {{ color: var(--color-news); border-color: var(--color-news); }}
        .tag-opportunity {{ color: #27ae60; border-color: #27ae60; }}

        .news-date {{
            font-size: 11px;
            color: var(--color-ink-light);
        }}

        .news-title a {{
            color: var(--color-ink);
            text-decoration: none;
            border-bottom: 1px solid transparent;
            transition: border-color 0.2s;
        }}

        .news-title a:hover {{
            border-bottom-color: var(--color-ink);
        }}

        .news-interpretation {{
            color: var(--color-ink-light);
            font-size: 14px;
            line-height: 1.6;
            margin-top: 8px;
        }}

        /* Workflow */
        .workflow-card {{
            border-left: 4px solid var(--color-workflow);
        }}

        .workflow-title {{
            color: var(--color-workflow);
        }}

        .workflow-detail {{
            color: var(--color-ink);
            margin-bottom: 12px;
            line-height: 1.7;
        }}

        .workflow-tools {{
            font-size: 13px;
            color: var(--color-ink-light);
        }}

        .tools-label {{
            font-weight: 600;
            color: var(--color-accent-dark);
            margin-right: 8px;
        }}

        /* Quote Cards */
        .quotes-grid {{
            display: grid;
            gap: 20px;
        }}

        .quote-card {{
            background: var(--color-quote);
            padding: 24px;
            border: 1px solid var(--border-medium);
            box-shadow: 2px 2px 0 rgba(0,0,0,0.06);
            position: relative;
        }}

        .quote-card::before {{
            content: '"';
            position: absolute;
            top: 8px;
            left: 16px;
            font-family: 'Playfair Display', serif;
            font-size: 48px;
            color: var(--color-accent);
            opacity: 0.4;
            line-height: 1;
        }}

        .quote-text {{
            font-size: 15px;
            line-height: 1.8;
            color: var(--color-ink);
            position: relative;
            z-index: 1;
            margin-left: 8px;
        }}

        .quote-footer {{
            margin-top: 16px;
            padding-top: 12px;
            border-top: 1px dashed var(--border-medium);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            color: var(--color-ink-light);
        }}

        .quote-source-label {{
            font-weight: 600;
        }}

        /* Card Footer */
        .card-footer {{
            margin-top: 16px;
            padding-top: 12px;
            border-top: 1px solid var(--border-light);
            font-size: 11px;
            color: var(--color-ink-light);
            letter-spacing: 0.5px;
        }}

        .source-links a {{
            color: var(--color-ink-light);
            text-decoration: none;
            margin-left: 4px;
            padding: 2px 6px;
            border: 1px solid var(--border-medium);
            transition: all 0.2s;
        }}

        .source-links a:hover {{
            background: var(--color-ink);
            color: white;
            border-color: var(--color-ink);
        }}

        /* Footer */
        .page-footer {{
            margin-top: 64px;
            padding-top: 24px;
            border-top: 1px solid var(--border-medium);
            text-align: center;
            font-size: 12px;
            color: var(--color-ink-light);
            letter-spacing: 1px;
        }}

        .page-footer p {{
            margin: 4px 0;
        }}

        /* Print Styles */
        @media print {{
            body {{ background: white; }}
            .container {{ padding: 20px; }}
            .pain-card, .news-card, .workflow-card, .quote-card {{
                box-shadow: none;
                border: 1px solid #ddd;
                break-inside: avoid;
            }}
            .mood-section {{
                break-inside: avoid;
            }}
        }}

        /* Responsive */
        @media (max-width: 640px) {{
            .container {{ padding: 24px 16px; }}
            .publication-title {{ font-size: 28px; letter-spacing: 4px; }}
            .mood-section {{ padding: 24px; }}
            .mood-word {{ font-size: 42px; }}
            .section-header {{ flex-wrap: wrap; }}
            .section-subtitle {{ margin-left: 0; margin-top: 4px; width: 100%; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="masthead">
            <div class="publication-title">外贸内参</div>
            <div class="publication-subtitle">Waimao Intelligence Briefing</div>
            <div class="issue-info">
                <span>第 001 期</span>
                <span>{date}</span>
                <span>雨果 · 邦阅 · 米课</span>
            </div>
        </header>

        <section class="mood-section">
            <div class="mood-label">今日情绪晴雨表</div>
            <div class="mood-word">{mood_word}</div>
            <p class="mood-reason">{mood_reason}</p>
            <div class="mood-sources">
                参考：{mood_sources}
            </div>
        </section>

        <section class="module">
            <header class="section-header">
                <span class="section-number">01</span>
                <h2 class="section-title">高频吐槽与痛点雷达</h2>
                <span class="section-subtitle">产品灵感来源</span>
            </header>
            {pain_cards}
        </section>

        <section class="module">
            <header class="section-header">
                <span class="section-number">02</span>
                <h2 class="section-title">今日行业地震带</h2>
                <span class="section-subtitle">政策与风向</span>
            </header>
            {news_cards}
        </section>

        <section class="module">
            <header class="section-header">
                <span class="section-number">03</span>
                <h2 class="section-title">搞钱与成单拆解</h2>
                <span class="section-subtitle">工作流洞察</span>
            </header>
            {workflow_cards}
        </section>

        <section class="module">
            <header class="section-header">
                <span class="section-number">04</span>
                <h2 class="section-title">原汁原味的呐喊</h2>
                <span class="section-subtitle">真实声音</span>
            </header>
            <div class="quotes-grid">
                {quote_cards}
            </div>
        </section>

        <footer class="page-footer">
            <p>数据已存储至本地 Markdown 素材库</p>
            <p>同理心是做好产品的第一步</p>
        </footer>
    </div>
</body>
</html>"""
    return html


def run(date: str | None = None) -> Path:
    """合并当日 Markdown、调 API、写 HTML 与 JSON。返回报告路径。"""
    date = date or datetime.now().strftime("%Y-%m-%d")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    merged = _merge_markdown(date)
    if "（本日无数据）" in merged and merged.strip().count("（本日无数据）") >= 3:
        raise FileNotFoundError(f"当日无 Markdown 素材，请先运行 fetch_urls 与 fetch_and_clean。日期: {date}")

    print("正在调用大模型…")
    data = _call_llm(merged)
    _ensure_sources(data)

    json_path = REPORTS_DIR / f"neican-{date}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] JSON -> {json_path}")

    html = _render_html(date, data)
    report_path = REPORTS_DIR / f"neican-{date}.html"
    report_path.write_text(html, encoding="utf-8")
    print(f"[OK] 报告 -> {report_path}")
    return report_path


if __name__ == "__main__":
    run()
