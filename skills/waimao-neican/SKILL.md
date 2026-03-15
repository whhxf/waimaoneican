---
name: waimao-neican
description: 每日抓取雨果网50条、邦阅网50条、米课圈100条，清洗为 Markdown 素材并落盘，合并后调用环境 API 生成带来源 URL 的外贸内参日报；支持一键运行或定时无人值守。触发词：每日外贸内参、外贸日报、外贸内参、/neican
metadata:
  version: 1.0.0
  scope: project
---

# 外贸内参 (Waimao Neican)

为产品经理/开发者提供每日「外贸同理心日报」：从雨果网、邦阅网、米课圈抓取内容，清洗为 Markdown 素材，合并后经大模型总结为五大模块报告（情绪晴雨表、痛点雷达、行业地震带、搞钱拆解、金句盲盒），每条结论带数据来源 URL。

## 触发词

- 每日外贸内参
- 外贸日报
- 外贸内参
- /neican

## 使用方式

### 一键运行（推荐）

在项目根目录执行：

```bash
python run_daily.py
```

将依次执行：抓取 URL → 拉正文并清洗为 Markdown → 合并当日 Markdown → 调用环境配置的大模型 API → 生成 HTML 日报。输出在 `output/reports/neican-YYYY-MM-DD.html`，素材在 `data/markdown/`。

### 分步执行

```bash
# 1. 抓取各站文章 URL（雨果 50 / 邦阅 50 / 米课圈 100）
python -m src.fetch_urls

# 2. 拉正文、去噪、写 Markdown 到 data/markdown/
python -m src.fetch_and_clean

# 3. 合并当日 MD、调 API、生成报告
python -m src.summarize
```

### 无人值守（定时任务）

- **macOS / Linux (cron)**：每日 6:00 执行  
  `0 6 * * * cd /path/to/msg-listener && python run_daily.py`

- **macOS (launchd)**：在 `README.md` 中查看 plist 示例与加载方式。

- **Windows**：使用任务计划程序，每日指定时间运行 `python run_daily.py`。

## 环境配置

复制 `config.example.env` 为 `config.env`（或通过环境变量），配置大模型 API：

- `OPENAI_API_KEY`（或兼容 API 的 key）
- `OPENAI_BASE_URL`（可选，兼容端点）
- `OPENAI_MODEL`（如 gpt-4o、gpt-4o-mini）

详见项目根目录 `README.md`。

## 输出与素材

- **日报**：`output/reports/neican-YYYY-MM-DD.html`，五大模块，每条带「延伸阅读」链接。
- **素材**：`data/markdown/YYYY-MM-DD_雨果网.md`、`_邦阅网.md`、`_米课圈.md`，仅含标题、链接、正文，便于日后写作复用。
