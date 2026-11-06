"""WebDAV / 坚果云 上传插件
支持任意标准 WebDAV 服务（坚果云 dav.jianguoyun.com/dav/ 及自建等）。
协议用 requests 直接实现：MKCOL 建目录、PUT 上传、PROPFIND 校验。
"""
import os
import posixpath

import requests

from .base import CloudUploader, Field, register


@register
class WebDAVUploader(CloudUploader):
    key = "webdav"
    name = "坚果云 / WebDAV"
    desc = "支持坚果云(https://dav.jianguoyun.com/dav/)及任意标准 WebDAV 服务器。"

    fields = [
        Field("url", "服务器地址", placeholder="https://dav.jianguoyun.com/dav/ARK/"),
        Field("username", "账号", placeholder="坚果云邮箱 / 登录名"),
        Field("password", "应用密码", placeholder="坚果云需使用应用密码(非登录密码)", secret=True),
        Field("remote_dir", "云端目录", placeholder="留空=服务器地址即根目录", required=False),
    ]

    def _base(self, remote_dir=""):
        """拼接最终远程根目录 URL"""
        if remote_dir:
            return posixpath.join(self.config.get("url", "").rstrip("/"),
                                  remote_dir.strip("/"))
        return self.config.get("url", "").rstrip("/") or "/"

    def _session(self):
        s = requests.Session()
        s.auth = (self.config.get("username", ""), self.config.get("password", ""))
        s.headers.update({"User-Agent": "ArkBackup/1.0"})
        return s

    def _mkcol(self, session, url):
        """递归创建目录（WebDAV 不会自动建父目录）"""
        # 拆出相对路径逐级创建
        parsed = self.config.get("url", "").rstrip("/")
        if not url.startswith(parsed):
            parsed = url.split("/")[0] + "//" + url.split("/")[2]
        rel = url[len(parsed):].strip("/")
        if not rel:
            return
        cur = parsed
        for part in rel.split("/"):
            cur = posixpath.join(cur, part)
            r = session.request("MKCOL", cur)
            if r.status_code in (201, 405):   # 201 已建 / 405 已存在
                continue
            # 409 表示父目录不存在，尝试继续（上面已递归）

    def test_connection(self):
        ok, missing = self.validate()
        if not ok:
            return False, "缺少必填字段: " + ", ".join(missing)
        try:
            with self._session() as s:
                r = s.request("PROPFIND", self._base(), headers={"Depth": "0"},
                              timeout=15)
            if r.status_code in (200, 207, 301):
                return True, "连接成功"
            return False, f"连接失败 (HTTP {r.status_code})"
        except Exception as e:
            return False, f"连接异常: {e}"

    def upload(self, local_path, remote_dir=""):
        """上传 local_path 到云端 remote_dir 下，返回云端 URL。
        remote_dir 省略时使用插件配置里的 remote_dir。
        """
        ok, missing = self.validate()
        if not ok:
            raise RuntimeError("缺少必填字段: " + ", ".join(missing))

        target_dir = self._base(remote_dir or self.config.get("remote_dir", ""))
        if not target_dir:
            raise RuntimeError("未能确定云端目标目录（请检查服务器地址）")
        filename = os.path.basename(local_path)

        with self._session() as s:
            self._mkcol(s, target_dir)
            dest = posixpath.join(target_dir, filename)
            with open(local_path, "rb") as f:
                r = s.put(dest, data=f, timeout=600)
            if r.status_code not in (200, 201, 204):
                raise RuntimeError(f"上传失败 (HTTP {r.status_code}): {r.text[:200]}")
        return dest
