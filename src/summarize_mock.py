#!/usr/bin/env python3
"""
Mock 版本的 summarize，用于测试 HTML 渲染（无需 API Key）
直接从 summarize.py 导入渲染函数，使用模拟数据
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

# 先导入 config
from src.config import REPORTS_DIR

# 动态导入 summarize 模块中的 _render_html
import sys
import importlib.util
spec = importlib.util.spec_from_file_location("summarize", Path(__file__).parent / "summarize.py")
summarize_module = importlib.util.module_from_spec(spec)
sys.modules["summarize"] = summarize_module
spec.loader.exec_module(summarize_module)
_render_html = summarize_module._render_html


# 模拟数据
MOCK_DATA = {
    "overall_mood": {
        "word": "焦虑",
        "reason": "海运费上涨、平台政策收紧、客户开发难度增加，外贸人面临多重成本压力",
        "source_urls": ["https://www.52by.com/article/211721", "https://www.cifnews.com/article/184088"]
    },
    "top_3_pain_points": [
        {
            "name": "客户开发效率低",
            "scene": "开发信石沉大海，每天发几百封邮件，回复率不到1%，老板还天天催KPI",
            "product_idea": "提供邮件到达率检测、智能跟进提醒、多渠道触达（邮件+社媒+WhatsApp）的集成工具",
            "source_urls": ["https://www.52by.com/article/186932", "https://www.52by.com/article/175466"]
        },
        {
            "name": "平台政策变动频繁",
            "scene": "亚马逊、TikTok政策说变就变，刚适应的规则明天可能就失效，罚款封号风险大",
            "product_idea": "实时政策监控+预警系统，自动推送平台规则变化及合规建议",
            "source_urls": ["https://www.cifnews.com/article/184088"]
        },
        {
            "name": "物流成本不可控",
            "scene": "海运费涨涨跌跌，客户嫌运费贵不下单，自己承担又亏本，左右为难",
            "product_idea": "运费趋势预测+智能报价工具，帮助业务员预判最佳发货时机",
            "source_urls": ["https://www.52by.com/article/211721"]
        }
    ],
    "core_news_impact": [
        {
            "title": "欧盟免税时代终结，7月1日起征收新关税",
            "impact_type": "cost",
            "interpretation": "欧洲市场运营成本上升10-15%，卖家需重新核算定价策略，考虑海外仓备货模式",
            "source_urls": ["https://www.cifnews.com/article/183648"]
        },
        {
            "title": "OpenClaw智能体工具引发数据泄露风险，多部门发预警",
            "impact_type": "time",
            "interpretation": "跨境卖家需谨慎使用AI工具，合规审查将增加时间成本，建议自建或选用可信工具",
            "source_urls": ["https://www.cifnews.com/article/184088"]
        }
    ],
    "workflow_insights": [
        {
            "title": "用LinkedIn+WhatsApp组合拳拿下大客户",
            "detail": "放弃传统群发邮件，通过LinkedIn找到采购负责人，点赞互动建立信任后加WhatsApp私聊，最后寄送样品促成订单",
            "tools": "LinkedIn、WhatsApp、CRM客户管理",
            "source_urls": ["https://ask.imiker.com/question/946383"]
        },
        {
            "title": "TikTok内容运营+数据分析双轮驱动",
            "detail": "使用CapCut剪辑视频，Pentos分析数据趋势，Buffer排期发布，配合TikTok Promote付费推广加速冷启动",
            "tools": "CapCut、Pentos、Buffer、TikTok Promote",
            "source_urls": ["https://www.52by.com/article/211706"]
        }
    ],
    "raw_quotes": [
        {
            "text": "每年都该来学习学习，建完站好好赚钱啦，收获满满的三天三夜。",
            "source_label": "米课圈",
            "source_urls": ["https://ask.imiker.com/question/946386"]
        },
        {
            "text": "客户砍价的情况和原因很多，知道客户砍价的原因，才能做出正确的应对。",
            "source_label": "邦阅网",
            "source_urls": ["https://www.52by.com/article/175466"]
        },
        {
            "text": "干外贸3年，落下一身颈椎病，今天终于出了个5万美金的柜子，提成够付首付了，想哭！",
            "source_label": "米课圈",
            "source_urls": ["https://ask.imiker.com/question/946384"]
        }
    ]
}


def run(date: str | None = None) -> Path:
    """使用模拟数据生成报告（无需 API）"""
    date = date or datetime.now().strftime("%Y-%m-%d")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    data = MOCK_DATA

    json_path = REPORTS_DIR / f"neican-{date}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] JSON -> {json_path}")

    # 使用 summarize.py 中的新版 _render_html
    html = _render_html(date, data)
    report_path = REPORTS_DIR / f"neican-{date}.html"
    report_path.write_text(html, encoding="utf-8")
    print(f"[OK] 报告 -> {report_path}")
    return report_path


if __name__ == "__main__":
    run()
