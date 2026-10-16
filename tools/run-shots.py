#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run-shots.py -- 按顺序出 S2..S5：建 job → 渲染 → 抽帧 → 存末帧锚 → 压 QQ 版。

为什么用 Python 而不是 PowerShell：PowerShell 5.1 按 ANSI 读 .ps1，脚本里的中文路径
会被读坏，python 打不开文件（2026-10-16 连踩两次）。Python 处理 UTF-8 路径没问题。

用法:
  python run-shots.py                 # 跑全部
  python run-shots.py --only C02      # 只跑某一镜（名字里含 C02 的）
"""
import argparse
import importlib.util
import io
import json
import os
import subprocess
import sys
import time

FLOW = r"$env:DSH_AI\out\flow"
WAN = r"$env:DSH_AI\Wan2GP"
WGP = os.path.join(WAN, "env_venv", "Scripts", "python.exe")
FFMPEG = os.path.join(WAN, "ffmpeg_bins", "ffmpeg.exe")
MAT = r"$env:DSH_WORKSPACE\AI视频流程\_素材-死芒苇草"
TEMPLATE = os.path.join(FLOW, "_base-job-template.json")
if not os.path.exists(TEMPLATE):                  # 回退：旧实验目录
    TEMPLATE = os.path.join(FLOW, "s4-burn-g", "job.json")
LOG = os.path.join(FLOW, "_shots.log")

_spec = importlib.util.spec_from_file_location("h3shot", r"$env:DSH_HOME\comfy-tools\h3-shot.py")

REFS = [
    os.path.join(MAT, r"死芒\立绘\立绘_死芒_1.png"),
    os.path.join(MAT, r"焰影苇草\立绘\立绘_焰影苇草_1.png"),
    os.path.join(FLOW, r"261016-SMWC-S01-P01-t02\out\261016-SMWC-S01-P01-t02.jpg"),
]

SHOTS = [
    ("261016-SMWC-S01-C02-t01", os.path.join(MAT, "prompt-S2.txt"), 73, "261016-SMWC-S01-C01-t02"),
    ("261016-SMWC-S01-C03-t01", os.path.join(MAT, "prompt-S3.txt"), 145, "261016-SMWC-S01-C02-t01"),
    ("261016-SMWC-S01-C04-t01", os.path.join(MAT, "prompt-S4.txt"), 192, "261016-SMWC-S01-C03-t01"),
    ("261016-SMWC-S01-C05-t01", os.path.join(MAT, "prompt-S5.txt"), 217, "261016-SMWC-S01-C04-t01"),
]

STD = {
    "model_type": "minimax_h3_ref2va_pruned_nvfp4",
    "resolution": "1344x768",
    "num_inference_steps": 40,
    "sample_solver": "euler",
    "guidance_phases": 2,
    "guidance_scale": 5,
    "video_prompt_type": "I",
    "multi_prompts_gen_type": "FG",
    "image_refs_relative_size": 100,
    "seed": 20291012,
    "image_mode": 0,
}


def say(m):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), m)
    print(line, flush=True)
    with io.open(LOG, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def last_frame(shot):
    for cand in (os.path.join(FLOW, shot, "_末帧-供锚定.png"),):
        if os.path.exists(cand):
            return cand
    fd = os.path.join(FLOW, shot, "_check", "frames")
    if os.path.isdir(fd):
        names = sorted(f for f in os.listdir(fd) if f.lower().endswith(".png"))
        if names:
            return os.path.join(fd, names[-1])
    return None


def build_job(name, prompt_file, frames, anchor):
    with io.open(TEMPLATE, encoding="utf-8") as f:
        job = json.load(f)
    job.update(STD)
    job["output_filename"] = name
    job["video_length"] = frames
    with io.open(prompt_file, encoding="utf-8") as f:
        job["prompt"] = f.read()
    job["image_refs"] = REFS
    if anchor:
        job["image_start"] = anchor
        job["image_prompt_type"] = "S"
    d = os.path.join(FLOW, name)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "job.json")
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(job, f, ensure_ascii=False, indent=1)
    with open(p, "rb") as f:
        assert f.read(3).hex() != "efbbbf", "BOM!"
    return p, d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    a = ap.parse_args()

    for ref in REFS:
        if not os.path.exists(ref):
            raise SystemExit("参考图缺失: %s" % ref)

    say("shots queue start")
    for name, pf, frames, anchor_shot in SHOTS:
        if a.only and a.only not in name:
            continue
        if not os.path.exists(pf):
            say("FAIL prompt missing: %s" % pf)
            continue
        anchor = last_frame(anchor_shot) if anchor_shot else None
        if anchor_shot and not anchor:
            say("WARN anchor missing for %s (from %s)" % (name, anchor_shot))
        job_path, d = build_job(name, pf, frames, anchor)
        out = os.path.join(d, "video")
        os.makedirs(out, exist_ok=True)
        say("BEGIN %s  frames=%d  anchor=%s" % (name, frames, os.path.basename(anchor) if anchor else "none"))
        t0 = time.time()
        r = subprocess.run([WGP, "wgp.py", "--process", job_path, "--output-dir", out],
                           cwd=WAN, capture_output=True, text=True, encoding="utf-8", errors="replace")
        el = int(time.time() - t0)
        with io.open(os.path.join(d, "_render.log"), "w", encoding="utf-8", newline="\n") as f:
            f.write((r.stdout or "") + "\n---STDERR---\n" + (r.stderr or ""))
        mp4s = [f for f in os.listdir(out) if f.lower().endswith(".mp4")] if os.path.isdir(out) else []
        if not mp4s:
            say("FAIL no mp4: %s rc=%s %ss" % (name, r.returncode, el))
            continue
        mp4 = os.path.join(out, sorted(mp4s)[-1])
        say("DONE  %s  %ss  %.2f MB" % (name, el, os.path.getsize(mp4) / 1e6))

        # 抽帧 + 存末帧锚
        sys.path.insert(0, r"$env:DSH_HOME\comfy-tools")
        import flow  # noqa: E402
        chk = os.path.join(d, "_check")
        os.makedirs(chk, exist_ok=True)
        frames_dir, dur = flow.extract_frames(mp4, chk)
        names = sorted(f for f in os.listdir(frames_dir) if f.lower().endswith(".png"))
        if names:
            import shutil
            shutil.copyfile(os.path.join(frames_dir, names[-1]), os.path.join(d, "_末帧-供锚定.png"))
            say("  anchor saved: %s (%d frames / %.1fs)" % (names[-1], len(names), dur))

        # QQ 压缩版
        small = os.path.join(out, name + "-small.mp4")
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", mp4,
                        "-vf", "scale=1280:-2", "-c:v", "libx264", "-crf", "26",
                        "-preset", "medium", "-c:a", "copy", small], capture_output=True)
        if os.path.exists(small):
            say("  small: %.2f MB" % (os.path.getsize(small) / 1e6))
    say("shots queue end")


if __name__ == "__main__":
    main()
