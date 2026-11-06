"""清洗策略模块
支持 count / days / both 三种模式，配置驱动。
安全设计：
- min_keep 安全下限：任何策略下备份数 ≤ min_keep 时绝不删除
- 删除前返回待删清单（preview模式），供 UI 前端确认后再执行
"""
import os
import time

from .backup import list_backups


def plan_clean(backup_dir, retention, name=None):
    """计算应删除的备份清单（不实际删除，供预览）。
    retention: dict, 键含 mode / keep_count / keep_days / min_keep
    返回 (to_delete列表[(path,size,time)], 现有总数)
    to_delete 为空表示无需清理（例如数量不足）。
    """
    mode = retention.get("mode", "count")
    keep_count = int(retention.get("keep_count", 10))
    keep_days = int(retention.get("keep_days", 30))
    min_keep = int(retention.get("min_keep", 5))

    zips = list_backups(backup_dir, name)  # 升序，最早在前
    total = len(zips)
    if total == 0:
        return [], 0

    to_delete = []

    if mode == "count":
        # 超过 keep_count 的部分删最旧，但留出 min_keep 兜底
        exceed = total - keep_count
        max_del = total - min_keep  # 最多能删这么多（保住 min_keep）
        del_n = max(0, min(exceed, max_del))
        to_delete = zips[:del_n]

    elif mode == "days":
        cutoff = time.time() - keep_days * 86400
        expired = [z for z in zips if z[2] < cutoff]
        max_del = total - min_keep
        to_delete = expired[:max_del]

    elif mode == "both":
        cutoff = time.time() - keep_days * 86400
        exceed = total - keep_count
        max_del = total - min_keep
        candidates = [z for z in zips if z[2] < cutoff]
        # 同时超出天数 与 份数 才删
        if exceed > 0 and candidates:
            del_n = max(0, min(exceed, len(candidates), max_del))
            to_delete = candidates[:del_n]

    return to_delete, total


def clean(backup_dir, retention, name=None, dry_run=False):
    """执行清洗。dry_run=True 仅返回清单不删除。
    返回 (deleted_count, kept_total, to_delete清单)
    """
    to_delete, total = plan_clean(backup_dir, retention, name)
    if dry_run:
        return 0, total - len(to_delete), to_delete
    for full, _, _ in to_delete:
        try:
            os.remove(full)
        except OSError:
            pass
    return len(to_delete), total - len(to_delete), to_delete
