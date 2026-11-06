"""一键恢复模块
安全设计：
- 恢复前自动备份当前存档（安全网），出错可回退
- 返回执行前备份路径，便于用户反悔时恢复
- 恢复过程流式解压，低内存占用
"""
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from .backup import make_backup


def snapshot_current(src_dir, safety_dir) -> str:
    """恢复前的安全网：把当前存档临时备份到 safety_dir，返回其路径"""
    os.makedirs(safety_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety_zip = os.path.join(safety_dir, f"_pre_restore_{stamp}.zip")
    src = Path(src_dir)
    if src.exists():
        with zipfile.ZipFile(safety_zip, "w", zipfile.ZIP_STORED) as zf:
            for root, _, files in os.walk(src):
                for f in files:
                    fp = os.path.join(root, f)
                    zf.write(fp, os.path.relpath(fp, src))
    return safety_zip


def restore_backup(zip_path, target_dir, do_snapshot=True) -> dict:
    """把备份 zip_path 恢复到 target_dir。
    返回 {'restored': bool, 'message': str, 'snapshot': str|None}
    """
    if not os.path.isfile(zip_path):
        return {"restored": False, "message": f"备份文件不存在: {zip_path}", "snapshot": None}

    snapshot = None
    safety_dir = os.path.join(os.path.dirname(target_dir), "_restore_safety")
    if do_snapshot and os.path.isdir(target_dir):
        snapshot = snapshot_current(target_dir, safety_dir)

    # 使用中间目录，先完整解压成功再切换，避免半途损坏原目录
    tmp = target_dir + ".restoringtmp"
    if os.path.isdir(tmp):
        shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)
        # 解压成功，替换目标目录
        if os.path.isdir(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)
        shutil.move(tmp, target_dir)
    except Exception as e:  # noqa: BLE001
        shutil.rmtree(tmp, ignore_errors=True)
        return {"restored": False, "message": f"恢复失败: {e}", "snapshot": snapshot}

    return {"restored": True, "message": "恢复成功", "snapshot": snapshot}
