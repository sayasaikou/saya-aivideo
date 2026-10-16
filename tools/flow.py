#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
flow.py —— 首帧 → H3 视频 一体化流程（一条命令跑完，2026-10-09 立）

解决的三件事：
  #4 尺寸联动：首帧按目标视频的宽高比出图（横屏就出横屏），避免"竖首帧→竖视频"
  #6 可复跑：一条命令干完「出首帧 → 建作业 → 跑 H3 → 提帧 → 自检」
  #2 提示词纪律：内置「一镜一动作」模板，动作数量靠参数控制，不靠手写

用法：
  python flow.py --prompt "1girl, ..." --w 1344 --h 768 --steps 20 --phases 2 --dur 4
       --name test1                # 产物前缀
       --first-steps 8             # 首帧出图步数（anima turbo 用 8）
       --skip-first                # 复用已有首帧
       --dry-run                   # 只建作业文件，不跑 H3

产物：
  E:\\dsh-ai\\out\\flow\\<name>\\first_frame.png          首帧图
  E:\\dsh-ai\\out\\flow\\<name>\\job.json                 H3 作业文件
  E:\\dsh-ai\\out\\flow\\<name>\\<name>.mp4               视频
  E:\\dsh-ai\\out\\flow\\<name>\\frames\\*.png             抽帧
  E:\\dsh-ai\\out\\flow\\<name>\\report.txt                自检报告
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time

PY312 = r"$env:USERPROFILE\AppData\Local\Programs\Python\Python312\python.exe"
COMFYGEN = r"$env:DSH_HOME\comfy-tools\comfygen.py"
WAN = r"$env:DSH_AI\Wan2GP"
WAN_PY = os.path.join(WAN, r"env_venv\Scripts\python.exe")
FFMPEG = os.path.join(WAN, r"ffmpeg_bins\ffmpeg.exe")
OUTROOT = r"$env:DSH_AI\out\flow"

# H3 关键参数（实测得出，别乱改）
H3_MODEL = "minimax_h3_fl2va_pruned"
SAMPLER = "euler"                      # H3 只认 euler / er_sde / res_multistep / ralston_2s
MIN_SECONDS = 4.0                      # H3 最短 4 秒
FPS = 24

# 官方 FL2VA 提示词骨架（2026-10-09 按 MiniMax 官方规范改）
#   ① 第一行必须是对齐指令 ② 空一行 ③ 三个核心字段
#   ④ 正文写"首帧→尾帧的运动路径"，不重复描述静态图
#   ⑤ 镜头运动 = 类型 + 幅度 + 速度
ALIGN_TMPL = ("How the reference pictures align with the target video — "
              "Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
              "Picture 2 (from Shot 1) aligns with the {dur}-second mark of the target video.")
PROMPT_TMPL = """{align}

integrated_multimodal_description: [Shot 1] {action} {style_line}
overall_soundscape: {sound}
non_diegetic_music: {music}
"""


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def run(cmd, **kw):
    log("run: " + (cmd if isinstance(cmd, str) else " ".join(cmd)))
    return subprocess.run(cmd, **kw)


def build_prompt(action, style_line, sound, music, dur=4.0, use_official=True):
    """use_official=True 时按官方 FL2VA 格式（带对齐指令）；False 时退回旧写法"""
    if not use_official:
        return ("integrated_multimodal_description: [Shot 1] %s %s\n"
                "overall_soundscape: %s\nnon_diegetic_music: %s\n"
                % (action, style_line, sound, music))
    return PROMPT_TMPL.format(align=ALIGN_TMPL.format(dur="%.2f" % dur),
                              action=action, style_line=style_line,
                              sound=sound, music=music)



# ---------------------------------------------------------------- 角色档案
# 少女版与 Q 版是**两套底模 + 两套 LoRA**，触发词也不同（抄错就画不出角色）
CHARACTERS = {
    "girl": {
        "family": "illustrious",
        "lora": "DS-WhaleGirl-Illustrious-v10.safetensors",
        "lora_strength": "0.85",
        "steps": "28",
        "cfg": "6",
        "trigger": ("deepseek_whale_girl, deepseek_maid_outfit, 1girl, solo, blue hair, "
                    "very long hair, gradient blue hair, ahoge, whale fin ears, maid headdress, "
                    "navy dress, white frilled apron, blue hair bows"),
        "desc": "少女版（Illustrious + DS-WhaleGirl LoRA，符合外观规格：正常比例约 7 头身）",
    },
    "chibi": {
        "family": "anima",
        "lora": "DS-Chibi-Anima.safetensors",
        "lora_strength": "0.85",
        "steps": "8",
        "cfg": "1.5",
        "turbo": True,
        "trigger": ("Deepseek [chibi] musume, (chibi:1.5), 1girl, solo, maid headdress, fins, "
                    "ahoge, very long hair, blue hair"),
        "desc": "Q 版（Anima + DS-Chibi LoRA，半写实电影感强，萌系比例）",
    },
}

def gen_first_frame(prompt, w, h, steps, outdir, name, batch=2, character="chibi",
                    first_hires=False):
    """按角色档案出首帧（少女版走 Illustrious+WhaleGirl LoRA；Q版走 Anima+Chibi LoRA）
    ⚠️ 必须传 --width/--height：否则 comfygen 默认 1024x1024 方图，
       而 H3 会跟着首帧比例走 ⇒ 首帧方图 = 视频也方（实测踩过）"""
    prof = CHARACTERS.get(character, CHARACTERS["chibi"])
    dst = os.path.join(outdir, "first")
    os.makedirs(dst, exist_ok=True)
    cmd = [PY312, COMFYGEN, "--family", prof["family"],
           "--lora", prof["lora"], "--lora-strength", prof["lora_strength"],
           "--prompt", prompt, "--steps", prof["steps"], "--cfg", prof["cfg"],
           "--width", str(w), "--height", str(h),
           "--hires", "1.8", "--hires-denoise", "0.45",   # hires 提细节，随后缩放到目标尺寸
           "--batch", str(batch), "--out", dst]
    if prof.get("turbo"):
        cmd.append("--turbo")
    r = run(cmd)
    if r.returncode != 0:
        raise SystemExit("comfygen failed rc=%d" % r.returncode)
    pngs = sorted(f for f in os.listdir(dst) if f.lower().endswith(".png"))
    if not pngs:
        raise SystemExit("no first frame produced")
    newest = os.path.join(dst, pngs[-1])
    # 复制成固定名，方便复用
    fixed = os.path.join(outdir, "first_frame.png")
    # hires 会把图放大 1.8 倍 ⇒ 缩放到目标尺寸（用了高质量重采样，比直接小图出更细）
    try:
        from PIL import Image
        im = Image.open(newest).convert("RGB")
        if (im.width, im.height) != (w, h):
            im = im.resize((w, h), Image.LANCZOS)
            log("resize first frame: %dx%d -> %dx%d" % (im.width, im.height, w, h))
        im.save(fixed)
    except Exception as e:
        log("resize skipped (%s); copying raw" % e)
        with open(newest, "rb") as src, open(fixed, "wb") as dstf:
            dstf.write(src.read())
    log("first frame: %s (%.1f KB)" % (fixed, os.path.getsize(fixed) / 1024))
    return fixed


def build_job(first_frame, prompt, w, h, steps, phases, dur, outdir, name, end_frame=None):
    """生成 H3 作业文件。注意：两阶段靠 guidance_phases>1（不是 model_switch_phase）"""
    frames = max(int(round(dur * FPS)), 1)
    # 97 帧 = 4.04 秒（实测可用），保持 4n+1 的形状更稳
    frames = 97 if dur <= 4.05 else frames
    job = {
        "model_type": H3_MODEL,
        "prompt": prompt,
        "resolution": "%dx%d" % (w, h),
        "video_length": frames,
        "duration_seconds": 0,
        "num_inference_steps": steps,
        "sample_solver": SAMPLER,
        "guidance_phases": phases,          # ← 2 = 两阶段（低分辨率起草 + 精修）
        "guidance_scale": 5,
        "seed": -1,
        "batch_size": 1,
        "image_start": first_frame,
        "image_end": end_frame,
        "image_mode": 0,
        "image_prompt_type": ("SE" if end_frame else "S"),   # S=首帧, E=尾帧
        # 官方格式提示词是多行的 ⇒ 必须 FG，否则 WanGP 按换行拆成多个请求
        "multi_prompts_gen_type": "FG",
        "output_filename": name,
    }
    path = os.path.join(outdir, "job.json")
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=1)
    log("job: %s  res=%dx%d frames=%d steps=%d phases=%d" % (path, w, h, frames, steps, phases))
    return path


def run_h3(job_path, outdir):
    vout = os.path.join(outdir, "video")
    os.makedirs(vout, exist_ok=True)
    cmd = [WAN_PY, "wgp.py", "--process", job_path, "--output-dir", vout]
    t0 = time.time()
    r = run(cmd, cwd=WAN)
    el = time.time() - t0
    if r.returncode != 0:
        raise SystemExit("H3 failed rc=%d after %.0fs" % (r.returncode, el))
    mp4s = [f for f in os.listdir(vout) if f.lower().endswith(".mp4")]
    if not mp4s:
        raise SystemExit("no mp4 produced")
    mp4 = os.path.join(vout, sorted(mp4s)[-1])
    log("video: %s (%.2f MB, %.0fs)" % (mp4, os.path.getsize(mp4) / 1e6, el))
    return mp4, el


def extract_frames(mp4, outdir, every=0.4):
    dst = os.path.join(outdir, "frames")
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(dst):
        os.remove(os.path.join(dst, f))
    # 先取时长
    # ⚠️ 必须显式 utf-8 + errors=replace：ffmpeg 的 stderr 含非 GBK 字节，
    #    默认按系统码页(GBK)解码会抛 UnicodeDecodeError 并把 stderr 变成 None（2026-10-09 实测）
    probe = subprocess.run([FFMPEG, "-hide_banner", "-i", mp4], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    dur = 4.5
    for line in probe.stderr.splitlines():
        if "Duration:" in line:
            hms = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = hms.split(":")
            dur = int(h) * 3600 + int(m) * 60 + float(s)
    n = int(dur / every) + 1
    for i in range(n):
        t = round(i * every, 2)
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", str(t),
                        "-i", mp4, "-frames:v", "1", "-vf", "scale=480:-2",
                        os.path.join(dst, "f%02d.png" % i)], capture_output=True)
    got = sorted(os.listdir(dst))
    log("frames: %d (dur %.2fs, every %.2fs)" % (len(got), dur, every))
    return dst, dur


def frame_selfcheck(frames_dir, report_path):
    """逐帧像素突变检测：相邻帧差异的中位数 + 3×MAD 判异常（纯算法，无模型）"""
    code = r'''
import glob, json, os, sys
from PIL import Image, ImageChops
import statistics as st
fs = sorted(glob.glob(os.path.join(sys.argv[1], "*.png")))
if len(fs) < 3:
    print("too few frames"); sys.exit(0)
diffs, sizes = [], []
prev = None
for f in fs:
    im = Image.open(f).convert("L")
    sizes.append(im.size)
    if prev is not None:
        d = ImageChops.difference(im, prev)
        h = d.histogram()
        tot = sum(h)
        mean = sum(i * c for i, c in enumerate(h)) / tot
        diffs.append(round(mean, 2))
    prev = im
med = st.median(diffs)
mad = st.median([abs(d - med) for d in diffs]) or 1.0
out = {"frames": len(fs), "size": sizes[0], "diff_median": med, "diff_mad": mad,
       "diffs": diffs}
out["outliers"] = [i + 1 for i, d in enumerate(diffs) if d > med + 3 * mad]
print(json.dumps(out, ensure_ascii=False))
'''
    tmp = os.path.join(os.path.dirname(report_path), "_selfcheck.py")
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([PY312, tmp, frames_dir], capture_output=True, text=True, encoding="utf-8")
    raw = (r.stdout or "").strip().splitlines()
    info = raw[-1] if raw else "{}"
    try:
        data = json.loads(info)
    except Exception:
        data = {}
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--first-hires", action="store_true",
                    help="首帧也开 hires（会放大 1.8 倍，与目标视频尺寸不匹配，仅在需要大图时用）")
    ap.add_argument("--character", default="chibi", choices=["girl", "chibi"],
                    help="角色版本：girl=少女版(Illustrious) / chibi=Q版(Anima)")
    ap.add_argument("--name", required=True, help="产物前缀（会建同名目录）")
    ap.add_argument("--prompt", help="首帧出图 prompt（角色+风格）；--skip-first 时可不填")
    ap.add_argument("--action", default="A girl stands still on a stone breakwater. The camera pushes in slowly from a medium shot toward her face.",
                    help="【一镜一动作】镜头里只允许一个动作")
    ap.add_argument("--style-line", default="2D semi-realistic anime, cinematic golden-hour light, detailed background by the sea.",
                    help="画面风格补充")
    ap.add_argument("--sound", default="Steady wind, gentle waves, distant gull cries.",
                    help="overall_soundscape 段")
    ap.add_argument("--music", default="One warm sustained string note fading at the end.",
                    help="non_diegetic_music 段")
    ap.add_argument("--w", type=int, default=1344)
    ap.add_argument("--h", type=int, default=768)
    ap.add_argument("--steps", type=int, default=20, help="H3 去噪步数（480p 用 8，720p 建议 20）")
    ap.add_argument("--phases", type=int, default=2, help="1=单阶段 2=两阶段（低分起草+精修）")
    ap.add_argument("--dur", type=float, default=4.0)
    ap.add_argument("--first-steps", type=int, default=8, help="首帧出图步数")
    ap.add_argument("--skip-first", action="store_true", help="复用已有 first_frame.png")
    ap.add_argument("--legacy-prompt", action="store_true",
                    help="用旧的简略提示词写法（无官方对齐指令），仅用于对比")
    ap.add_argument("--end-frame", help="尾帧图路径：给了就走首尾帧驱动（H3 FL2VA 的 image_end）")
    ap.add_argument("--dry-run", action="store_true", help="只出首帧+建作业，不跑 H3")
    args = ap.parse_args()

    outdir = os.path.join(OUTROOT, args.name)
    os.makedirs(outdir, exist_ok=True)

    t_start = time.time()
    # ① 首帧
    first = os.path.join(outdir, "first_frame.png")
    if args.skip_first and os.path.exists(first):
        log("reuse first frame: %s" % first)
    else:
        prof = CHARACTERS.get(args.character, CHARACTERS["chibi"])
        full_prompt = (args.prompt if args.prompt else prof["trigger"])
        if args.prompt and args.character:
            full_prompt = prof["trigger"] + ", " + args.prompt
        log("character: %s" % prof["desc"])
        first = gen_first_frame(full_prompt, args.w, args.h, args.first_steps, outdir, args.name,
                                character=args.character,
                                first_hires=args.first_hires)

    # ② 作业文件
    prompt = build_prompt(args.action, args.style_line, args.sound, args.music,
                          dur=args.dur, use_official=not args.legacy_prompt)
    job = build_job(first, prompt, args.w, args.h, args.steps, args.phases, args.dur, outdir, args.name,
                    end_frame=getattr(args, "end_frame", None))

    if args.dry_run:
        log("dry-run: stop before H3")
        return 0

    # ③ H3
    mp4, h3_el = run_h3(job, outdir)

    # ④ 抽帧 + 自检
    frames_dir, dur = extract_frames(mp4, outdir)
    report_path = os.path.join(outdir, "report.txt")
    data = frame_selfcheck(frames_dir, report_path)

    lines = []
    lines.append("name: %s" % args.name)
    lines.append("resolution: %dx%d | frames: %d | steps: %d | phases: %d" % (args.w, args.h, 97 if args.dur <= 4.05 else int(args.dur * FPS), args.steps, args.phases))
    lines.append("video: %s (%.2f MB)" % (mp4, os.path.getsize(mp4) / 1e6))
    lines.append("timing: first frame + h3 = %.0fs (h3 alone %.0fs)" % (time.time() - t_start, h3_el))
    if data:
        lines.append("frame diffs: median=%.2f mad=%.2f" % (data.get("diff_median", -1), data.get("diff_mad", -1)))
        lines.append("outlier frames (突变嫌疑): %s" % (data.get("outliers") or "none"))
        lines.append("diffs: %s" % data.get("diffs"))
    with io.open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log("report: %s" % report_path)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
