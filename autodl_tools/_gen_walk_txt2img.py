"""AutoDL: SDXL txt2img + IP-Adapter 生成 walk 迈步左右腿两帧。
历史教训：walk 用站姿 idle 做 img2img 起点 → SDXL 迈不开腿（姿态被起点锁死）。
改走 txt2img（strength 1.0 = 纯文生图）+ IP-Adapter 身份锁定，迈步姿态完全交给 prompt 描述。

用法：/root/miniconda3/bin/python -u _gen_walk_txt2img.py
"""
import os, time, torch
from diffusers import StableDiffusionXLImg2ImgPipeline, DPMSolverMultistepScheduler
from diffusers.utils import load_image

MODEL = "/root/autodl-tmp/models/animagineXL40_v40.safetensors"
IPA   = "/root/autodl-tmp/ip_adapter"
REF   = "/root/autodl-tmp/sprites_output/idle/idle_00.png"  # 身份参考（白底单角色）
OUT   = "/root/autodl-tmp/sprites_output/walk"

NEG = ("lowres, bad anatomy, bad hands, missing fingers, extra digits, extra arms, "
       "extra legs, deformed, worst quality, low quality, normal quality, "
       "jpeg artifacts, signature, watermark, username, blurry, collage, "
       "multiple characters, grid, frame, borders, "
       "standing still, static pose, legs together, stiff, straight legs")

BASE = ("1girl, chibi, blue hair, whale tail, maid outfit, full body, "
        "white background, simple background, solo, walking to the right, "
        "side view, dynamic walking stride, arms swinging, skirt flowing")

# 左右腿两帧：同一走姿的两个相位（统一朝右），强动作词对抗 IP-Adapter 的站姿惯性
PROMPTS = {
    "walk_00": BASE + ", LEFT leg lifted forward mid-step, knee bent, heel raised, "
               "RIGHT leg extended back pushing off the ground, toes pointed down, motion",
    "walk_01": BASE + ", RIGHT leg lifted forward mid-step, knee bent, heel raised, "
               "LEFT leg extended back pushing off the ground, toes pointed down, motion",
}

SIZE = 1024
SEED0 = 20260814


def main():
    print("加载 SDXL + IP-Adapter ...", flush=True)
    pipe = StableDiffusionXLImg2ImgPipeline.from_single_file(
        MODEL, torch_dtype=torch.float16)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(
        pipe.scheduler.config, use_karras_sigmas=True)
    pipe.load_ip_adapter(IPA, subfolder="sdxl_models",
                         weight_name="ip-adapter-plus_sdxl_vit-h.safetensors")
    pipe.set_ip_adapter_scale(0.6)  # 0.6 而非 0.8：身份参考图是站姿，权重太高会把迈步姿态拉回站姿
    pipe.to("cuda")

    print("读身份参考图 ...", flush=True)
    ref = load_image(REF).convert("RGB").resize((SIZE, SIZE))
    os.makedirs(OUT, exist_ok=True)

    for si, (name, prompt) in enumerate(PROMPTS.items()):
        t0 = time.time()
        img = pipe(
            prompt=prompt, negative_prompt=NEG,
            image=ref,              # img2img 管线需要 image；strength=1.0 → 纯 txt2img
            ip_adapter_image=ref,   # 身份锁定
            num_inference_steps=30, strength=1.0, guidance_scale=6.0,
            height=SIZE, width=SIZE,
            generator=torch.Generator("cuda").manual_seed(SEED0 + si),
        ).images[0]
        img.save(os.path.join(OUT, f"{name}.png"))
        print(f"[{name}] 完成，耗时 {time.time()-t0:.1f}s -> {OUT}", flush=True)

    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
