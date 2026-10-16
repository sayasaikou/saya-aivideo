#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""style-metrics.py -- 用算法量"平涂/赛璐璐"程度，不靠模型目测。

思路：赛璐璐的特征是「大片同色 + 色阶少 + 渐变少」。
所以量四个与"平涂"相关的客观量：
  1. unique_colors  量化后的不同颜色数（越少越平涂）
  2. color_entropy  颜色直方图熵（越低越平涂）
  3. gradient_mean  相邻像素亮度差的均值（越低越"没有渐变/没有细节"）
  4. flat_ratio     局部方差极小的像素占比（"平色块"比例，越高越赛璐璐）

用法:
  python style-metrics.py --dir <视频产物目录> --shot <名字> [--points 50]
  或
  python style-metrics.py --video <mp4> --label s4 [--points 50]
"""
import argparse
import io
import os
import sys

from PIL import Image

sys.path.insert(0, r"$env:DSH_HOME\comfy-tools")
import flow  # noqa: E402

BINS = 6  # 每通道量化到 6 级 -> 最多 216 色


def metrics(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    small = im.resize((320, max(1, int(320 * h / w))), Image.LANCZOS)
    q = small.point(lambda v: (v * BINS) // 256)  # 量化
    px = list(q.getdata())
    uniq = len(set(px))
    # 颜色熵
    from collections import Counter
    import math
    cnt = Counter(px)
    total = len(px)
    ent = -sum((c / total) * math.log2(c / total) for c in cnt.values())
    # 亮度梯度
    g = small.convert("L")
    gw, gh = g.size
    gp = list(g.getdata())
    diffs = []
    for y in range(gh):
        row = y * gw
        for x in range(gw - 1):
            diffs.append(abs(gp[row + x] - gp[row + x + 1]))
    grad = sum(diffs) / max(1, len(diffs))
    # 平色块比例：3x3 邻域极差 <= 2 视为平
    flat = 0
    checked = 0
    for y in range(1, gh - 1):
        for x in range(1, gw - 1):
            i = y * gw + x
            vals = (gp[i - gw - 1], gp[i - gw], gp[i - gw + 1], gp[i - 1], gp[i], gp[i + 1],
                    gp[i + gw - 1], gp[i + gw], gp[i + gw + 1])
            checked += 1
            if max(vals) - min(vals) <= 2:
                flat += 1
    return {
        "unique_colors": uniq,
        "color_entropy": round(ent, 3),
        "gradient_mean": round(grad, 2),
        "flat_ratio": round(flat / max(1, checked), 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video")
    ap.add_argument("--label")
    ap.add_argument("--dir")
    ap.add_argument("--shot")
    ap.add_argument("--points", default="25,50,75")
    args = ap.parse_args()

    if args.video:
        video, label = args.video, (args.label or os.path.basename(args.video))
    else:
        base = os.path.join(args.dir, args.shot)
        cands = [f for f in os.listdir(os.path.join(base, "video")) if f.lower().endswith(".mp4")]
        if not cands:
            raise SystemExit("no mp4 in %s/video" % base)
        video = os.path.join(base, "video", sorted(cands)[-1])
        label = args.shot

    tmp = os.path.join(os.path.dirname(video), "_styleframes")
    os.makedirs(tmp, exist_ok=True)
    frames_dir, dur = flow.extract_frames(video, tmp)
    names = sorted(f for f in os.listdir(frames_dir) if f.lower().endswith(".png"))
    n = len(names)
    print("== %s ==  %d 帧 / %.1f 秒" % (label, n, dur))
    print("%-6s %-14s %-13s %-13s %-10s" % ("point", "unique_colors", "color_entropy", "gradient_mean", "flat_ratio"))
    acc = []
    for p in [int(x) for x in args.points.split(",")]:
        idx = min(n - 1, max(0, int(round((n - 1) * p / 100.0))))
        m = metrics(os.path.join(frames_dir, names[idx]))
        acc.append(m)
        print("%-6s %-14d %-13.3f %-13.2f %-10.3f" % ("%d%%" % p, m["unique_colors"], m["color_entropy"], m["gradient_mean"], m["flat_ratio"]))
    if acc:
        print("%-6s %-14.0f %-13.3f %-13.2f %-10.3f" % (
            "AVG",
            sum(a["unique_colors"] for a in acc) / len(acc),
            sum(a["color_entropy"] for a in acc) / len(acc),
            sum(a["gradient_mean"] for a in acc) / len(acc),
            sum(a["flat_ratio"] for a in acc) / len(acc),
        ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
