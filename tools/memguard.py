#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""memguard.py -- 大型渲染期间临时停掉 Mem Reduct，渲染完还原（2026-10-12）

为什么：Mem Reduct 会周期性裁剪各进程的工作集。H3 把 20B 权重钉在保留内存里，
一被剪掉模型就得重新从盘上读，渲染会莫名变慢。

原则：**只临时停、不碰任何自启动项**；本来没开就不开，本来开着就按原样拉回来。

两个实测踩出来的坑（别改回去）：
  1. 杀必须走 **pwsh (PS7)**：`taskkill.exe` / `powershell.exe`(5.1) / python `os.kill` 三条路全被 `Access is denied`；只有 pwsh 能杀。别改回去。
  2. Mem Reduct 平时是由计划任务 `MemReductStart` 以 **RunLevel=Highest（提权）** 启动的。
     所以拉回来也必须走同一个计划任务，否则会把一个非提权的副本塞回他机器上。

CLI:
  python memguard.py status
  python memguard.py pause
  python memguard.py resume
"""
import os
import subprocess
import sys

EXE = r"D:\mem_reduct\Mem Reduct\memreduct.exe"
IMAGE = "memreduct.exe"
TASK = "MemReductStart"

_state = {"touched": False, "was_running": False}


def _ps(cmd):
    return subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True, text=True, errors="replace")


def running():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + IMAGE, "/NH"],
                       capture_output=True, text=True, errors="replace")
    return IMAGE.lower() in (r.stdout or "").lower()


def pause(verbose=True):
    """停掉 Mem Reduct。返回 True=真停了。幂等。"""
    if _state["touched"]:
        return False
    _state["touched"] = True
    if not running():
        _state["was_running"] = False
        if verbose:
            print("[memguard] Mem Reduct 本来就没开，跳过")
        return False
    _state["was_running"] = True
    r = _ps("Stop-Process -Name memreduct -Force -ErrorAction Stop; 'ok'")
    gone = not running()
    if verbose:
        msg = "OK" if gone else (r.stderr or r.stdout or "").strip()[:200]
        print("[memguard] 停掉 Mem Reduct: %s" % msg)
    return gone


def resume(force=False, verbose=True):
    """把 Mem Reduct 拉回来（走原来的计划任务，保持提权属性）。"""
    if not force and not _state["touched"]:
        return False
    if not force and not _state["was_running"]:
        _state["touched"] = False
        if verbose:
            print("[memguard] 本来就没开，不拉起")
        return False
    _state["touched"] = False
    if running():
        if verbose:
            print("[memguard] 已经在跑了，不重复拉起")
        return False
    r = _ps("Start-ScheduledTask -TaskName '%s'; 'ok'" % TASK)
    if not running():
        if os.path.exists(EXE):
            subprocess.Popen([EXE, "-minimized"], close_fds=True)
            if verbose:
                print("[memguard] 计划任务没拉起，已直接启动 exe（注：可能是非提权副本）")
        else:
            if verbose:
                print("[memguard] 拉不起来: %s" % (r.stderr or "").strip()[:200])
        return running()
    if verbose:
        print("[memguard] 已拉回 Mem Reduct（走计划任务 %s，提权属性不变）" % TASK)
    return True


def main():
    act = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    if act == "status":
        print("[memguard] Mem Reduct %s" % ("在跑" if running() else "没在跑"))
    elif act == "pause":
        pause()
        print("[memguard] 现在: %s" % ("还在" if running() else "已停"))
    elif act == "resume":
        resume(force=True)
        print("[memguard] 现在: %s" % ("在跑" if running() else "没在跑"))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
