# 外贸内参 (Waimao Neican)

每日抓取雨果网、邦阅网、米课圈文章，清洗为 Markdown 素材并落盘，合并后经大模型总结为「外贸同理心日报」（五大模块，每条带数据来源 URL）。支持本地一键运行与定时无人值守。

## 数据源与数量

| 来源   | 条数  | URL |
|--------|-------|-----|
| 雨果网 | 50 条 | https://www.cifnews.com |
| 邦阅网 | 50 条 | https://www.52by.com |
| 米课圈 | 100 条 | https://ask.imiker.com/explore/find/ |

## 环境准备

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

复制配置并填写 API：

```bash
cp config.example.env config.env
# 编辑 config.env：OPENAI_API_KEY、OPENAI_BASE_URL（可选）、OPENAI_MODEL
```

## 一键运行

```bash
python run_daily.py
```

将依次执行：抓取 URL → 拉正文并清洗为 Markdown → 合并当日 MD → 调用大模型 → 生成 HTML 日报。

- **日报**：`output/reports/neican-YYYY-MM-DD.html`
- **素材**：`data/markdown/YYYY-MM-DD_雨果网.md`、`_邦阅网.md`、`_米课圈.md`

## 分步执行

```bash
python -m src.fetch_urls        # 步骤1：抓取 URL 列表
python -m src.fetch_and_clean   # 步骤2：拉正文、去噪、写 Markdown
python -m src.summarize         # 步骤3：合并 MD、调 API、生成报告
```

## 无人值守（定时任务）

### macOS / Linux：cron

每日 6:00 执行（请将 `/path/to/msg-listener` 改为实际路径）：

```cron
0 6 * * * cd /path/to/msg-listener && .venv/bin/python run_daily.py >> /path/to/msg-listener/logs/cron.log 2>&1
```

### macOS：launchd

1. 创建 `~/Library/LaunchAgents/com.waimao.neican.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.waimao.neican</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/msg-listener/.venv/bin/python</string>
        <string>/path/to/msg-listener/run_daily.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/msg-listener</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/path/to/msg-listener/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/msg-listener/logs/launchd.err</string>
</dict>
</plist>
```

2. 加载：

```bash
launchctl load ~/Library/LaunchAgents/com.waimao.neican.plist
```

### Windows：任务计划程序

在「任务计划程序」中新建任务，触发器为每日指定时间，操作：程序 `python`，参数 `run_daily.py`，起始于项目根目录。

## 项目结构

```
msg-listener/
├── run_daily.py           # 一键入口
├── config.example.env     # 配置示例
├── config.env            # 本地配置（勿提交）
├── requirements.txt
├── docs/
│   └── 需求说明书.md
├── skills/
│   └── waimao-neican/
│       └── SKILL.md       # Cursor Skill 说明
├── src/
│   ├── config.py         # 路径与数据源配置
│   ├── fetch_urls.py     # 抓取 URL
│   ├── fetch_and_clean.py # 拉正文、清洗、写 Markdown
│   └── summarize.py       # 合并、调 API、生成 HTML
├── data/
│   ├── urls/             # 每日 URL 列表 JSON
│   └── markdown/         # 清洗后 Markdown 素材
└── output/
    └── reports/          # 日报 HTML + JSON
```

## Skill 触发词

在 Cursor 中可触发：`每日外贸内参`、`外贸日报`、`外贸内参`、`/neican`。详见 `skills/waimao-neican/SKILL.md`。
