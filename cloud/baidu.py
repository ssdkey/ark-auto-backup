"""百度网盘上传插件（PCS superfile2 分片上传）
认证：access_token 作 URL 查询参数（PCS 特有），无 refresh 环节。
协议：precreate -> 逐分片 upload(4MB) -> create。
block_list = 每个 4MB 分片的 md5 组成的 JSON 数组字符串。
"""
import hashlib
import json
import os

import requests

from .base import CloudUploader, Field, register

PCS = "https://d.pcs.baidu.com/rest/2.0/pcs/superfile2"
BLOCK = 4 * 1024 * 1024   # 4MB


def _md5_chunks(path):
    """返回 [(start, end, md5), ...]，每块 4MB"""
    size = os.path.getsize(path)
    chunks = []
    with open(path, "rb") as f:
        off = 0
        while off < size:
            data = f.read(BLOCK)
            chunks.append((off, off + len(data), hashlib.md5(data).hexdigest()))
            off += len(data)
    return chunks, size


@register
class BaiduUploader(CloudUploader):
    key = "baidu"
    name = "百度网盘"
    desc = "百度网盘个人存储，基于开放平台 PCS 分片上传。Token 从百度开放平台 OAuth 获取。"

    fields = [
        Field("access_token", "access_token", placeholder="粘贴百度 access_token", secret=True),
        Field("remote_dir", "云端路径", placeholder="/apps/ARK_BACKUP（建议以 /apps/ 开头）", required=False),
    ]

    def _params(self, remote_dir):
        return {
            "access_token": self.config.get("access_token", ""),
            "type": "tmpfile",
            "path": self._base(remote_dir or self.config.get("remote_dir", "")),
        }

    def _base(self, remote_dir):
        p = (remote_dir or self.config.get("remote_dir", "")) or "/apps/ARK_BACKUP"
        if not p.startswith("/"):
            p = "/" + p
        return p

    def _request(self, method, params, files=None, data=None, timeout=600):
        r = requests.request(method, PCS, params=params, files=files, data=data,
                             timeout=timeout)
        return r.json()

    def test_connection(self):
        ok, missing = self.validate()
        if not ok:
            return False, "缺少必填字段: " + ", ".join(missing)
        try:
            r = requests.get("https://pan.baidu.com/rest/2.0/xpan/nas",
                             params={"method": "uinfo",
                                     "access_token": self.config.get("access_token", "")},
                             timeout=15)
            j = r.json()
            if j.get("errno") == 0 and j.get("baidu_name"):
                return True, f"连接成功（{j['baidu_name']}）"
            return False, f"连接失败: {j.get('errmsg') or j.get('errno')}"
        except Exception as e:
            return False, f"连接异常: {e}"

    def upload(self, local_path, remote_dir=""):
        ok, missing = self.validate()
        if not ok:
            raise RuntimeError("缺少必填字段: " + ", ".join(missing))

        path = self._base(remote_dir or self.config.get("remote_dir", ""))
        if path.endswith("/"):
            path = path.rstrip("/") + "/" + os.path.basename(local_path)
        else:
            path = path + "/" + os.path.basename(local_path)

        chunks, size = _md5_chunks(local_path)
        block_list = json.dumps([c[2] for c in chunks])

        # 1) precreate
        params = self._params(remote_dir)
        params.update({"method": "precreate", "path": path, "size": size,
                       "block_list": block_list, "autoinit": "1"})
        j = self._request("GET", params)
        if j.get("errno") != 0:
            raise RuntimeError(f"预创建失败: {j.get('errmsg') or j.get('errno')}")
        uploadid = j["uploadid"]

        # 2) 逐分片上传
        for i, (start, end, md5) in enumerate(chunks):
            with open(local_path, "rb") as f:
                f.seek(start)
                data = f.read(end - start)
            p = self._params(remote_dir)
            p.update({"method": "upload", "path": path, "uploadid": uploadid,
                      "partseq": i})
            r = requests.post(PCS, params=p,
                              files={"file": (os.path.basename(local_path), data)},
                              timeout=600)
            j = r.json()
            if j.get("errno") != 0:
                raise RuntimeError(f"分片 {i} 上传失败: {j.get('errmsg') or j.get('errno')}")

        # 3) create
        params = self._params(remote_dir)
        params.update({"method": "create", "path": path, "size": size,
                       "uploadid": uploadid, "block_list": block_list,
                       "autoinit": "1"})
        j = self._request("GET", params)
        if j.get("errno") != 0:
            raise RuntimeError(f"完成上传失败: {j.get('errmsg') or j.get('errno')}")
        return path
