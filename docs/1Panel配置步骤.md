# 1Panel 配置步骤：外贸内参日报二级域名访问

在腾讯云轻量服务器上用 1Panel 创建静态网站，绑定二级域名，用于自动部署 neican 日报。按顺序执行即可。

---

## 一、安装 1Panel（若尚未安装）

1. **登录腾讯云轻量服务器**  
   在腾讯云控制台打开你的轻量应用服务器，点击「登录」或使用本地 SSH：
   ```bash
   ssh root@你的服务器公网IP
   ```

2. **执行 1Panel 官方一键安装**  
   在服务器上执行（需可访问外网）：
   ```bash
   bash -c "$(curl -sSL https://resource.fit2cloud.com/1panel/package/v2/quick_start.sh)"
   ```
   - 按提示选择安装目录、端口等（可直接回车用默认）。
   - 安装过程中会安装 Docker、1Panel 主程序；若提示 Docker 安装失败，可先执行：
     ```bash
     bash <(curl -sSL https://linuxmirrors.cn/docker.sh)
     ```
     再重新运行 1Panel 安装脚本。

3. **记录访问信息**  
   安装结束后控制台会输出类似：
   ```text
   http://目标服务器IP:目标端口/安全入口
   ```
   记下「端口」和「安全入口」。若忘记安全入口，在服务器上执行：
   ```bash
   1pctl user-info
   ```

4. **开放防火墙端口**  
   - 在腾讯云轻量控制台：防火墙 / 安全组 中放行 1Panel 使用的端口（默认如 xxxx）。  
   - 同时放行 **80**、**443**（后续网站访问）、**22**（SSH）。

5. **浏览器访问 1Panel**  
   打开 `http://你的服务器IP:端口/安全入口`，用安装时设置的用户名密码登录。

---

## 二、安装 OpenResty（网站运行环境）

1Panel 用 OpenResty（Nginx）来托管网站，需先安装：

1. 在 1Panel 左侧菜单进入 **应用商店**。
2. 搜索 **OpenResty**，点击「安装」。
3. 安装完成后保持「运行中」状态，无需额外配置。

---

## 三、创建静态网站并绑定二级域名

1. 在 1Panel 左侧菜单进入 **网站** → **创建网站**。

2. 选择类型：**静态网站**。

3. 填写表单：
   - **主域名**：你的二级域名，例如 `neican.yourdomain.com`（先填好，后面再做域名解析）。
   - **代号**：填英文目录名，例如 `neican`（会作为网站目录名，建议与主域名一致或好记）。
   - **备注**：可选，如「外贸内参日报」。
   - **其他域名**：不填即可。
   - **启用 HTTPS**：可先不勾选，建好站并解析后再来配置 SSL。

4. 点击「确认」创建。

5. **查看网站根目录路径**（部署时要填到本机 `config.env`）：
   - 在 **网站** 列表中找到刚建的站点，点击站点名进入。
   - 左侧或上方进入 **基本设置** → **网站目录**。
   - 页面上会显示「网站根目录」的绝对路径，例如：
     ```text
     /opt/1panel/apps/openresty/openresty/www/sites/neican
     ```
     或类似（不同 1Panel/OpenResty 版本可能略有差异，以你当前页面显示为准）。  
   - **复制该路径**，作为本机 `config.env` 里的 `NEICAN_DEPLOY_PATH`。

---

## 四、配置二级域名解析

1. 登录你的**域名服务商**（阿里云、腾讯云 DNSPod、Cloudflare 等）。

2. 找到该域名的 **DNS 解析 / 解析设置**。

3. 添加一条 **A 记录**：
   - **主机记录**：填二级前缀，如 `neican`（即 `neican.yourdomain.com`）。
   - **记录类型**：A。
   - **记录值**：填腾讯云轻量服务器的 **公网 IP**。
   - TTL：默认即可（如 600 或 10 分钟）。

4. 等待解析生效（通常几分钟，最多可能几小时）。  
   可用本机测试：`ping neican.yourdomain.com` 看是否解析到服务器 IP。

---

## 五、配置 HTTPS（推荐）

1. 在 1Panel **网站** 中点击该站点 → **基本设置** → **HTTPS**。

2. 选择 **Let's Encrypt** 等免费证书（1Panel 会引导申请），或使用「选择已有证书」若你已有证书。

3. 勾选「自动将 HTTP 跳转到 HTTPS」等选项后保存。

4. 证书申请成功后，即可用 `https://neican.yourdomain.com` 访问。

---

## 六、本机配置与自动部署

1. **本机 `config.env`** 中配置（路径用你在「三、5」中复制的网站根目录）：
   ```bash
   NEICAN_DEPLOY_ENABLED=1
   NEICAN_DEPLOY_HOST=root@你的服务器公网IP
   NEICAN_DEPLOY_PATH=/opt/1panel/apps/openresty/openresty/www/sites/neican
   ```
   `NEICAN_DEPLOY_PATH` 务必与 1Panel 里「网站目录」显示的路径一致（有的版本末尾带 `/index` 或不同，以面板为准）。

2. **本机 SSH 免密**（推荐）：
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
   ssh-copy-id root@你的服务器公网IP
   ```
   输入一次服务器密码后，以后 `python run_daily.py` 部署时不再需要输密码。

3. **运行日报并部署**：
   ```bash
   cd /path/to/waimaoneican
   python run_daily.py
   ```
   生成 HTML 后会自动上传到服务器；访问 `https://neican.yourdomain.com` 即可看到最新一期，历史期为 `https://neican.yourdomain.com/neican-YYYY-MM-DD.html`。

---

## 常见问题

- **安装 OpenResty 时提示 80 端口已占用**  
  说明系统里已有程序在监听 80（常见是 Nginx、Apache、1Panel 自带的某个服务等）。  
  1）在服务器上查占用：`ss -tlnp | grep :80` 或 `lsof -i :80`，看是哪个进程。  
  2）若该进程可以不用（例如旧的 Nginx 测试），可先停掉再装 OpenResty。  
  3）若必须保留 80 给别的服务，可在 1Panel 安装 OpenResty 时选择其他端口（如 8080），但之后网站访问需带端口（如 `http://域名:8080`），且 HTTPS 通常仍需 443。  
  4）若 80 被 1Panel 自己的 Nginx/OpenResty 占用了，可能是之前装过，可在 1Panel「应用商店」里看是否已有 OpenResty/Nginx，若已运行可直接用，不必再装一份。

- **上传后访问 403 / 空白**  
  检查 1Panel 里该站点的「网站目录」权限，确保运行用户（如 www）对该目录有读权限；或在本机用 `scp` 手动传一个 `index.html` 测试是否能访问。

- **SCP 报错 Permission denied (publickey)**  
  本机未做免密或密钥未生效，请完成「六、2」或改用密码登录（需在 deploy 或脚本里配合 sshpass，不推荐）。

- **路径不确定**  
  以 1Panel **网站 → 该站点 → 基本设置 → 网站目录** 中显示的「网站根目录」为准，不要猜路径。

- **1Panel 安装/访问问题**  
  见官方文档：[1Panel 在线安装](https://1panel.cn/docs/installation/online_installation/)、[创建网站](https://1panel.cn/docs/v2/user_manual/websites/website_create/)。
