#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""zimage.py -- WanGP 的 Z-Image 出图驱动器（2026-10-13 立）

为何不用 SDXL 了：本机 SDXL 是 2023 年引擎，风格对齐一直是天花板。
Z-Image Turbo 是机器里已注册好的现代图像模型（6B / 9 步 / 1920x1088）。

控制图（把 3D 搭景 / NPR 底图锚成插图级背景）：
  WanGP 的 `video_prompt_type`（图像模式下就叫控制图预处理）字母：
    ""   什么都不做 -> 控制图原样进 ControlNet（**喂自己算好的深度图就用这个**）
    V    Z-Image Raw Format（官方让原图直接进）
    DV   转深度（WanGP 自带 Depth-Anything-V2；**权重本机没有，会现场下**）
    EV   转 Canny 边
    PV   转人体姿态
  ⚠️ 结论（读 wgp.py 的 process_map_video_guide 得出）：DV 是「拿 RGB 估深度」，
     不是「你喂深度图」。自己已经有真深度图时，用 "" 最干净。

用法:
  python zimage.py --name forge-z1 --prompt-file p.txt --guide forge-depth.png
  python zimage.py --name probe --guide a.png --mode DV --dry-run
产物:
  $env:DSH_AI\out\flow\<name>\job.json  /  images\*.png  /  report.txt
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

# 默认值取自 defaults/z_image_control2_1.json（2026-10-13 实测读的，不是猜的）
DEFAULTS = {
    "z_image_control2_1": {"resolution": "1920x1088", "steps": 9, "guidance": 0, "net_weight": 0.75},
    "z_image_control": {"resolution": "1024x1024", "steps": 9, "guidance": 0, "net_weight": 0.75},
    "z_image": {"resolution": "1024x1024", "steps": 8, "guidance": 0, "net_weight": 0.75},
}

# WanGP 的 settings_version（跟 h3 模板一致；差一点没关系，它只用来做迁移）
SETTINGS_VERSION = 2.80


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def img_size(path):
    """读 PNG 尺寸，不依赖 PIL（用标准库手解 IHDR）"""
    with open(path, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("not a PNG: %s" % path)
    w = int.from_bytes(head[16:20], "big")
    h = int.from_bytes(head[20:24], "big")
    return w, h


def build_job(args, guide_path):
    """按 h3 模板的全字段集拼 job —— 多给字段没事，少给才会被默认值坑"""
    w, h = img_size(guide_path)
    if args.w and args.h:
        w, h = args.w, args.h
    d = DEFAULTS[args.model]
    res = "%dx%d" % (w, h)

    job = {
        "client_id": "",
        "prompt": io.open(args.prompt_file, encoding="utf-8").read() if args.prompt_file else "",
        "alt_prompt": "",
        "image_mode": 1,                     # 1 = 图像生成模式
        "image_prompt_type": "",
        "model_mode": "",
        "keep_frames_video_source": "",
        "video_prompt_type": args.mode,      # "" = 控制图原样进 ControlNet
        "denoising_strength": 1.0,
        "input_video_strength": 1.0,
        "keep_frames_video_guide": "",
        "video_guide_outpainting": "#",
        "video_guide_outpainting_ratio": "",
        "masking_strength": 1,
        "mask_expand": 0,
        "frames_positions": "",
        "image_refs_relative_size": 50,
        "remove_background_images_ref": 0,
        "audio_prompt_type": "",
        "speakers_locations": "",
        "prompt_enhancer": "",
        "custom_settings": None,
        "resolution": res,
        "batch_size": 1,
        "video_length": 1,
        "duration_seconds": 0,
        "pause_seconds": 0,
        "force_fps": "",
        "num_inference_steps": args.steps or d["steps"],
        "seed": args.seed,
        "guidance_phases": 1,
        "guidance_scale": d["guidance"],
        "sample_solver": "default",
        "flow_shift": 0.0,
        "control_net_weight": args.net_weight if args.net_weight is not None else d["net_weight"],
        "negative_prompt": args.negative or "",
        "NAG_scale": 1.0,
        "NAG_tau": 3.5,
        "NAG_alpha": 0.5,
        "repeat_generation": 1,
        "multi_images_gen_type": 0,
        # ⚠️ 必须是 FG：提示词里有空行（分段）时，PG 会把它拆成两个生成请求
        # （实测报 "parses this prompt into 2 separate generation requests" 然后 Skipping）——同 ref2va.py 那条坑
        "multi_prompts_gen_type": "FG",
        "temporal_upsampling": "",
        "spatial_upsampling": "",
        "film_grain_intensity": 0,
        "film_grain_saturation": 0.5,
        "override_profile": -1,
        "override_attention": "",
        "attention_sparsity": 1.0,
        "output_filename": args.name,
        "config": "",
        "activated_loras": [],
        "loras_multipliers": "",
        "image_start": None,
        "image_end": None,
        "image_refs": None,
        "image_guide": guide_path,           # ⭐ 控制图入口（image_mode>0 且 "V" in video_prompt_type）
        "image_mask": None,
        "video_guide": None,
        "video_guide2": None,
        "video_guide3": None,
        "video_mask": None,
        "video_source": None,
        "audio_guide": None,
        "audio_guide2": None,
        "audio_guide3": None,
        "custom_guide": None,
        "audio_source": None,
        "replace_voice_method": "",
        "replace_voice_sample": None,
        "replace_voice_sample2": None,
        "settings_version": SETTINGS_VERSION,
        "model_type": args.model,
    }
    return job, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--guide", required=True, help="控制图（深度图 / NPR 底图）")
    ap.add_argument("--mode", default="",
                    help='控制图预处理字母：""（原样进）/ V（Z-Image Raw）/ DV（转深度）/ EV（转边）/ PV（姿态）')
    ap.add_argument("--model", default="z_image_control2_1",
                    choices=sorted(DEFAULTS.keys()))
    ap.add_argument("--prompt-file", default=None, help="提示词文件（UTF-8）；不给就空提示词")
    ap.add_argument("--negative", default=None)
    ap.add_argument("--w", type=int, default=None)
    ap.add_argument("--h", type=int, default=None)
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--net-weight", type=float, default=None, dest="net_weight",
                    help="ControlNet 权重（默认取预设 0.75）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.guide):
        raise SystemExit("control image missing: %s" % args.guide)
    if args.prompt_file and not os.path.exists(args.prompt_file):
        raise SystemExit("prompt file missing: %s" % args.prompt_file)

    outdir = os.path.join(OUTROOT, args.name)
    os.makedirs(outdir, exist_ok=True)
    job, res = build_job(args, os.path.abspath(args.guide))
    path = os.path.join(outdir, "job.json")
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=1)
    log("job: %s  model=%s mode=%r res=%s steps=%d net=%.2f seed=%d"
        % (path, args.model, args.mode, res, job["num_inference_steps"],
           job["control_net_weight"], args.seed))
    log("guide: %s" % job["image_guide"])

    if args.dry_run:
        log("dry-run: stop before WanGP")
        return 0

    iout = os.path.join(outdir, "images")
    os.makedirs(iout, exist_ok=True)
    cmd = [WAN_PY, "wgp.py", "--process", path, "--output-dir", iout]
    log("run: %s" % " ".join(cmd))

    # 渲染期间停 Mem Reduct（它会剪掉钉在内存里的权重）——同 ref2va.py
    try:
        sys.path.insert(0, r"$env:DSH_HOME\comfy-tools")
        import memguard
    except Exception as exc:  # noqa: BLE001
        memguard = None
        log("memguard 未加载（%s），不动 Mem Reduct" % exc)
    if memguard:
        memguard.pause()
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=WAN)
    finally:
        if memguard:
            memguard.resume()
    el = time.time() - t0
    if r.returncode != 0:
        raise SystemExit("Z-Image failed rc=%d after %.0fs" % (r.returncode, el))

    imgs = sorted(f for f in os.listdir(iout)
                  if os.path.splitext(f)[1].lower() in (".png", ".jpg", ".jpeg", ".webp"))
    if not imgs:
        raise SystemExit("no image produced in %s" % iout)
    log("done in %.0fs" % el)
    for f in imgs:
        p = os.path.join(iout, f)
        log("  %s  %.2f MB" % (p, os.path.getsize(p) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
