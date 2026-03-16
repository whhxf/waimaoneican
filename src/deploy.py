"""
可选：将生成的 neican HTML 日报通过 SCP 上传到腾讯云轻量服务器（1Panel 静态站点），
实现二级域名访问。需在 config.env 中开启并配置 NEICAN_DEPLOY_*。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv

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


def _deploy_to_git_export(report_path: Path) -> None:
    """
    新方案：将生成的 HTML 拷贝到本地静态站点仓库目录（用于 GitHub + EdgeOne）。

    环境变量：
    - NEICAN_GIT_EXPORT_ENABLED: 开关（1/true/yes/on）
    - NEICAN_GIT_EXPORT_DIR: 本地 neicanhtml 仓库目录，例如 /Users/xxx/projects/neicanhtml
      该目录下会生成：
      - neican-YYYY-MM-DD.html
      - index.html （指向最新一期）
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
    dest_file = export_dir / date_name
    dest_index = export_dir / "index.html"

    try:
        shutil.copyfile(report_path, dest_file)
        shutil.copyfile(report_path, dest_index)
    except OSError as e:
        print(f"[部署] [git] 拷贝失败: {e}")
        return

    print(f"[部署] [git] 已导出到 {dest_file}")
    print(f"[部署] [git] index.html 已更新为最新一期")


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
