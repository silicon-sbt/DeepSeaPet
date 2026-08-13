"""SDXL img2img + IP-Adapter 生成精灵图：身份锁定（IP-Adapter）+ 构图起点（img2img）。

在 GPU 模式跑：
  /root/miniconda3/bin/python -u generate_sdxl.py happy
先跑一张"开心微笑"测试图，验证 IP-Adapter 单图能否锁住 Q 版角色身份，
再决定是否扩展到批量 7 状态。
"""
import os, sys, time, torch
from diffusers import StableDiffusionXLImg2ImgPipeline, DPMSolverMultistepScheduler
from diffusers.utils import load_image

MODEL = "/root/autodl-tmp/models/animagineXL40_v40.safetensors"
IPA   = "/root/autodl-tmp/ip_adapter"
REF   = "/root/autodl-tmp/sprites_output/idle/idle_00.png"
OUTDIR = "/root/autodl-tmp/sprites_video"

NEG = ("lowres, bad anatomy, bad hands, missing fingers, extra digits, extra arms, "
       "extra legs, deformed, worst quality, low quality, normal quality, "
       "jpeg artifacts, signature, watermark, username, blurry")

# 各状态的动作 prompt（danbooru 标签风格，身份由 IP-Adapter 锁定）
STATES = {
    "happy": "1girl, chibi, blue hair, whale tail, maid outfit, smile, open mouth, "
             "happy, white background, simple background, solo",
    "idle":  "1girl, chibi, blue hair, whale tail, maid outfit, standing, "
             "white background, simple background, solo",
    "held":  "1girl, chibi, blue hair, whale tail, maid outfit, "
             "dangling in the air, limbs flailing, scared, surprised, "
             "open mouth, wide eyes, white background, simple background, solo",
    "flying": "1girl, chibi, blue hair, whale tail, maid outfit, "
              "flying through the air, horizontal pose, arms and legs spread, "
              "screaming, eyes closed, tears, open mouth, motion lines, "
              "white background, simple background, solo",
}

def main():
    state = sys.argv[1] if len(sys.argv) > 1 else "happy"
    prompt = STATES.get(state, STATES["happy"])
    out = os.path.join(OUTDIR, f"{state}_test.png")

    print("[1/4] 加载 SDXL (Animagine XL 4.0) ...", flush=True)
    pipe = StableDiffusionXLImg2ImgPipeline.from_single_file(
        MODEL, torch_dtype=torch.float16)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(
        pipe.scheduler.config, use_karras_sigmas=True)

    print("[2/4] 加载 IP-Adapter ...", flush=True)
    pipe.load_ip_adapter(IPA, subfolder="sdxl_models",
                         weight_name="ip-adapter-plus_sdxl_vit-h.safetensors")
    pipe.set_ip_adapter_scale(0.8)
    pipe.to("cuda")

    print("[3/4] 读基准图 ...", flush=True)
    ref = load_image(REF).convert("RGB").resize((1024, 1024))

    print(f"[4/4] 生成 {state} 测试图 ...", flush=True)
    t = time.time()
    img = pipe(
        prompt=prompt,
        negative_prompt=NEG,
        image=ref,             # img2img 输入：构图/姿势起点
        ip_adapter_image=ref,  # IP-Adapter：身份锁定
        num_inference_steps=30,
        strength=0.55,
        guidance_scale=6.0,
        height=1024, width=1024,
        generator=torch.Generator("cuda").manual_seed(20260813),
    ).images[0]
    os.makedirs(OUTDIR, exist_ok=True)
    img.save(out)
    print(f"完成，耗时 {time.time()-t:.1f}s -> {out}", flush=True)

if __name__ == "__main__":
    main()
