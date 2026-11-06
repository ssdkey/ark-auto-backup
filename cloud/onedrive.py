"""OneDrive 上传插件（Microsoft Graph API）
认证：Authorization: Bearer <access_token>。
上传：PUT https://graph.microsoft.com/v1.0/me/drive/root:/<path>:/content
说明：单请求 PUT 适合 ≤250MB 文件；>250MB 需 createUploadSession 分片，
本插件对超大文件会直接提示（默认走 PUT，遇 413 给出明确错误）。
access_token 官方有效期约 1 小时，过期需用户重新获取。
"""
import os

import requests

from .base import CloudUploader, Field, register

GRAPH = "https://graph.microsoft.com/v1.0"
# PUT 整文件上限
SIMPLE_LIMIT = 250 * 1024 * 1024


@register
class OneDriveUploader(CloudUploader):
    key = "onedrive"
    name = "OneDrive"
    desc = "微软 OneDrive 个人云盘（Graph API）。access_token 约 1 小时有效，过期需重新获取。"

    fields = [
        Field("access_token", "access_token", placeholder="粘贴 Graph access_token", secret=True),
        Field("remote_dir", "云端目录", placeholder="留空=OneDrive 根目录", required=False),
    ]

    def _headers(self):
        return {"Authorization": "Bearer " + self.config.get("access_token", ""),
                "Content-Type": "text/plain"}

    def _remote_path(self, remote_dir):
        d = remote_dir or self.config.get("remote_dir", "")
        d = d.strip("/")
        return d

    def test_connection(self):
        ok, missing = self.validate()
        if not ok:
            return False, "缺少必填字段: " + ", ".join(missing)
        try:
            r = requests.get(f"{GRAPH}/me/drive",
                             headers={"Authorization": "Bearer " + self.config.get("access_token", "")},
                             timeout=15)
            if r.status_code == 200:
                j = r.json()
                name = j.get("owner", {}).get("user", {}).get("displayName", "")
                return True, f"连接成功（{name}）" if name else "连接成功"
            return False, f"连接失败 (HTTP {r.status_code}): {r.text[:120]}"
        except Exception as e:
            return False, f"连接异常: {e}"

    def upload(self, local_path, remote_dir=""):
        ok, missing = self.validate()
        if not ok:
            raise RuntimeError("缺少必填字段: " + ", ".join(missing))
        size = os.path.getsize(local_path)
        if size > SIMPLE_LIMIT:
            raise RuntimeError(f"文件 {size/1024/1024:.1f}MB 超过单次 PUT 上限 250MB，需用分片上传会话")

        base = self._remote_path(remote_dir)
        filename = os.path.basename(local_path)
        # URL 路径段各自编码（保留 / ）
        path = ("/".join(p for p in [base, filename] if p))
        encoded = "/".join(_url_quote(seg) for seg in path.split("/"))
        url = f"{GRAPH}/me/drive/root:/{encoded}:/content"

        with open(local_path, "rb") as f:
            r = requests.put(url, headers=self._headers(), data=f, timeout=600)
        if r.status_code == 201:
            return path
        if r.status_code in (401, 403):
            raise RuntimeError("鉴权失败，access_token 可能已过期，请重新获取")
        if r.status_code == 413:
            raise RuntimeError("文件过大，请使用分片上传")
        raise RuntimeError(f"上传失败 (HTTP {r.status_code}): {r.text[:200]}")


def _url_quote(seg):
    from urllib.parse import quote
    return quote(seg, safe="")
