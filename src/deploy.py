"""
可选：将生成的 neican HTML 日报通过 SCP 上传到腾讯云轻量服务器（1Panel 静态站点），
实现二级域名访问。需在 config.env 中开启并配置 NEICAN_DEPLOY_*。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv

# 与 summarize.py 一致的情绪颜色
MOOD_COLORS = {
    "焦虑": "#c0392b",
    "愤怒": "#8e44ad",
    "喜悦": "#d4a373",
    "平静": "#5d6d7e",
    "兴奋": "#e67e22",
}
DEFAULT_MOOD_COLOR = "#1a1a2e"

load_dotenv(Path(__file__).resolve().parent.parent / "config.env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _flag_on(value: str | None) -> bool:
    v = (value or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _deploy_to_server(report_path: Path) -> None:
    """旧方案：通过 scp 上传到 1Panel / 服务器目录。"""
    if not _flag_on(os.environ.get("NEICAN_DEPLOY_ENABLED")):
        return

    host = (os.environ.get("NEICAN_DEPLOY_HOST") or "").strip()
    remote_path = (os.environ.get("NEICAN_DEPLOY_PATH") or "").strip().rstrip("/")
    if not host or not remote_path:
        print("[部署] 已开启 NEICAN_DEPLOY_ENABLED，但 NEICAN_DEPLOY_HOST 或 NEICAN_DEPLOY_PATH 未配置，跳过服务器部署")
        return
    if not report_path.exists():
        print(f"[部署] 文件不存在: {report_path}，跳过服务器部署")
        return

    date_name = report_path.name  # neican-YYYY-MM-DD.html
    remote_file = f"{remote_path}/{date_name}"
    remote_index = f"{remote_path}/index.html"

    for dest in (remote_file, remote_index):
        try:
            subprocess.run(
                ["scp", "-o", "StrictHostKeyChecking=accept-new", str(report_path), f"{host}:{dest}"],
                check=True,
                timeout=60,
            )
            print(f"[部署] [server] 已上传 -> {host}:{dest}")
        except subprocess.CalledProcessError as e:
            print(f"[部署] [server] 上传失败 {dest}: {e}")
        except FileNotFoundError:
            print("[部署] [server] 未找到 scp 命令，请确保 SSH 已安装并可访问")
            break
        except subprocess.TimeoutExpired:
            print(f"[部署] [server] 上传超时: {dest}")


def _build_manifest(export_dir: Path) -> str | None:
    """
    扫描 export_dir 下所有 neican-YYYY-MM-DD.json，生成 manifest.json。
    返回最新日期 YYYY-MM-DD，若无任何 JSON 则返回 None。
    """
    pattern = re.compile(r"^neican-(\d{4}-\d{2}-\d{2})\.json$")
    days: list[dict] = []
    for p in export_dir.iterdir():
        if not p.is_file():
            continue
        m = pattern.match(p.name)
        if not m:
            continue
        date_str = m.group(1)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        mood = (data.get("overall_mood") or {}) if isinstance(data.get("overall_mood"), dict) else {}
        word = mood.get("word", "—")
        reason = mood.get("reason", "")
        color = MOOD_COLORS.get(word, DEFAULT_MOOD_COLOR)
        days.append({
            "date": date_str,
            "mood_word": word,
            "mood_color": color,
            "mood_reason": reason[:200] + ("…" if len(reason) > 200 else ""),
        })
    days.sort(key=lambda x: x["date"], reverse=True)
    latest = days[0]["date"] if days else None
    manifest = {"updated": latest or "", "days": days}
    (export_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return latest


def _render_index_html(latest_date: str | None, export_dir: Path) -> None:
    """
    生成汇总导航页 index.html：主区为当日最新内参（iframe），右侧边栏上半为历史内参列表（可翻页），下半为情绪日历。
    """
    iframe_src = f"neican-{latest_date}.html" if latest_date else ""
    iframe_html = (
        f'<iframe id="report-frame" src="{iframe_src}" title="当日内参"></iframe>'
        if iframe_src
        else '<p class="no-report">暂无内参数据，请先运行 run_daily.py 并导出。</p>'
    )
    default_year = int(latest_date[:4]) if latest_date else 2026
    default_month = int(latest_date[5:7]) if latest_date else 3

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>外贸内参 · 汇总</title>
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
            --border-light: #e8e4de;
            --border-medium: #d4cfc7;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Noto Serif SC', 'Songti SC', Georgia, serif;
            line-height: 1.75;
            color: var(--color-ink);
            background: var(--color-bg);
            font-size: 15px;
        }}
        .masthead {{
            text-align: center;
            padding: 24px 24px 20px;
            border-bottom: 3px double var(--color-ink);
        }}
        .masthead::before {{
            content: '';
            display: block;
            height: 4px;
            background: linear-gradient(90deg, var(--color-ink) 0%, var(--color-accent) 50%, var(--color-ink) 100%);
            margin: -24px -24px 24px -24px;
        }}
        .publication-title {{
            font-family: 'Playfair Display', 'Noto Serif SC', serif;
            font-size: 36px;
            font-weight: 700;
            letter-spacing: 6px;
            color: var(--color-ink);
            margin-bottom: 6px;
            text-transform: uppercase;
        }}
        .publication-subtitle {{ font-size: 12px; color: var(--color-ink-light); letter-spacing: 2px; }}
        .layout-wrap {{
            display: flex;
            gap: 24px;
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px;
        }}
        .main {{
            flex: 1;
            min-width: 0;
        }}
        .section-title {{ font-size: 16px; font-weight: 600; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 2px solid var(--color-ink); }}
        #report-wrap {{
            background: var(--color-paper);
            border: 1px solid var(--border-light);
            overflow: hidden;
        }}
        #report-frame {{ width: 100%; height: 80vh; min-height: 520px; border: 0; display: block; }}
        .no-report {{ padding: 40px; text-align: center; color: var(--color-ink-light); }}
        .sidebar {{
            width: 280px;
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }}
        .history-section {{ flex-shrink: 0; }}
        .history-list-wrap {{
            max-height: 36vh;
            overflow-y: auto;
            border: 1px solid var(--border-light);
            background: var(--color-paper);
            border-radius: 6px;
        }}
        .history-list {{ list-style: none; }}
        .history-list a {{
            display: block;
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-light);
            color: var(--color-ink);
            text-decoration: none;
            font-size: 14px;
        }}
        .history-list a:hover {{ background: var(--color-bg); }}
        .history-list a:last-child {{ border-bottom: none; }}
        .history-date {{ font-weight: 600; margin-bottom: 2px; }}
        .history-mood {{ font-size: 12px; color: var(--color-ink-light); }}
        .history-more {{
            display: block;
            width: 100%;
            margin-top: 8px;
            padding: 8px 12px;
            font-family: inherit;
            font-size: 13px;
            cursor: pointer;
            background: var(--color-paper);
            border: 1px solid var(--border-medium);
            color: var(--color-ink);
            border-radius: 4px;
        }}
        .history-more:hover {{ background: var(--color-bg); border-color: var(--color-accent); }}
        .history-more:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .calendar-section {{ flex-shrink: 0; }}
        .calendar-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
        }}
        .calendar-title {{ font-size: 16px; font-weight: 600; }}
        .calendar-nav {{ display: flex; gap: 6px; }}
        .calendar-nav button {{
            padding: 4px 10px;
            font-family: inherit;
            font-size: 12px;
            cursor: pointer;
            background: var(--color-paper);
            border: 1px solid var(--border-medium);
            color: var(--color-ink);
            border-radius: 4px;
        }}
        .calendar-nav button:hover {{ background: var(--color-bg); border-color: var(--color-accent); }}
        .calendar-nav button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .calendar-weekdays {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 2px;
            margin-bottom: 6px;
            font-size: 10px;
            color: var(--color-ink-light);
            text-align: center;
        }}
        .calendar-grid {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 4px;
        }}
        .calendar-day {{
            aspect-ratio: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            border-radius: 4px;
            background: var(--color-bg);
            border: 1px solid var(--border-light);
            color: var(--color-ink-light);
        }}
        .calendar-day.has-data {{
            cursor: pointer;
            text-decoration: none;
            color: var(--color-ink);
            font-weight: 600;
        }}
        .calendar-day.has-data:hover {{ border-color: var(--color-accent); box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
        .calendar-day .mood-label {{ font-size: 9px; margin-top: 1px; }}
        .calendar-day.empty {{ opacity: 0.5; }}
        @media (max-width: 900px) {{
            .layout-wrap {{ flex-direction: column; }}
            .sidebar {{ width: 100%; flex-direction: row; flex-wrap: wrap; }}
            .history-section {{ flex: 1; min-width: 260px; }}
            .history-list-wrap {{ max-height: 240px; }}
            .calendar-section {{ min-width: 260px; }}
        }}
        @media (max-width: 640px) {{
            .masthead {{ padding: 16px; }}
            .publication-title {{ font-size: 26px; letter-spacing: 4px; }}
            .layout-wrap {{ padding: 16px; }}
        }}
    </style>
</head>
<body>
    <header class="masthead">
        <div class="publication-title">外贸内参</div>
        <div class="publication-subtitle">Waimao Intelligence Briefing · 汇总</div>
    </header>
    <div class="layout-wrap">
        <main class="main">
            <h2 class="section-title">当日最新内参</h2>
            <div id="report-wrap">{iframe_html}</div>
        </main>
        <aside class="sidebar">
            <section class="history-section">
                <h2 class="section-title">历史内参</h2>
                <div class="history-list-wrap">
                    <ul class="history-list" id="history-list"></ul>
                </div>
                <button type="button" class="history-more" id="history-more">加载更多</button>
            </section>
            <section class="calendar-section">
                <h2 class="section-title">情绪日历</h2>
                <div class="calendar-header">
                    <span class="calendar-title" id="calendar-title">加载中…</span>
                    <div class="calendar-nav">
                        <button type="button" id="btn-prev" aria-label="上一月">上一月</button>
                        <button type="button" id="btn-next" aria-label="下一月">下一月</button>
                    </div>
                </div>
                <div class="calendar-weekdays">
                    <span>日</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span>
                </div>
                <div class="calendar-grid" id="calendar-grid"></div>
            </section>
        </aside>
    </div>
    <script>
(function() {{
    const MIN_YEAR = 2026, MIN_MONTH = 3;
    const HISTORY_PAGE_SIZE = 10;
    let manifest = {{ days: [] }};
    let currentYear = {default_year}, currentMonth = {default_month};
    let historyShown = 0;

    function getDaysInMonth(y, m) {{
        return new Date(y, m, 0).getDate();
    }}
    function getFirstWeekday(y, m) {{
        return new Date(y, m - 1, 1).getDay();
    }}
    function buildDayMap() {{
        const map = {{}};
        manifest.days.forEach(function(d) {{
            map[d.date] = {{ mood_word: d.mood_word, mood_color: d.mood_color, mood_reason: d.mood_reason }};
        }});
        return map;
    }}

    function renderHistoryList(append) {{
        const listEl = document.getElementById('history-list');
        const btnEl = document.getElementById('history-more');
        const total = manifest.days.length;
        if (!append) {{
            listEl.innerHTML = '';
            historyShown = 0;
        }}
        const end = Math.min(historyShown + HISTORY_PAGE_SIZE, total);
        for (var i = historyShown; i < end; i++) {{
            var d = manifest.days[i];
            var a = document.createElement('a');
            a.href = 'neican-' + d.date + '.html';
            a.innerHTML = '<span class="history-date">' + d.date + '</span><span class="history-mood">' + (d.mood_word || '—') + '</span>';
            listEl.appendChild(a);
        }}
        historyShown = end;
        btnEl.style.display = total === 0 ? 'none' : 'block';
        btnEl.disabled = historyShown >= total;
        btnEl.textContent = historyShown >= total ? '已全部加载' : '加载更多';
    }}

    function renderCalendar() {{
        var titleEl = document.getElementById('calendar-title');
        var gridEl = document.getElementById('calendar-grid');
        var btnPrev = document.getElementById('btn-prev');
        var btnNext = document.getElementById('btn-next');
        titleEl.textContent = currentYear + ' 年 ' + currentMonth + ' 月';
        btnPrev.disabled = currentYear === MIN_YEAR && currentMonth === MIN_MONTH;
        var now = new Date();
        btnNext.disabled = currentYear > now.getFullYear() || (currentYear === now.getFullYear() && currentMonth >= now.getMonth() + 1);
        var dayMap = buildDayMap();
        var daysInMonth = getDaysInMonth(currentYear, currentMonth);
        var firstWeekday = getFirstWeekday(currentYear, currentMonth);
        gridEl.innerHTML = '';
        for (var i = 0; i < firstWeekday; i++) {{
            var cell = document.createElement('div');
            cell.className = 'calendar-day empty';
            cell.setAttribute('aria-hidden', 'true');
            gridEl.appendChild(cell);
        }}
        for (var d = 1; d <= daysInMonth; d++) {{
            var dateStr = currentYear + '-' + String(currentMonth).padStart(2, '0') + '-' + String(d).padStart(2, '0');
            var info = dayMap[dateStr];
            var cell = document.createElement(info ? 'a' : 'div');
            cell.className = 'calendar-day' + (info ? ' has-data' : ' empty');
            if (info) {{
                cell.href = 'neican-' + dateStr + '.html';
                cell.setAttribute('title', info.mood_reason || info.mood_word);
            }}
            var dayNum = document.createElement('span');
            dayNum.textContent = d;
            cell.appendChild(dayNum);
            if (info) {{
                var label = document.createElement('span');
                label.className = 'mood-label';
                label.textContent = info.mood_word;
                label.style.color = info.mood_color;
                cell.appendChild(label);
            }}
            gridEl.appendChild(cell);
        }}
    }}

    document.getElementById('btn-prev').addEventListener('click', function() {{
        if (currentMonth === 1) {{ currentYear--; currentMonth = 12; }} else {{ currentMonth--; }}
        if (currentYear < MIN_YEAR || (currentYear === MIN_YEAR && currentMonth < MIN_MONTH)) {{ currentYear = MIN_YEAR; currentMonth = MIN_MONTH; }}
        renderCalendar();
    }});
    document.getElementById('btn-next').addEventListener('click', function() {{
        var now = new Date();
        if (currentYear > now.getFullYear() || (currentYear === now.getFullYear() && currentMonth >= now.getMonth() + 1)) return;
        if (currentMonth === 12) {{ currentYear++; currentMonth = 1; }} else {{ currentMonth++; }}
        renderCalendar();
    }});
    document.getElementById('history-more').addEventListener('click', function() {{ renderHistoryList(true); }});

    fetch('./manifest.json')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
            manifest = data;
            renderHistoryList(false);
            renderCalendar();
        }})
        .catch(function() {{
            document.getElementById('calendar-title').textContent = '暂无数据';
        }});
}})();
    </script>
</body>
</html>"""
    (export_dir / "index.html").write_text(html, encoding="utf-8")


def _deploy_to_git_export(report_path: Path) -> None:
    """
    新方案：将生成的 HTML/JSON 拷贝到本地静态站点仓库，重建 manifest，生成汇总 index.html。

    环境变量：
    - NEICAN_GIT_EXPORT_ENABLED: 开关（1/true/yes/on）
    - NEICAN_GIT_EXPORT_DIR: 本地 neicanhtml 仓库目录
      该目录下会生成：neican-YYYY-MM-DD.html、neican-YYYY-MM-DD.json、manifest.json、index.html
    """
    if not _flag_on(os.environ.get("NEICAN_GIT_EXPORT_ENABLED")):
        return

    export_dir_raw = (os.environ.get("NEICAN_GIT_EXPORT_DIR") or "").strip()
    if not export_dir_raw:
        print("[部署] NEICAN_GIT_EXPORT_ENABLED=on，但 NEICAN_GIT_EXPORT_DIR 为空，跳过 Git 导出")
        return

    export_dir = Path(export_dir_raw).expanduser().resolve()
    export_dir.mkdir(parents=True, exist_ok=True)

    if not report_path.exists():
        print(f"[部署] 文件不存在: {report_path}，跳过 Git 导出")
        return

    date_name = report_path.name  # neican-YYYY-MM-DD.html
    date_stem = date_name.replace(".html", "")
    json_src = report_path.with_suffix(".json")
    dest_html = export_dir / date_name
    dest_json = export_dir / f"{date_stem}.json"

    try:
        shutil.copyfile(report_path, dest_html)
        if json_src.exists():
            shutil.copyfile(json_src, dest_json)
    except OSError as e:
        print(f"[部署] [git] 拷贝失败: {e}")
        return

    print(f"[部署] [git] 已导出到 {dest_html}")

    latest = _build_manifest(export_dir)
    n_days = len(json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))["days"])
    print(f"[部署] [git] manifest.json 已更新，共 {n_days} 期")
    _render_index_html(latest, export_dir)
    print(f"[部署] [git] index.html 已更新为汇总页")


def deploy(report_path: Path) -> None:
    """
    部署入口：
    - 若配置 NEICAN_DEPLOY_*：继续支持旧的服务器 scp 部署（1Panel / 轻量服务器）。
    - 若配置 NEICAN_GIT_EXPORT_*：将 HTML 拷贝到本地静态站点仓库（用于 GitHub + EdgeOne/CDN）。
    两者可并行开启，也可只用其一。
    """
    _deploy_to_server(report_path)
    _deploy_to_git_export(report_path)


if __name__ == "__main__":
    from src.config import REPORTS_DIR
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / f"neican-{date}.html"
    deploy(report_path)
