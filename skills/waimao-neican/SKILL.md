---
name: waimao-neican
description: 每日抓取雨果网50条、邦阅网50条、米课圈100条，清洗为 Markdown 素材并落盘，合并后调用环境 API 生成带来源 URL 的外贸内参日报；支持一键运行或定时无人值守；可选生成后自动部署到腾讯云轻量（1Panel）二级域名。触发词：每日外贸内参、外贸日报、外贸内参、/neican
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

将依次执行：抓取 URL → 拉正文并清洗为 Markdown → 合并当日 Markdown → 调用环境配置的大模型 API → 生成 HTML 日报；若已开启部署，会再自动上传到腾讯云轻量服务器。输出在 `output/reports/neican-YYYY-MM-DD.html`，素材在 `data/markdown/`。

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

## 可选：生成后自动部署到腾讯云轻量（1Panel + 二级域名）

生成 HTML 日报后，可将报告自动上传到已安装 1Panel 的腾讯云轻量服务器，通过二级域名访问。不配置则不会执行部署。

### 配置项（config.env）

在 `config.env` 中增加（或取消注释）：

```bash
NEICAN_DEPLOY_ENABLED=1
NEICAN_DEPLOY_HOST=root@你的服务器公网IP
NEICAN_DEPLOY_PATH=/opt/1panel/apps/openresty/neican
```

- `NEICAN_DEPLOY_ENABLED`：设为 `1`、`true`、`yes` 之一即开启部署。
- `NEICAN_DEPLOY_HOST`：SSH 登录，格式 `用户@IP`（如 `root@43.xxx.xxx.xxx`）。
- `NEICAN_DEPLOY_PATH`：服务器上网站根目录的绝对路径（1Panel 里创建站点后对应的目录）。

### 具体操作步骤

1. **在腾讯云轻量服务器上安装 1Panel**（若未安装）  
   按 [1Panel 官方文档](https://1panel.cn/docs/) 安装，并确保 SSH 已开放（默认 22 端口）。

2. **在 1Panel 中创建静态网站并绑定二级域名**  
   - 打开 1Panel → 网站 → 创建网站，选择「静态网站」或使用 OpenResty/Nginx 建站。  
   - 域名填你的二级域名（如 `neican.yourdomain.com`）。  
   - 记下「网站根目录」或「运行目录」，例如：`/opt/1panel/apps/openresty/neican`（以你实际 1Panel 显示的路径为准）。  
   - 将该路径填到本机 `config.env` 的 `NEICAN_DEPLOY_PATH`。

3. **配置二级域名解析**  
   - 在域名服务商处为二级域名添加 A 记录，指向轻量服务器公网 IP。  
   - 若用 HTTPS，在 1Panel 中为该站点申请 SSL（如 Let’s Encrypt）。

4. **本机 SSH 免密登录服务器（推荐）**  
   - 本机执行：`ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519`（无则生成）。  
   - 将公钥写入服务器：`ssh-copy-id root@你的服务器IP`，按提示输入密码。  
   - 之后执行 `python run_daily.py` 时，部署步骤将自动用 SCP 上传，无需再输密码。

5. **开启部署并运行**  
   - 在 `config.env` 中设置 `NEICAN_DEPLOY_ENABLED=1` 以及上述 `NEICAN_DEPLOY_HOST`、`NEICAN_DEPLOY_PATH`。  
   - 在项目根目录执行：`python run_daily.py`。  
   - 生成日报后会自动上传：  
     - `neican-YYYY-MM-DD.html` 保留日期文件（可做历史链接）；  
     - 同时覆盖 `index.html`，访问二级域名根即最新一期。

6. **验证**  
   - 浏览器打开 `https://你的二级域名`，应看到当日外贸内参日报。

### 仅手动部署当前报告

若只想上传已有报告、不跑完整 pipeline，在项目根目录执行：

```bash
python -m src.deploy
```

会读取当日日期，上传 `output/reports/neican-YYYY-MM-DD.html`（若存在）。

## 输出与素材

- **日报**：`output/reports/neican-YYYY-MM-DD.html`，五大模块，每条带「延伸阅读」链接。
- **素材**：`data/markdown/YYYY-MM-DD_雨果网.md`、`_邦阅网.md`、`_米课圈.md`，仅含标题、链接、正文，便于日后写作复用。
