#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""audio-to-video.py —— 把音频包成"静态图 + 音轨"的 mp4（2026-10-12 立）

为什么：QQ 打不开 wav / mp3 这类裸音频（点了没反应），
      但 mp4 能直接播 → 试听素材一律先转成静态视频再发。

用法:
  python audio-to-video.py --audio x.wav --image y.png --out z.mp4 [--label "文字"]
  python audio-to-video.py --batch list.json          # [{audio,image,out,label}, ...]

要点:
  · 视频轨 = 单帧静止图（-loop 1 + -tune stillimage），体积几乎只由音轨决定
  · yuv420p + faststart，保证手机 / QQ 能播
  · 尺寸强制偶数（yuv420p 要偶数）
"""
import argparse
import json
import os
import subprocess
import sys

FFMPEG = r"$env:DSH_AI\Wan2GP\ffmpeg_bins\ffmpeg.exe"
FFPROBE = r"$env:DSH_AI\Wan2GP\ffmpeg_bins\ffprobe.exe"
FONT = "'C\\:/Windows/Fonts/msyh.ttc'"   # 微软雅黑；单引号 + 单反斜杠转义冒号，两者缺一 ffmpeg 就报 "No option name near"


def log(msg):
    print(msg, flush=True)


def even(n):
    return int(n) // 2 * 2


def probe_duration(path):
    if not os.path.exists(FFPROBE):
        return 0.0
    cmd = [FFPROBE, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=nw=1:nk=1", path]
    try:
        out = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=60)
        return float((out.stdout or "0").strip() or 0)
    except Exception:
        return 0.0


def build_filter(width, height, label=None, label_size=38):
    f = ["scale=%d:%d:force_original_aspect_ratio=increase" % (width, height),
         "crop=%d:%d" % (width, height),
         "format=yuv420p"]
    if label:
        # 底部一条半透明黑带上写字，位置固定，不依赖字体度量
        band_h = label_size * 2
        f.append("drawbox=x=0:y=ih-%d:w=iw:h=%d:color=black@0.55:t=fill" % (band_h, band_h))
        f.append(
            "drawtext=fontfile=%s:text='%s':fontcolor=white:fontsize=%d"
            ":x=(w-text_w)/2:y=h-%d+(%d-text_h)/2"
            % (FONT, label, label_size, band_h, band_h)
        )
    return ",".join(f)


def make(audio, image, out, label=None, width=1280, height=720, fps=24, crf=20):
    for p in (audio, image):
        if not os.path.exists(p):
            raise SystemExit("missing input: %s" % p)
    width, height = even(width), even(height)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    dur = probe_duration(audio)
    vf = build_filter(width, height, label)
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-loop", "1", "-framerate", str(fps), "-i", image,
           "-i", audio,
           "-vf", vf,
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
           "-crf", str(crf), "-r", str(fps),
           "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           "-shortest", out]
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=900)
    if r.returncode != 0:
        # drawtext 不被支持时退一步：去掉标签重来
        if label:
            log("  ! drawtext failed, retry without label")
            return make(audio, image, out, None, width, height, fps, crf)
        raise SystemExit("ffmpeg failed: %s" % (r.stderr or "")[-400:])
    mb = os.path.getsize(out) / 1e6
    log("  -> %s  %.2f s  %.2f MB" % (out, dur, mb))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio")
    ap.add_argument("--image")
    ap.add_argument("--out")
    ap.add_argument("--label", default=None)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--batch", default=None, help="JSON 清单：[{audio,image,out,label}, ...]")
    args = ap.parse_args()

    if args.batch:
        with open(args.batch, encoding="utf-8") as f:
            items = json.load(f)
        for it in items:
            log("[%s]" % os.path.basename(it["audio"]))
            make(it["audio"], it["image"], it["out"], it.get("label"),
                 it.get("width", args.width), it.get("height", args.height))
        return 0

    if not (args.audio and args.image and args.out):
        ap.error("--audio / --image / --out are required (or use --batch)")
    make(args.audio, args.image, args.out, args.label, args.width, args.height)
    return 0


if __name__ == "__main__":
    sys.exit(main())
