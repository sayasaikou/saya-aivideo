# -*- coding: utf-8 -*-
"""comfy-bg.py -- 用 ComfyUI 出「背景」：深度 ControlNet 锁结构 + 风格 LoRA 定画风（2026-10-13 立）

为何走这条：Z-Image 不支持参考图（pipeline 里 input_ref_images 只在 inpainting 分支被读），
而社区对「保持原版场景画风」的标准做法就是：**ControlNet 管结构 + 风格 LoRA 管画风**。
本机的 controlnet-union-sdxl-1.0-promax 是 Union 版，一个模型就能吃 depth 控制图。

与 cn-paint.py 的区别：
  - 控制图用 **已算好的深度图**（不走 Canny）-> type='depth'
  - 多了 LoraLoader（风格 LoRA）
  - denoise=1.0（不重绘底图，完全由深度图 + 提示词生成）

用法:
  python comfy-bg.py --depth <深度图.png> --prompt-file <提示词.txt> --name <产物名>
         [--ckpt Illustrious-XL-v1.0.safetensors] [--lora arknights-scenery-SDXL.safetensors]
         [--lora-strength 0.8] [--cn-strength 0.8] [--steps 28] [--seed 424242]
产物:
  ComfyUI 输出目录\<name>_00001_.png，并复制到 $env:DSH_AI\out\flow\<name>\images\
"""
import argparse
import io
import json
import os
import shutil
import time
import urllib.request

HOST = 'http://127.0.0.1:8188'
COMFY_INPUT = r'$env:DSH_AI\ComfyUI-master\input'
OUTROOT = r'$env:DSH_AI\out\flow'
CN_NAME = 'controlnet-union-sdxl-1.0-promax.safetensors'

NEG_DEFAULT = ('people, human, character, figure, hands, arms, face, 1girl, solo, '
               'low quality, worst quality, blurry, jpeg artifacts, watermark, '
               'text, signature, chinese ancient style, wooden house, medieval castle, '
               'rustic farmhouse, low-poly, 3d render, cgi, photorealistic, dirty, grimy')


def post(path, payload):
    req = urllib.request.Request(HOST + path, data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode('utf-8'))


def get(path):
    with urllib.request.urlopen(HOST + path, timeout=300) as r:
        return json.loads(r.read().decode('utf-8'))


def upload_image(local_path):
    """把本地图上传到 ComfyUI 的 input 目录（走 /upload/image，不要直接拷文件）"""
    import mimetypes
    import uuid
    boundary = '----dsh' + uuid.uuid4().hex
    name = os.path.basename(local_path)
    ctype = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    with open(local_path, 'rb') as f:
        data = f.read()
    body = b''
    body += ('--%s\r\n' % boundary).encode()
    body += ('Content-Disposition: form-data; name="image"; filename="%s"\r\n' % name).encode()
    body += ('Content-Type: %s\r\n\r\n' % ctype).encode()
    body += data + b'\r\n'
    body += ('--%s\r\n' % boundary).encode()
    body += b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
    body += ('--%s--\r\n' % boundary).encode()
    req = urllib.request.Request(HOST + '/upload/image', data=body,
                                 headers={'Content-Type': 'multipart/form-data; boundary=%s' % boundary})
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.loads(r.read().decode('utf-8'))
    sub = res.get('subfolder') or ''
    return ('%s/%s' % (sub, res['name'])) if sub else res['name']


def build(args, img_name, positive, negative, seed):
    wf = {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': args.ckpt}},
        '2': {'class_type': 'LoadImage', 'inputs': {'image': img_name, 'upload': 'image'}},
        '4': {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': CN_NAME}},
        '5': {'class_type': 'SetUnionControlNetType',
              'inputs': {'control_net': ['4', 0], 'type': 'depth'}},
        '6': {'class_type': 'CLIPTextEncode', 'inputs': {'text': positive, 'clip': ['1', 1]}},
        '7': {'class_type': 'CLIPTextEncode', 'inputs': {'text': negative, 'clip': ['1', 1]}},
        '9': {'class_type': 'ControlNetApplyAdvanced',
              'inputs': {'positive': ['6', 0], 'negative': ['7', 0], 'control_net': ['5', 0],
                         'image': ['2', 0], 'strength': args.cn_strength,
                         'start_percent': 0.0, 'end_percent': args.cn_end}},
        '10': {'class_type': 'KSampler',
               'inputs': {'model': ['1', 0], 'seed': seed, 'steps': args.steps, 'cfg': args.cfg,
                          'sampler_name': args.sampler, 'scheduler': args.scheduler,
                          'positive': ['9', 0], 'negative': ['9', 1],
                          'latent_image': ['11', 0], 'denoise': 1.0}},
        '11': {'class_type': 'EmptyLatentImage',
               'inputs': {'width': args.width, 'height': args.height, 'batch_size': 1}},
        '12': {'class_type': 'VAEDecode', 'inputs': {'samples': ['10', 0], 'vae': ['1', 2]}},
        '13': {'class_type': 'SaveImage',
               'inputs': {'images': ['12', 0], 'filename_prefix': args.name}},
    }
    if args.lora:
        wf['3'] = {'class_type': 'LoraLoader',
                   'inputs': {'model': ['1', 0], 'clip': ['1', 1], 'lora_name': args.lora,
                              'strength_model': args.lora_strength,
                              'strength_clip': args.lora_strength}}
        for node, slot in (('6', 1), ('7', 1)):
            wf[node]['inputs']['clip'] = ['3', 1]
        wf['10']['inputs']['model'] = ['3', 0]
    return wf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--depth', required=True)
    ap.add_argument('--prompt-file', required=True, dest='prompt_file')
    ap.add_argument('--name', required=True)
    ap.add_argument('--ckpt', default='Illustrious-XL-v1.0.safetensors')
    ap.add_argument('--lora', default='arknights-scenery-SDXL.safetensors')
    ap.add_argument('--lora-strength', type=float, default=0.8, dest='lora_strength')
    ap.add_argument('--negative', default=None)
    ap.add_argument('--cn-strength', type=float, default=0.8, dest='cn_strength')
    ap.add_argument('--cn-end', type=float, default=0.85, dest='cn_end')
    ap.add_argument('--steps', type=int, default=28)
    ap.add_argument('--cfg', type=float, default=6.0)
    ap.add_argument('--sampler', default='euler_ancestral')
    ap.add_argument('--scheduler', default='karras')
    ap.add_argument('--seed', type=int, default=424242)
    ap.add_argument('--width', type=int, default=1344)
    ap.add_argument('--height', type=int, default=768)
    args = ap.parse_args()

    for p in (args.depth, args.prompt_file):
        if not os.path.exists(p):
            raise SystemExit('missing: %s' % p)

    outdir = os.path.join(OUTROOT, args.name)
    images = os.path.join(outdir, 'images')
    os.makedirs(images, exist_ok=True)

    positive = io.open(args.prompt_file, encoding='utf-8').read().strip()
    negative = args.negative if args.negative is not None else NEG_DEFAULT

    img_name = upload_image(args.depth)
    print('[bg] uploaded depth -> %s' % img_name)
    seed = args.seed if args.seed >= 0 else int(time.time()) % (2 ** 31)
    wf = build(args, img_name, positive, negative, seed)
    with io.open(os.path.join(outdir, 'workflow.json'), 'w', encoding='utf-8') as f:
        json.dump(wf, f, ensure_ascii=False, indent=1)

    print('[bg] ckpt=%s lora=%s(%.2f) cn=depth/%.2f steps=%d cfg=%.1f seed=%d'
          % (args.ckpt, args.lora, args.lora_strength, args.cn_strength, args.steps, args.cfg, seed))
    res = post('/prompt', {'prompt': wf, 'client_id': 'comfy-bg'})
    pid = res.get('prompt_id')
    if not pid:
        raise SystemExit('submit rejected: %s' % json.dumps(res, ensure_ascii=False)[:600])
    print('[bg] prompt_id=%s  waiting...' % pid)

    t0 = time.time()
    while True:
        if time.time() - t0 > 900:
            raise SystemExit('timeout waiting for render')
        time.sleep(2)
        hist = get('/history/%s' % pid)
        if pid not in hist:
            continue
        entry = hist[pid]
        status = (entry.get('status') or {})
        if status.get('status_str') == 'error' or not status.get('completed', True):
            msgs = status.get('messages') or []
            raise SystemExit('render error: %s' % json.dumps(msgs, ensure_ascii=False)[:900])
        outs = entry.get('outputs') or {}
        saved = []
        for node in outs.values():
            for im in (node.get('images') or []):
                saved.append(im)
        if not saved:
            continue
        print('[bg] done in %.0fs' % (time.time() - t0))
        for im in saved:
            src = os.path.join(r'$env:DSH_AI\ComfyUI-master\output', im.get('subfolder') or '', im['filename'])
            dst = os.path.join(images, im['filename'])
            if os.path.exists(src):
                shutil.copy2(src, dst)
                print('[bg]   %s  %.2f MB' % (dst, os.path.getsize(dst) / 1e6))
            else:
                print('[bg]   (not found) %s' % src)
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
