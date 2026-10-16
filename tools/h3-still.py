#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""h3-still.py -- 用 MiniMax H3 生成一张静帧（image_mode=1，文生图模式）。

为什么要它：出片用的是 H3，照片道具**也应该用同一个模型** ——
  ① 画风天然一致，不会出现"照片和片子不是一个渲染体系"的割裂；
  ② Ref2VA 支持最多 9 张参考图锁角色 ⇒ 比 ComfyUI 的文字生图更能保住"是这两个人"。

用法:
  python h3-still.py --name <输出名> --prompt-file <提示词.txt> --refs a.png,b.png[,c.png]
"""
import argparse
import io
import json
import os

FLOW = r"$env:DSH_AI\out\flow"
BASE = os.path.join(FLOW, "_base-job-template.json")   # 公共字段基准（分辨率/步数/seed）
if not os.path.exists(BASE):                      # 回退：旧实验目录
    BASE = os.path.join(FLOW, "s4-burn-g", "job.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--refs", required=True, help="逗号分隔的参考图路径（最多 9 张）")
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--steps", type=int, default=40)
    a = ap.parse_args()

    with io.open(BASE, encoding="utf-8") as f:
        job = json.load(f)

    refs = [r.strip() for r in a.refs.split(",") if r.strip()]
    for r in refs:
        if not os.path.exists(r):
            raise SystemExit("参考图不存在: %s" % r)

    with io.open(a.prompt_file, encoding="utf-8") as f:
        prompt = f.read()

    job["prompt"] = prompt
    job["output_filename"] = a.name
    job["model_type"] = "minimax_h3_ref2va_pruned_nvfp4"
    job["image_mode"] = 1          # ← 关键：1 = Text to Image（出单张静帧）
    job["image_refs"] = refs
    job["image_refs_relative_size"] = 100
    job["video_prompt_type"] = "I"
    job["num_inference_steps"] = a.steps
    if a.seed >= 0:
        job["seed"] = a.seed

    d = os.path.join(FLOW, a.name)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "job.json")
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(job, f, ensure_ascii=False, indent=1)

    with open(p, "rb") as f:
        head = f.read(3)
    print("job: %s" % p)
    print("  image_mode = %s (1=Text to Image)" % job["image_mode"])
    print("  refs = %d 张" % len(refs))
    for r in refs:
        print("    - %s" % r)
    print("  steps=%d seed=%s frames=%s" % (job["num_inference_steps"], job["seed"], job.get("video_length")))
    print("  BOM check: %s" % head.hex())
    print("  prompt: %d 字符" % len(prompt))


if __name__ == "__main__":
    main()
