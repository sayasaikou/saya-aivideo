#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upscale.py —— 用 Real-ESRGAN 把裁块超分（理论效果最好的那条路）

════════════════════════════════════════════════════════════════════
为什么要有这个脚本（以及它和"锐化"的区别）
════════════════════════════════════════════════════════════════════

识图这条线对"看得清"的需求，实测下来是三层的，一层比一层强、也一层比一层危险：

  ① 裁图放大（LANCZOS）  —— 不改变内容，只是把已有像素摊开   ✅ 绝对安全
  ② 感知式锐化（unsharp）—— 让已有边缘更好读，不新增内容     ✅ 基本安全
  ③ AI 超分（本脚本）    —— **模型"补"出原图没有的细节**     ⚠️ 有风险

本机实测：前两层已经能解决"整图问会看错"的主因（人物被切/被缩小），
所以本脚本是**第三层、可选、按需**，不是默认流程。

⚠️ 三条纪律（写死，改脚本前先读）
  1. **颜色判断绝不用超分结果** —— 超分会改像素值，取色一律在原始裁块上做。
  2. **超分结果要标出来源** —— 上层（模型/人）必须知道"这段描述基于超分图"，
     这样万一超分编了细节，责任链是清楚的。
  3. **只在裁块小的时候用** —— 裁块已经够大（比如长边 >1600）就别超分，
     收益低、还多一层失真。

════════════════════════════════════════════════════════════════════
用法
════════════════════════════════════════════════════════════════════

    python upscale.py <图片> [--model anime|video|general] [--out <输出>]
                      [--tile 512] [--no-start] [--dry-run]

模型选择建议：
    anime   = RealESRGAN_x4plus_anime_6B —— **二次元插画首选**（就是给它训的）
    video   = realesr-animevideov3       —— 更快、更轻，适合批量
    general = realesr-general-x4v3       —— 照片/写实，插画别用

依赖：ComfyUI 的 venv（E:\\dsh-ai\\venv）＋ ComfyUI 服务（默认 127.0.0.1:8188）
     ⚠️ 这些模型是给 ComfyUI 的 upscale 节点用的，脚本通过它的 HTTP API 调用 ——
        这样不用再装一份 torch，也不用维护第二套推理代码。
"""

import argparse
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

COMFY = "http://127.0.0.1:8188"
COMFY_VENV_PY = r"$env:DSH_AI\venv\Scripts\python.exe"
COMFY_MAIN = r"$env:DSH_AI\ComfyUI-master\main.py"
MODELS_DIR = r"$env:DSH_AI\ComfyUI\models\upscale_models"

MODEL_FILES = {
    "anime": "RealESRGAN_x4plus_anime_6B.pth",
    "video": "realesr-animevideov3.pth",
    "general": "realesr-general-x4v3.pth",
}


def comfy_alive(timeout=3):
    try:
        with urllib.request.urlopen(COMFY + "/system_stats", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def start_comfy(wait_s=90):
    """把 ComfyUI 拉起来（它没在跑的时候）。⚠️ 必须带那两个 disable 参数，
    否则会撞 comfy_aimdo 的 hostbuf_file_reader_read failed 并直接崩进程。"""
    print("  ComfyUI 没在跑，拉起它……")
    cmd = [COMFY_VENV_PY, COMFY_MAIN,
           "--disable-pinned-memory", "--disable-async-offload",
           "--listen", "127.0.0.1", "--port", "8188"]
    subprocess.Popen(cmd, cwd=r"$env:DSH_AI\ComfyUI-master",
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    t0 = time.time()
    while time.time() - t0 < wait_s:
        if comfy_alive():
            print("  ✓ ComfyUI 就绪（%.1fs）" % (time.time() - t0))
            return True
        time.sleep(2)
    return False


def upload(image_path):
    """POST /upload/image —— multipart，手写以免依赖 requests"""
    boundary = "----dsh" + uuid.uuid4().hex
    with open(image_path, "rb") as fh:
        data = fh.read()
    name = os.path.basename(image_path)
    body = io.BytesIO()

    def w(s):
        body.write(s.encode("utf-8") if isinstance(s, str) else s)

    w("--%s\r\n" % boundary)
    w('Content-Disposition: form-data; name="image"; filename="%s"\r\n' % name)
    w("Content-Type: application/octet-stream\r\n\r\n")
    w(data)
    w("\r\n--%s\r\n" % boundary)
    w('Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n')
    w("--%s--\r\n" % boundary)

    req = urllib.request.Request(
        COMFY + "/upload/image", data=body.getvalue(),
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def build_workflow(uploaded_name, model_file, tile):
    """最小工作流：LoadImage → UpscaleModelLoader → ImageUpscaleWithModel → SaveImage"""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": uploaded_name}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model_file}},
        "3": {"class_type": "ImageUpscaleWithModel",
              "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": "sr", "images": ["3", 0]}},
    }


def run_prompt(workflow):
    payload = json.dumps({"prompt": workflow, "client_id": uuid.uuid4().hex}).encode("utf-8")
    req = urllib.request.Request(COMFY + "/prompt", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_history(pid, timeout_s=600):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            with urllib.request.urlopen(COMFY + "/history/" + pid, timeout=15) as r:
                h = json.loads(r.read().decode("utf-8"))
            if pid in h:
                return h[pid]
        except Exception:
            pass
        time.sleep(1.5)
    return None


def fetch_output(hist, out_path):
    outs = hist.get("outputs", {})
    for node in outs.values():
        for img in node.get("images", []):
            q = urllib.request.urlopen(
                "%s/view?filename=%s&subfolder=%s&type=%s" % (
                    COMFY, urllib.parse.quote(img["filename"]),
                    urllib.parse.quote(img.get("subfolder", "")), img.get("type", "output")),
                timeout=180)
            with open(out_path, "wb") as fh:
                fh.write(q.read())
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Real-ESRGAN 超分（走 ComfyUI API）")
    ap.add_argument("image")
    ap.add_argument("--model", default="anime", choices=list(MODEL_FILES))
    ap.add_argument("--out")
    ap.add_argument("--tile", type=int, default=512, help="保留项，当前工作流整图处理")
    ap.add_argument("--no-start", action="store_true", help="不要自动拉起 ComfyUI")
    ap.add_argument("--out-long-side", type=int, default=1600,
                    help="输出目标长边（默认 1600）。输入超过它的 1/4 会先预缩")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.image):
        print("ERROR: 找不到图片 %s" % args.image)
        return 2

    model_file = MODEL_FILES[args.model]
    model_path = os.path.join(MODELS_DIR, model_file)
    if not os.path.isfile(model_path):
        print("ERROR: 模型不存在 %s" % model_path)
        return 3

    from PIL import Image

    # ── 先决定"喂给超分模型的输入尺寸"
    #
    # ⚠️ 这一步是本脚本最重要的设计，改过一次，理由是实测：
    #   最初直接拿裁块去超分 —— 一个 2545x1430 的裁块乘 4 变成 **10180x5720 = 38.8 MB**，
    #   视觉模型根本吃不下这么大的图，等于白跑。
    #   而且那个裁块**本来就够清楚**，再放大 4 倍没有任何意义。
    #
    #   Real-ESRGAN 真正有价值的地方恰恰相反：**输入越小越糊，它补出来的细节越多**。
    #   所以正确姿势是：把输入**缩到目标尺寸的 1/4**，再让模型放大 4 倍 ——
    #   这样输出正好是目标尺寸，而细节是模型"补"出来的（而不是 Lanczos 插值撑的）。
    #
    #   例：想要一张 1600 长的图 → 喂 400 → 超分 x4 = 1600（细节由模型补）
    work = args.image
    tmp_input = None
    with Image.open(args.image) as im:
        w0, h0 = im.size
        long_side = max(w0, h0)
        # 输入长边目标：输出目标 / 4
        in_target = max(64, int(args.out_long_side / 4))
        if long_side > in_target * 1.15:
            k = in_target / float(long_side)
            nw, nh = max(1, int(w0 * k)), max(1, int(h0 * k))
            tmp_input = os.path.splitext(args.image)[0] + "_sr_in.png"
            im.convert("RGB").resize((nw, nh), Image.LANCZOS).save(tmp_input, "PNG")
            work = tmp_input
            print("预缩: %dx%d -> %dx%d（再超分 x4 得到约 %d 长边）"
                  % (w0, h0, nw, nh, args.out_long_side))
        else:
            print("输入已足够小，直接超分 x%d" % 4)

    with Image.open(work) as im2:
        wi, hi = im2.size
    print("输入: %s  %dx%d" % (os.path.basename(args.image), w0, h0))
    print("模型: %s (%s)" % (args.model, model_file))
    print("预期输出: %dx%d (x4 of %dx%d)" % (wi * 4, hi * 4, wi, hi))

    if args.dry_run:
        print("DRY RUN：不执行。")
        return 0

    if not comfy_alive():
        if args.no_start:
            print("ERROR: ComfyUI 没在跑，且指定了 --no-start")
            return 4
        if not start_comfy():
            print("ERROR: ComfyUI 起不来")
            return 4

    t0 = time.time()
    up = upload(work)
    name = up.get("name") or os.path.basename(args.image)
    sub = up.get("subfolder") or ""
    ref = (sub + "/" + name) if sub else name

    res = run_prompt(build_workflow(ref, model_file, args.tile))
    pid = res.get("prompt_id")
    if not pid:
        print("ERROR: 提交失败: %s" % json.dumps(res)[:300])
        return 5

    hist = wait_history(pid)
    if hist is None:
        print("ERROR: 超时没等到结果")
        return 6

    out = args.out or (os.path.splitext(args.image)[0] + "_sr4x.png")
    if not fetch_output(hist, out):
        print("ERROR: 结果里没有图片输出")
        return 7

    # 收尾：把超分结果缩到目标长边（超分给的是"清晰的像素"，尺寸由我们定）
    if args.out_long_side and max(Image.open(out).size) > args.out_long_side * 1.15:
        with Image.open(out) as im:
            ow, oh = im.size
            k = args.out_long_side / float(max(ow, oh))
            im.convert("RGB").resize((max(1, int(ow * k)), max(1, int(oh * k))),
                                     Image.LANCZOS).save(out, "PNG")
            print("收尾缩放: %dx%d -> %dx%d" % (ow, oh, int(ow * k), int(oh * k)))

    with Image.open(out) as im:
        w1, h1 = im.size
    mb = os.path.getsize(out) / 1024 / 1024
    print("out=%s" % out)
    print("size=%dx%d" % (w1, h1))
    print("scale=%.2f" % (w1 / max(1, w0)))
    print("bytes=%d" % os.path.getsize(out))
    print("seconds=%.1f" % (time.time() - t0))
    print("MB=%.2f" % mb)
    print("caution=超分会补出原图没有的细节；颜色判断请用超分【之前】的图取色")
    return 0


if __name__ == "__main__":
    sys.exit(main())
