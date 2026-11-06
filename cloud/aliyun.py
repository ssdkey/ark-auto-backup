"""阿里云盘上传插件（Open API，open-api.alipan.com，新一代 aDrive 协议）
认证：Authorization: Bearer <access_token>。支持用 refresh_token 刷新 access_token。
流程：create 获取上传地址(upload_url) -> 直接 PUT 分片 -> complete 完成。
注意：刷新 access_token 需在阿里云盘开放平台注册应用得到 client_id / client_secret；
若没有 client_id/secret 则只能用已拿到的有效 access_token 直接上传。
"""
import os

import requests

from .base import CloudUploader, Field, register

API = "https://openapi.alipan.com"
PART = 4 * 1024 * 1024   # 4MB


@register
class AliyunUploader(CloudUploader):
    key = "aliyun"
    name = "阿里云盘"
    desc = "阿里云盘个人云盘，基于 Open API。需 access_token（或 refresh_token+应用凭据自动刷新）。"

    fields = [
        Field("refresh_token", "refresh_token", placeholder="粘贴 refresh_token（可自动换新 access_token）", secret=True),
        Field("access_token", "access_token", placeholder="有效 access_token（二选一，优先自动刷新）", secret=True, required=False),
        Field("drive_id", "drive_id", placeholder="云盘空间 ID"),
        Field("client_id", "client_id", placeholder="开放平台应用 client_id（用于刷新 token）", required=False),
        Field("client_secret", "client_secret", placeholder="开放平台应用 client_secret", secret=True, required=False),
        Field("remote_dir", "云端目录", placeholder="留空=根目录", required=False),
    ]

    def _headers(self):
        return {"Authorization": "Bearer " + self._token(),
                "Content-Type": "application/json"}

    def _token(self):
        """优先已存 access_token，否则尝试用 refresh_token 刷新取得。"""
        at = self.config.get("access_token", "")
        if at:
            return at
        rt = self.config.get("refresh_token", "")
        cid = self.config.get("client_id", "")
        cs = self.config.get("client_secret", "")
        if not (rt and cid and cs):
            raise RuntimeError("需要有效 access_token；或用 refresh_token+client_id+client_secret 自动刷新")
        r = requests.post(f"{API}/oauth/access_token", json={
            "grant_type": "refresh_token",
            "refresh_token": rt,
            "client_id": cid,
            "client_secret": cs,
        }, timeout=20)
        j = r.json()
        at = j.get("access_token")
        if not at:
            raise RuntimeError(f"刷新 token 失败: {j.get('error_description') or j.get('error')}")
        self.config["access_token"] = at
        if j.get("refresh_token"):
            self.config["refresh_token"] = j["refresh_token"]
        return at

    def _root(self, remote_dir):
        r = remote_dir or self.config.get("remote_dir", "")
        return r.strip("/") or None

    def test_connection(self):
        ok, missing = self.validate()
        if not ok:
            return False, "缺少必填字段: " + ", ".join(missing)
        try:
            r = requests.get(f"{API}/user/getDriveInfo",
                             headers={"Authorization": "Bearer " + self._token()},
                             timeout=15)
            j = r.json()
            if j.get("user_id") or j.get("name") or j.get("code") == 0:
                return True, "连接成功"
            return False, f"连接失败: {j.get('message') or j.get('code')}"
        except Exception as e:
            return False, f"连接异常: {e}"

    def _create_file(self, drive_id, parent_id, name):
        # 单分片（小文件）或按需分片；此处用固定 1 片，>4MB 拆多片
        size = 0  # 由调用方填
        body = {
            "drive_id": drive_id,
            "parent_file_id": parent_id,
            "name": name,
            "type": "file",
            "check_name_mode": "auto_rename",
            "part_info_list": [{"part_number": 1}],
        }
        r = requests.post(f"{API}/adrive/v1.0/openFile/create",
                          headers=self._headers(), json=body, timeout=60)
        return r.json()

    def _complete(self, drive_id, file_id, upload_id):
        r = requests.post(f"{API}/adrive/v1.0/openFile/complete",
                          headers=self._headers(),
                          json={"drive_id": drive_id, "file_id": file_id,
                                "upload_id": upload_id},
                          timeout=60)
        return r.json()

    def upload(self, local_path, remote_dir=""):
        ok, missing = self.validate()
        if not ok:
            raise RuntimeError("缺少必填字段: " + ", ".join(missing))
        drive_id = self.config.get("drive_id", "")
        parent = self._root(remote_dir) or "root"
        name = os.path.basename(local_path)

        # 分片计划
        size = os.path.getsize(local_path)
        nparts = max(1, (size + PART - 1) // PART)
        create_body = {
            "drive_id": drive_id,
            "parent_file_id": parent,
            "name": name,
            "type": "file",
            "check_name_mode": "auto_rename",
            "part_info_list": [{"part_number": i} for i in range(1, nparts + 1)],
        }
        r = requests.post(f"{API}/adrive/v1.0/openFile/create",
                          headers=self._headers(), json=create_body, timeout=60)
        j = r.json()
        if "file_id" not in j or "upload_id" not in j:
            raise RuntimeError(f"创建上传失败: {j.get('code') or j.get('message')}")
        file_id, upload_id = j["file_id"], j["upload_id"]
        parts = j.get("part_info_list") or []
        if not parts:
            raise RuntimeError("未返回上传地址 part_info_list")

        # 逐分片 PUT 到预签名 upload_url（无需再带 token）
        with open(local_path, "rb") as fh:
            for p in parts:
                pn = p["part_number"]
                url = p["upload_url"]
                # 定位该分片的字节区间
                start = (pn - 1) * PART
                fh.seek(start)
                data = fh.read(PART)
                rr = requests.put(url, data=data, timeout=600)
                if rr.status_code not in (200, 201, 204):
                    raise RuntimeError(f"分片 {pn} 上传失败 (HTTP {rr.status_code})")

        cj = self._complete(drive_id, file_id, upload_id)
        if "file_id" not in cj:
            raise RuntimeError(f"完成上传失败: {cj.get('code') or cj.get('message')}")
        remote = "/".join([parent if parent != "root" else "", name]).lstrip("/")
        return remote
