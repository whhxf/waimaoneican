---
name: waimao-neican
description: 每日抓取雨果网 30 条、邦阅网 30 条、米课圈 140 条，清洗为 Markdown 素材并落盘，合并后调用环境 API 生成带来源 URL 的外贸内参日报；支持一键运行或定时无人值守；可选生成后自动提交到 Git 仓库，通过 Cloudflare Pages 实现全球 CDN 加速和 HTTPS 访问。触发词：每日外贸内参、外贸日报、外贸内参、/neican
metadata:
  version: 1.1.0
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

将依次执行：抓取 URL → 拉正文并清洗为 Markdown → 合并当日 Markdown → 调用环境配置的大模型 API → 生成 HTML 日报；若已开启部署，会再自动提交到 Git 仓库并通过 Cloudflare Pages 发布。输出在 `output/reports/neican-YYYY-MM-DD.html`，素材在 `data/markdown/`。

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

## 可选：生成后自动提交到 Git 仓库 + Cloudflare Pages 部署

生成 HTML 日报后，可将报告自动提交到 GitHub 仓库 `neicanhtml`，该仓库已连接 Cloudflare Pages，会自动构建并发布，通过自定义域名 + HTTPS 全球 CDN 加速访问。不配置则不会执行部署。

### 配置项（config.env）

在 `config.env` 中增加（或取消注释）：

```bash
NEICAN_GIT_EXPORT_ENABLED=1
NEICAN_GIT_EXPORT_DIR=/absolute/path/to/neicanhtml
```

- `NEICAN_GIT_EXPORT_ENABLED`：设为 `1`、`true`、`yes` 之一即开启部署。
- `NEICAN_GIT_EXPORT_DIR`：本地 `neicanhtml` Git 仓库的**绝对路径**。

### 具体操作步骤

1. **本地克隆静态站点仓库**

   ```bash
   # 任选一个目录作为静态仓库位置（建议与本项目同级）
   cd /path/to/your/workspace
   git clone git@github.com:whhxf/neicanhtml.git
   # 或者用 HTTPS：
   # git clone https://github.com/whhxf/neicanhtml.git
   ```

2. **在本项目里配置导出目录**

   编辑 `config.env`，增加：

   ```bash
   NEICAN_GIT_EXPORT_ENABLED=1
   NEICAN_GIT_EXPORT_DIR=/absolute/path/to/neicanhtml
   ```

   `NEICAN_GIT_EXPORT_DIR` 必须是你刚才克隆的 `neicanhtml` 仓库的**绝对路径**。

3. **运行日报并导出到静态仓库**

   ```bash
   cd /path/to/waimaoneican
   python run_daily.py
   ```

   跑完后，会在 `NEICAN_GIT_EXPORT_DIR` 目录下自动生成：
   - `neican-YYYY-MM-DD.html`：当期日报（历史可保留多期）
   - `index.html`：始终指向**最新一期**，方便用作首页

4. **提交并推送到 GitHub**

   ```bash
   cd /absolute/path/to/neicanhtml
   git add .
   git commit -m "feat: 更新外贸内参 YYYY-MM-DD"
   git push origin main
   ```

   推送后，Cloudflare Pages 会自动检测到仓库更新并开始构建。

5. **在 Cloudflare Pages 上接入该仓库**

   - 打开 Cloudflare Dashboard → Pages → 创建项目 → 连接到 Git
   - 选择 `neicanhtml` 仓库
   - 构建设置：无需构建命令，直接部署（因为是纯静态 HTML）
   - 自定义域名：绑定你的域名（如 `nc.kingswayai.cloud`）
   - 启用 HTTPS（Cloudflare 自动提供）

   构建完成后，访问 `https://你的域名/neican-YYYY-MM-DD.html` 即可在线查看日报。

> **小结**：每天跑完 `python run_daily.py` 后，在 `neicanhtml` 仓库里 `git add/commit/push` 一次，页面就会自动更新到线上。

### 仅手动提交当前报告

若只想提交已有报告、不跑完整 pipeline，在项目根目录执行：

```bash
python -m src.git_export
```

会读取当日日报并复制到 Git 仓库目录（需配置 `NEICAN_GIT_EXPORT_DIR`）。

## 输出与素材

- **日报**：`output/reports/neican-YYYY-MM-DD.html`，五大模块，每条带「延伸阅读」链接。
- **素材**：`data/markdown/YYYY-MM-DD_雨果网.md`、`_邦阅网.md`、`_米课圈.md`，仅含标题、链接、正文，便于日后写作复用。
