#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tts.py —— 本地 TTS 驱动器（2026-10-12 立）

两个引擎：
  h3      = minimax_h3_tts_ref2va_pruned（复用 Ref2VA ckpt，零下载；音质＝捧读感 / 机械底噪）
  itts25  = index_tts25（IndexTTS 2.5，中文＋情绪内联标注＋语速控制；组件已下到 ckpts）

用法:
  python tts.py --engine itts25 --name itts-01 --text "..." --ref <参考音>
  python tts.py --engine itts25 --name itts-02 --text "[excited] ..." --ref a.mp3 --ref2 b.mp3 --mode AB
  python tts.py --engine h3 --name h3-x --text "..." --ref a.mp3

关键参数:
  --mode A    单说话人克隆（参考音给音色）
  --mode AB   音色 A ＋ 情绪参考 B
  --mode AB2  双说话人对话（--ref / --ref2，文本里写 Speaker 1: / Speaker 2:）
  --lang      itts25 专用：ZH / EN / ZHEN / JA / ES / AR
  --speed     语速 0.5~2.0（默认 1.0）
  --pack      跑完自动包成静态视频（需 --pack-image）
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time

WAN = r"$env:DSH_AI\Wan2GP"
WAN_PY = os.path.join(WAN, r"env_venv\Scripts\python.exe")
OUTROOT = r"$env:DSH_AI\out\flow"

ENGINES = {
    "h3": "minimax_h3_tts_ref2va_pruned",
    "itts25": "index_tts25",
}


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def build_job(args):
    if args.engine == "h3":
        job = {
            "model_type": ENGINES["h3"],
            "prompt": args.text,
            "audio_prompt_type": args.mode,
            "audio_guide": args.ref,
            "video_length": 0,
            "duration_seconds": args.dur,
            "num_inference_steps": 20,
            "guidance_phases": 1,
            "sample_solver": "euler",
            "multi_prompts_gen_type": "FG",
            "output_filename": args.name,
        }
        if args.ref2:
            job["audio_guide2"] = args.ref2
        return job

    # IndexTTS 2.5
    job = {
        "model_type": ENGINES["itts25"],
        "prompt": args.text,
        "alt_prompt": args.emotion or "",
        "model_mode": args.lang,
        "audio_prompt_type": args.mode,
        "audio_guide": args.ref,
        "duration_seconds": args.dur,
        "pause_seconds": 0.2,
        "temperature": 0.8,
        "top_p": 0.8,
        "top_k": 30,
        "video_length": 0,
        "num_inference_steps": 0,
        "multi_prompts_gen_type": "FG",
        "custom_settings": {
            "speech_speed": args.speed,
            "text_normalization": "Yes" if args.normalize else "No",
        },
        "output_filename": args.name,
    }
    if args.ref2:
        job["audio_guide2"] = args.ref2
    if args.ref3:
        job["audio_guide3"] = args.ref3
    return job


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=sorted(ENGINES), required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--text", default=None, help="台词（换行写 \\n；多说话人写 Speaker 1: / Speaker 2:）")
    ap.add_argument("--text-file", default=None, help="从文件读台词（长文本用这个，避免命令行转义）")
    ap.add_argument("--ref", required=True, help="参考音（音色）")
    ap.add_argument("--ref2", default=None)
    ap.add_argument("--ref3", default=None)
    ap.add_argument("--mode", default="A", choices=["A", "AB", "AB2", "ABD2"])
    ap.add_argument("--lang", default="ZH", choices=["EN", "ZH", "ZHEN", "JA", "ES", "AR"])
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--emotion", default=None, help="默认情绪指令（itts25 的 alt_prompt）")
    ap.add_argument("--dur", type=float, default=30.0, help="最大时长上限（秒）")
    ap.add_argument("--no-normalize", dest="normalize", action="store_false")
    ap.add_argument("--pack", action="store_true", help="跑完自动包成静态视频")
    ap.add_argument("--pack-image", default=None)
    ap.add_argument("--pack-label", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.set_defaults(normalize=True)
    args = ap.parse_args()

    if args.text_file:
        args.text = io.open(args.text_file, encoding="utf-8").read().rstrip("\n")
    else:
        args.text = args.text.replace("\\n", "\n")

    for p in (args.ref, args.ref2, args.ref3):
        if p and not os.path.exists(p):
            raise SystemExit("reference audio missing: %s" % p)

    outdir = os.path.join(OUTROOT, args.name)
    os.makedirs(outdir, exist_ok=True)
    job = build_job(args)
    path = os.path.join(outdir, "job.json")
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=1)
    log("job: %s  engine=%s mode=%s lang=%s speed=%.2f" % (path, args.engine, args.mode, args.lang, args.speed))
    log("text: %s" % args.text.replace("\n", " | ")[:160])

    if args.dry_run:
        log("dry-run: stop before inference")
        return 0

    vout = os.path.join(outdir, "out")
    os.makedirs(vout, exist_ok=True)
    cmd = [WAN_PY, "wgp.py", "--process", path, "--output-dir", vout]
    log("run: %s" % " ".join(cmd))
    t0 = time.time()
    r = subprocess.run(cmd, cwd=WAN)
    el = time.time() - t0
    if r.returncode != 0:
        raise SystemExit("%s failed rc=%d after %.0fs" % (args.engine, r.returncode, el))

    wavs = [f for f in os.listdir(vout) if f.lower().endswith((".wav", ".mp3", ".flac"))]
    if not wavs:
        raise SystemExit("no audio produced in %s" % vout)
    wav = os.path.join(vout, sorted(wavs)[-1])
    log("audio: %s (%.2f MB, %.0fs)" % (wav, os.path.getsize(wav) / 1e6, el))

    if args.pack:
        if not args.pack_image:
            raise SystemExit("--pack needs --pack-image")
        sys.path.insert(0, r"$env:DSH_HOME\comfy-tools")
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "a2v", r"$env:DSH_HOME\comfy-tools\audio-to-video.py")
        a2v = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(a2v)
        mp4 = os.path.join(outdir, "%s.mp4" % args.name)
        a2v.make(wav, args.pack_image, mp4, args.pack_label or args.name)
        log("packed: %s" % mp4)
    return 0


if __name__ == "__main__":
    sys.exit(main())
