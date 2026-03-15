"""
可选：将生成的 neican HTML 日报通过 SCP 上传到腾讯云轻量服务器（1Panel 静态站点），
实现二级域名访问。需在 config.env 中开启并配置 NEICAN_DEPLOY_*。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "config.env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _is_deploy_enabled() -> bool:
    v = (os.environ.get("NEICAN_DEPLOY_ENABLED") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def deploy(report_path: Path) -> None:
    """
    若已配置部署，则将 report_path 上传到服务器：
    - 保留日期文件：neican-YYYY-MM-DD.html（历史可访问）
    - 同时写入 index.html（二级域名根即最新一期）
    """
    if not _is_deploy_enabled():
        return
    host = (os.environ.get("NEICAN_DEPLOY_HOST") or "").strip()
    remote_path = (os.environ.get("NEICAN_DEPLOY_PATH") or "").strip().rstrip("/")
    if not host or not remote_path:
        print("[部署] 已开启但 NEICAN_DEPLOY_HOST 或 NEICAN_DEPLOY_PATH 未配置，跳过")
        return
    if not report_path.exists():
        print(f"[部署] 文件不存在: {report_path}，跳过")
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
            print(f"[部署] 已上传 -> {host}:{dest}")
        except subprocess.CalledProcessError as e:
            print(f"[部署] 上传失败 {dest}: {e}")
        except FileNotFoundError:
            print("[部署] 未找到 scp 命令，请确保 SSH 已安装并可访问")
            break
        except subprocess.TimeoutExpired:
            print(f"[部署] 上传超时: {dest}")


if __name__ == "__main__":
    from src.config import REPORTS_DIR
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / f"neican-{date}.html"
    deploy(report_path)
