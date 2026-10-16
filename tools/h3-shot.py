#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""h3-shot.py -- 统一入口：用 H3 出一镜（视频，192帧/8s），或出一张静帧（--still）。

为什么要有它：每出一镜都要设同一套参数（model_type / 分辨率 / 步数 / seed / 参考图），
散在各处改一次就容易漂。这里把"标准件参数"集中写死，只暴露真正要变的：
  --name / --prompt-file / --refs / [--start-image] / [--frames] / [--seed] / [--still]

命名规范（2026-10-16 定）：<立项日>-<题材>-S<场>-C<镜>-t<试>
  例：261016-SMWC-S01-C01-t02

用法:
  python h3-shot.py --name 261016-SMWC-S01-C01-t02 --prompt-file p.txt --refs a.png,b.png
  python h3-shot.py --name ... --prompt-file p.txt --refs a.png --start-image prev.png
  python h3-shot.py --name ... --prompt-file p.txt --refs a.png --still
"""
import argparse
import io
import json
import os

FLOW = r"$env:DSH_AI\out\flow"
TEMPLATE = os.path.join(FLOW, "_base-job-template.json")
if not os.path.exists(TEMPLATE):                  # 回退：旧实验目录
    TEMPLATE = os.path.join(FLOW, "s4-burn-g", "job.json")

STD = {
    "model_type": "minimax_h3_ref2va_pruned_nvfp4",  # nvfp4 编码器档（2026-10-16 起为默认）
    "resolution": "1344x768",
    "video_length": 192,
    "num_inference_steps": 40,
    "sample_solver": "euler",
    "guidance_phases": 2,
    "guidance_scale": 5,
    "video_prompt_type": "I",
    "multi_prompts_gen_type": "FG",
    "image_refs_relative_size": 100,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--refs", required=True)
    ap.add_argument("--start-image", default=None)
    ap.add_argument("--frames", type=int, default=None)
    ap.add_argument("--seed", type=int, default=20291012)
    ap.add_argument("--still", action="store_true", help="出单张静帧（image_mode=1）")
    a = ap.parse_args()

    with io.open(TEMPLATE, encoding="utf-8") as f:
        job = json.load(f)

    job.update(STD)
    job["output_filename"] = a.name
    job["seed"] = a.seed

    with io.open(a.prompt_file, encoding="utf-8") as f:
        job["prompt"] = f.read()

    refs = [r.strip() for r in a.refs.split(",") if r.strip()]
    for r in refs:
        if not os.path.exists(r):
            raise SystemExit("参考图不存在: %s" % r)
    job["image_refs"] = refs

    if a.still:
        job["image_mode"] = 1
    else:
        job["image_mode"] = 0
        if a.frames:
            job["video_length"] = a.frames

    if a.start_image:
        if not os.path.exists(a.start_image):
            raise SystemExit("首帧不存在: %s" % a.start_image)
        job["image_start"] = a.start_image
        job["image_prompt_type"] = "S"
        job["image_mode"] = 0

    d = os.path.join(FLOW, a.name)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "job.json")
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(job, f, ensure_ascii=False, indent=1)

    with open(p, "rb") as f:
        head = f.read(3)
    assert head.hex() != "efbbbf", "job.json 带了 BOM"
    print("job: %s" % p)
    print("  mode      = %s" % ("STILL (image_mode=1)" if a.still else ("video + start-image" if a.start_image else "video")))
    print("  frames    = %s" % job.get("video_length"))
    print("  steps/seed= %s / %s" % (job["num_inference_steps"], job["seed"]))
    print("  refs      = %d 张" % len(refs))
    for r in refs:
        print("    - %s" % os.path.basename(r))
    if a.start_image:
        print("  start_img = %s" % os.path.basename(a.start_image))
    print("  prompt    = %d 字符 / dd=%d 词" % (
        len(job["prompt"]),
        len(job["prompt"].split("detailed_description:", 1)[-1].split("overall_soundscape:", 1)[0].split()),
    ))
    print("  BOM       = %s (ok)" % head.hex())


if __name__ == "__main__":
    main()
