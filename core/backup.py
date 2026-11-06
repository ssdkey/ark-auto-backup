"""备份核心模块 - 流式压缩，低内存低CPU占用
关键设计：
- 使用 ZIP_STORED（不压缩），速度最快、CPU占用最低；
  方舟存档多为已压缩二进制数据，再压缩收益小。
- 逐个文件写入 zip，不一次性读入内存，内存占用极小。
"""
import os
import zipfile
from datetime import datetime
from pathlib import Path


PREFIX = "ARK_backup_"


class BackupTask:
    """单个备份任务（对应 config.json 的一个 task）"""

    def __init__(self, name, src_dir, backup_dir):
        self.name = name or "未命名任务"
        self.src_dir = str(src_dir)
        self.backup_dir = str(backup_dir)

    def _safe_name(self):
        """生成安全文件名"""
        return "".join(c if c.isalnum() or c in "_- " else "_" for c in self.name).strip()

    def run(self, progress=None) -> str:
        """执行备份，返回生成的备份文件完整路径。
        progress: 可选回调 progress(done_files, total_files)
        """
        src = Path(self.src_dir)
        if not src.exists():
            raise FileNotFoundError(f"备份源目录不存在: {self.src_dir}")

        os.makedirs(self.backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self.backup_dir, f"{PREFIX}{self._safe_name()}_{stamp}.zip")

        # 先收集文件列表，用于进度显示（只记录路径字符串，不读内容）
        files = []
        for root, _, fs in os.walk(src):
            for f in fs:
                files.append(os.path.join(root, f))

        # 流式写入：每个文件打开->写入->关闭，内存占用恒定
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
            done = 0
            for fp in files:
                rel = os.path.relpath(fp, src)
                # ZIP_STORED 模式直接写，绕过压缩，省 CPU
                zf.write(fp, rel, compress_type=zipfile.ZIP_STORED)
                done += 1
                if progress and done % 10 == 0:
                    progress(done, len(files))
        return out


def make_backup(name, src_dir, backup_dir, progress=None) -> str:
    """便捷入口"""
    return BackupTask(name, src_dir, backup_dir).run(progress)


def _safe_task_name(name):
    """与 BackupTask._safe_name 一致：把不可用于文件名的字符替换成下划线"""
    return "".join(c if c.isalnum() or c in "_- " else "_" for c in (name or "")).strip()


def list_backups(backup_dir, name=None) -> list:
    """列出某目录下所有备份文件，按修改时间升序（最早在前）。
    返回 [(路径, 大小字节, 时间戳), ...]
    name: 可选，按任务名过滤（与生成文件名使用同一规则 _safe_task_name，
          确保含特殊字符的任务名也能正确匹配）。
    """
    backup_dir = str(backup_dir)
    if not os.path.isdir(backup_dir):
        return []
    # 用与文件名一致的规则处理 name，避免特殊字符任务名匹配失败
    match_token = None
    if name:
        token = _safe_task_name(name)
        if token:  # 任务名全被净化成空时不强制过滤
            match_token = (PREFIX + token + "_")
    rows = []
    for f in os.listdir(backup_dir):
        full = os.path.join(backup_dir, f)
        if os.path.isfile(full) and f.startswith(PREFIX) and f.endswith(".zip"):
            if match_token is None or match_token in f:
                rows.append((full, os.path.getsize(full), os.path.getmtime(full)))
    rows.sort(key=lambda r: r[2])  # 早期在前
    return rows
