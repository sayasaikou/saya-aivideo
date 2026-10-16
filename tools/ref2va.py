#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ref2va.py —— Ref2VA 出片：用参考图锁角色，不用 LoRA（2026-10-10 立）

为什么：两天卡在「首尾帧背景漂移」——因为 FL2VA 要从 A 图运动到 B 图，
两图背景不一致时模型必须同时解决多个问题。Ref2VA 不需要尾帧，背景由提示词自洽生成。

用法:
  python ref2va.py --name ref2va-test1 [--steps 20] [--dur 4] [--dry-run]

2026-10-12 新增（方案A · 官方语音驱动）：
  --audio <mp3> [--audio-mode AS]   原音保留、画面跟着它走（帧数按音频时长自动算）
  --audio <mp3> [--audio-mode A]    只当音色参考（克隆）

2026-10-12 新增：
  --spatial-upsampling h3_vae*2   直出 2 倍分辨率（换 H3 的 X2 Detail VAE 解码器）
  --temporal-upsampling rife*2    插帧（2/3/4）
  --pp / --no-pp                  ffmpeg 轻量后处理（**默认开**）：先降噪再锐化

产物:
  E:\\dsh-ai\\out\\flow\\<name>\\job.json / video\\*.mp4 / frames\\ / report.txt
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
CKPT = os.path.join(WAN, r"ckpts\MiniMax-H3-Ref2VA-pruned_rank8_int8_convrot.safetensors")
CKPT_MIN_BYTES = 20_000_000_000  # 20 GB decimal (actual file = 21,057,674,788 B)

FFMPEG = os.path.join(WAN, r"ffmpeg_bins\ffmpeg.exe")
# 已实测配方（2026-10-11）：先降噪再锐化，反了会把噪声一起锐化
#   拉普拉斯方差 +83~88%；平坦区噪声 30.80 → 31.00（+0.65%，没放大）；2.3 s / 15 秒片
PP_VF = "hqdn3d=1.5:1:2:3,unsharp=5:5:0.6:5:5:0"

REFS = [
    r"$env:DSH_WORKSPACE\acg生图\the whale-girl persona形象-参考\原版设定-ZipZipPipe\原版设定-01.png",
    r"$env:DSH_WORKSPACE\acg生图\the whale-girl persona形象-参考\原版设定-ZipZipPipe\原版设定-02.png",
]

PROMPT = """subject_definitions:
<Subject 1> is the blue-haired whale-girl maid shown in <Picture 1> and <Picture 2>, preserving her exact identity: pale skin, large bright-blue eyes with three highlights, very long gradient-blue hair that is darkest at the roots and palest at the tips, a single long thin ahoge rising from behind her headdress, a pair of navy whale-fin ears with pale edges, a white katyusha-style maid headdress with a small navy bow on the right, and a whale tail ending in a V-shaped fluke.
summary:
[reference generation] Place <Subject 1> on a stone breakwater by a seaside town at golden hour and show her turning from the sea to face the camera in one continuous four-second shot, with her hair and the layers of her skirt lifted by the wind.
retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity, face, eye colour, hair gradient, ahoge, whale-fin ears, headdress and bow, navy multi-layer maid dress, white frilled apron with the small navy whale print, navy waist sash with gold buttons, white socks, navy Mary Jane shoes and whale tail remain recognizable and unchanged; only the location, lighting, camera framing and her pose are new.
detailed_description:
The target video is a four-second cinematic 2D semi-realistic anime single take with warm golden-hour light and crisp linework. [Shot 1] <Subject 1> stands on a stone breakwater with the sea behind her, framed in a steady medium shot that keeps her recognizable face, hair, ears, headdress and full outfit from the reference pictures clearly visible. She begins facing the water, her long gradient-blue hair and the layered skirt of her navy maid dress already lifting and drifting in the sea wind, her whale tail swaying slowly behind her. She turns her upper body smoothly toward the camera in one continuous movement, her hair swinging across her shoulder as she comes around, until she faces the viewer and settles into a calm, slightly curious expression. Her arms stay relaxed at her sides with only a small natural swing, and the fabric of her apron and skirt keeps moving after she stops. Throughout the turn her proportions, facial features, clothing details and colours stay stable and physically coherent, with no morphing of the face, hands or costume. The camera holds a static medium shot with small amplitude so that her whole figure and the breakwater stay in the same framing from the beginning to the end of the shot.
overall_soundscape: Sea waves against the stone breakwater, gusting wind, distant gull cries, and the soft rustle of layered cloth during the turn.
non_diegetic_music: One warm sustained string note that swells slightly as she turns and fades at the end."""


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", **kw)


def laplacian_var(png):
    """PIL 拉普拉斯方差 —— 清晰度代理指标（不用 numpy，避免依赖假设）"""
    from PIL import Image, ImageFilter, ImageStat
    im = Image.open(png).convert("L")
    k = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)
    return ImageStat.Stat(im.filter(k)).var[0]


def sharpness(mp4, tmpdir, samples=3):
    """抽 3 帧算拉普拉斯方差均值；失败返回 None 而不是编一个数"""
    try:
        probe = run([os.path.join(WAN, r"ffmpeg_bins\ffprobe.exe"), "-v", "error",
                     "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", mp4])
        dur = float((probe.stdout or "0").strip() or 0)
        vals = []
        for i in range(samples):
            t = dur * (i + 1) / (samples + 1)
            png = os.path.join(tmpdir, "_sharp_%d.png" % i)
            r = run([FFMPEG, "-y", "-v", "error", "-ss", "%.2f" % t, "-i", mp4,
                     "-frames:v", "1", png])
            if r.returncode == 0 and os.path.exists(png):
                vals.append(laplacian_var(png))
        return sum(vals) / len(vals) if vals else None
    except Exception as e:
        log("sharpness measure failed: %s" % e)
        return None


def postprocess(mp4, outdir):
    """ffmpeg 轻量档：先降噪（hqdn3d）再锐化（unsharp）。原始片保留，另存 -pp.mp4。"""
    out = os.path.join(outdir, os.path.splitext(os.path.basename(mp4))[0] + "-pp.mp4")
    t0 = time.time()
    r = run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", mp4,
             "-vf", PP_VF, "-c:v", "libx264", "-crf", "18", "-preset", "medium",
             "-c:a", "copy", out])
    if r.returncode != 0:
        log("postprocess FAILED rc=%d: %s" % (r.returncode, (r.stderr or "")[-200:]))
        return None
    el = time.time() - t0
    before = sharpness(mp4, outdir)
    after = sharpness(out, outdir)
    if before and after:
        log("postprocess: %.1f s  |  拉普拉斯方差 %.1f → %.1f (%+.0f%%)  |  %.2f MB → %.2f MB"
            % (el, before, after, (after / before - 1) * 100,
               os.path.getsize(mp4) / 1e6, os.path.getsize(out) / 1e6))
    else:
        log("postprocess: %.1f s  (sharpness 量不到，不编数)" % el)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--refs", default=None, help="逗号分隔的参考图；默认用两张原版设定图")
    ap.add_argument("--w", type=int, default=1344)
    ap.add_argument("--h", type=int, default=768)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--phases", type=int, default=2)
    ap.add_argument("--dur", type=float, default=4.0)
    ap.add_argument("--ref-size", type=int, default=100)
    ap.add_argument("--seed", type=int, default=-1, help="固定种子做 A/B（-1=随机）")
    ap.add_argument("--turbo", choices=["off", "8", "4"], default="off",
                    help="Ref2V turbo 加速 LoRA：8 = 8步 768p，4 = 4步（见 profiles/minimax_h3_ref2va）")
    ap.add_argument("--prompt-file", default=None, help="从文件读六段式提示词（默认用脚本内置的 4 秒版）")
    ap.add_argument("--audio", default=None, help="音频驱动：官方语音 mp3/wav（配合 --audio-mode）")
    ap.add_argument("--audio-mode", default="AS", choices=["A", "AS"],
                    help="AS=原音保留为输出音轨、画面跟着音频走；A=只当音色参考（克隆）")
    ap.add_argument("--frames", type=int, default=None, help="直接指定帧数（默认按 --dur / --audio 时长算）")
    ap.add_argument("--start-image", default=None, dest="start_image", help="首帧锚点（image_start，用来锁姿势/构图）")
    ap.add_argument("--spatial-upsampling", default=None,
                    help="空间超分，如 h3_vae*2（解码即 2 倍，需 MiniMax-H3-X2-Detail 权重）")
    ap.add_argument("--temporal-upsampling", default=None, help="插帧，如 rife*2 / rife*3 / rife*4")
    ap.add_argument("--no-pp", dest="pp", action="store_false", help="关掉 ffmpeg 后处理（默认开）")
    ap.add_argument("--dry-run", action="store_true")
    ap.set_defaults(pp=True)
    args = ap.parse_args()

    if not os.path.exists(CKPT) or os.path.getsize(CKPT) < CKPT_MIN_BYTES:
        have = os.path.getsize(CKPT) / 1e9 if os.path.exists(CKPT) else 0
        raise SystemExit("Ref2VA checkpoint not ready yet (%.2f GB)" % have)

    refs = [r for r in (args.refs.split(",") if args.refs else REFS) if r.strip()]
    for r in refs:
        if not os.path.exists(r):
            raise SystemExit("reference image missing: %s" % r)

    # Ref2V turbo 加速档：官方预设见 profiles/minimax_h3_ref2va/*.json
    TURBO = {
        "8": ("minimax_h3_lightx2v_ref2v_turbo_8step_alpha8_v1.0_768p_bf16.safetensors", 8),
        "4": ("minimax_h3_lightx2v_ref2v_turbo_4step_alpha8_v0.1_bf16.safetensors", 4),
    }
    turbo_file, turbo_steps = TURBO.get(args.turbo, (None, 0))
    turbo_path = None
    if turbo_file:
        turbo_path = os.path.join(WAN, "loras", "minimax_h3", turbo_file)
        if not os.path.exists(turbo_path):
            raise SystemExit("turbo LoRA missing: %s" % turbo_path)

    outdir = os.path.join(OUTROOT, args.name)
    os.makedirs(outdir, exist_ok=True)
    # 帧数对齐 H3 原生的 17k+5 形状（4 秒=97，15 秒=362）
    if args.frames:
        frames = args.frames
    elif args.audio:
        if not os.path.exists(args.audio):
            raise SystemExit("audio file missing: %s" % args.audio)
        probe = run([os.path.join(WAN, "ffmpeg_bins", "ffprobe.exe"), "-v", "error",
                     "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", args.audio])
        adur = float((probe.stdout or "0").strip() or 0)
        if adur <= 0:
            raise SystemExit("cannot read audio duration: %s" % args.audio)
        frames = max(97, (int(round(adur * 24)) // 17) * 17 + 5)
        log("audio: %.2f s -> %d frames (%.2f s)" % (adur, frames, frames / 24.0))
    else:
        frames = 97 if args.dur <= 4.05 else (int(round(args.dur * 24)) // 17) * 17 + 5

    job = {
        "model_type": "minimax_h3_ref2va_pruned",
        "prompt": (io.open(args.prompt_file, encoding="utf-8").read() if args.prompt_file else PROMPT),
        "resolution": "%dx%d" % (args.w, args.h),
        "video_length": frames,
        "duration_seconds": 0,
        "num_inference_steps": turbo_steps or args.steps,
        "sample_solver": "euler",
        "guidance_phases": args.phases,
        "guidance_scale": 1 if turbo_file else 5,
        "seed": args.seed,
        "batch_size": 1,
        # Ref2VA 的参考图入口：video_prompt_type 的 I = Use Reference Images
        "image_refs": refs,
        "image_refs_relative_size": args.ref_size,
        "video_prompt_type": "I",
        # 多行提示词 ⟹ 必须 FG，否则 WanGP 按换行拆成多个请求
        "multi_prompts_gen_type": "FG",
        "output_filename": args.name,
    }
    if args.start_image:
        if not os.path.exists(args.start_image):
            raise SystemExit("start image missing: %s" % args.start_image)
        # 首帧锚点：编号上它是 <Picture 1>，参考图往后顺延
        job["image_start"] = args.start_image
        job["image_prompt_type"] = "S"
        job["image_mode"] = 0
    if args.audio:
        # 方案A：AS = 保留输入音频作为输出音轨（画面跟着音频走）；A = 只当音色参考
        job["audio_prompt_type"] = args.audio_mode
        job["audio_guide"] = args.audio
    if args.spatial_upsampling:
        job["spatial_upsampling"] = args.spatial_upsampling
    if args.temporal_upsampling:
        job["temporal_upsampling"] = args.temporal_upsampling
    if turbo_file:
        # 官方 turbo 预设的三个配套值（profiles/minimax_h3_ref2va/*.json）
        job["flow_shift"] = 12
        job["activated_loras"] = [turbo_path]
        job["loras_multipliers"] = "1.0"

    path = os.path.join(outdir, "job.json")
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=1)
    log("job: %s  refs=%d  res=%dx%d frames=%d steps=%d phases=%d turbo=%s seed=%d" %
        (path, len(refs), args.w, args.h, frames, turbo_steps or args.steps, args.phases,
         args.turbo, args.seed))
    if args.spatial_upsampling or args.temporal_upsampling:
        log("post: spatial=%s temporal=%s" % (args.spatial_upsampling, args.temporal_upsampling))

    if args.dry_run:
        log("dry-run: stop before H3")
        return 0

    vout = os.path.join(outdir, "video")
    os.makedirs(vout, exist_ok=True)
    cmd = [WAN_PY, "wgp.py", "--process", path, "--output-dir", vout]
    log("run: %s" % " ".join(cmd))
    # 2026-10-12: 渲染期间停掉 Mem Reduct（它会剪掉 H3 钉在内存里的权重），完了原样拉回
    try:
        import memguard
    except Exception as _exc:  # noqa: BLE001
        memguard = None
        log("memguard 未加载（%s），不动 Mem Reduct" % _exc)
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
        raise SystemExit("Ref2VA failed rc=%d after %.0fs" % (r.returncode, el))
    mp4s = [f for f in os.listdir(vout) if f.lower().endswith(".mp4")]
    if not mp4s:
        raise SystemExit("no mp4 produced")
    mp4 = os.path.join(vout, sorted(mp4s)[-1])
    log("video: %s (%.2f MB, %.0fs)" % (mp4, os.path.getsize(mp4) / 1e6, el))

    sys.path.insert(0, r"$env:DSH_HOME\comfy-tools")
    import flow
    frames_dir, dur = flow.extract_frames(mp4, outdir)
    data = flow.frame_selfcheck(frames_dir, os.path.join(outdir, "report.txt"))
    if data:
        print("frame diffs: median=%.2f mad=%.2f outliers=%s" %
              (data.get("diff_median", -1), data.get("diff_mad", -1), data.get("outliers") or "none"))

    if args.pp:
        pp = postprocess(mp4, outdir)
        if pp:
            log("deliverable: %s" % pp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
