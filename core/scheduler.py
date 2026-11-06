"""Windows 计划任务封装
通过 schtasks.exe 注册/查询/删除每日自动备份任务。
任务执行体为「方舟自动备份工具.exe --backup」，程序不常驻，只在计划时刻运行。
"""
import os
import subprocess
import sys

TASK_NAME = "方舟自动备份工具"


def _exe_path():
    """获取要交给计划任务执行的程序路径：
    - 冻结(exe)：当前 exe
    - 源码：当前 python + app.py
    返回可安全放入 schtasks 命令的原始字符串路径。
    """
    if getattr(sys, "frozen", False):
        return sys.executable
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根
    py = sys.executable
    return f'"{py}" "{os.path.join(here, "app.py")}"'


def _run(cmd):
    """执行命令并返回 (code, stdout+stderr)"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                           timeout=30)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return -1, str(e)


def register_task(time_str="03:00"):
    """注册每日计划任务。
    time_str 形如 'HH:MM'。返回 (ok, message)。
    """
    exe = _exe_path()
    # schtasks 命令行：/TR 里含引号和空格需转义
    task_run = f"{exe} --backup"
    cmd = [
        "schtasks", "/Create", "/F", "/TN", TASK_NAME,
        "/SC", "DAILY", "/ST", time_str,
        "/TR", task_run,
    ]
    code, out = _run(cmd)
    detail = out.strip().replace("\r\n", " ").replace("\n", " ") or "无输出"
    if code == 0:
        return True, f"已注册每日 {time_str} 自动备份"
    return False, f"注册失败: {detail}"


def query_task():
    """查询任务是否存在。返回 (exists, message)"""
    cmd = ["schtasks", "/Query", "/TN", TASK_NAME]
    code, out = _run(cmd)
    if code == 0:
        return True, "已注册"
    return False, "未注册"


def delete_task():
    """删除计划任务。返回 (ok, message)"""
    cmd = ["schtasks", "/Delete", "/F", "/TN", TASK_NAME]
    code, out = _run(cmd)
    detail = out.strip().replace("\r\n", " ").replace("\n", " ") or "无输出"
    if code == 0:
        return True, "已取消自动备份"
    return False, f"取消失败: {detail}"


def apply_schedule(enabled, time_str):
    """根据界面开关同步计划任务状态。返回 (ok, message)"""
    exists, _ = query_task()
    if enabled:
        if exists:
            # 已存在则删除重建（时间可能变更）
            delete_task()
        return register_task(time_str)
    else:
        if exists:
            return delete_task()
        return True, "当前未启用自动备份"
