"""项目路径与常量。"""
from pathlib import Path

# 项目根目录（msg-listener）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
URLS_DIR = DATA_DIR / "urls"
MARKDOWN_DIR = DATA_DIR / "markdown"
OUTPUT_DIR = PROJECT_ROOT / "output"
REPORTS_DIR = OUTPUT_DIR / "reports"

# 数据源配置：名称, 首页 URL, 需要条数, 文章链接匹配规则（URL 包含）
SOURCES = [
    {
        "name": "雨果网",
        "url": "https://www.cifnews.com",
        "limit": 50,
        "url_contains": ["cifnews.com", "/article/"],
        "scroll_times": 2,
    },
    {
        "name": "邦阅网",
        "url": "https://www.52by.com",
        "limit": 50,
        "url_contains": ["52by.com"],
        "load_more_text": "加载更多",
        "scroll_times": 3,
    },
    {
        "name": "米课圈",
        "url": "https://ask.imiker.com/explore/find/",
        "limit": 100,
        "url_contains": ["ask.imiker.com"],
        "scroll_times": 15,
    },
]

# 正文抓取：使用 Playwright 直接访问页面提取（不再使用 jina）
# 单条正文最大保留字符
# qwen3.5-plus 支持 1M tokens 上下文，放宽到 50000 字符，基本保留完整文章
MAX_BODY_CHARS = 50000
