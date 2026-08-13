"""SDXL + IP-Adapter 批量生成精灵图：身份锁定（IP-Adapter）+ 姿势派生（img2img）。

在 GPU 模式跑：
  /root/miniconda3/bin/python -u generate_sdxl.py             # 批量 9 状态
  /root/miniconda3/bin/python -u generate_sdxl.py happy idle  # 指定状态

方案：身份层 + 姿势层分离。
- img2img 状态：从 idle 基准图派生（strength 0.55 改姿势）
- txt2img 状态：悬空/横飞/横趴构图差异大，单独生成基准（strength 1.0
  等价纯 txt2img，仅靠 IP-Adapter 锁身份）
- 帧 1-7 从帧 0 微调（strength 0.35），靠不同 seed 产生细微变化

注意：SDXL img2img 无法精确控制逐帧动作，动画靠「同一姿势的细微变体」
拼合，帧间可能有轻微闪烁——下载后先用 rembg 抠图、8fps 播放看实际效果。
"""
import os, sys, time, torch
from diffusers import StableDiffusionXLImg2ImgPipeline, DPMSolverMultistepScheduler
from diffusers.utils import load_image

MODEL = "/root/autodl-tmp/models/animagineXL40_v40.safetensors"
IPA   = "/root/autodl-tmp/ip_adapter"
REF   = "/root/autodl-tmp/sprites_output/idle/idle_00.png"  # 基准图（黑皮鞋版，需先上传）
OUTDIR = "/root/autodl-tmp/sprites_output"

NEG = ("lowres, bad anatomy, bad hands, missing fingers, extra digits, extra arms, "
       "extra legs, deformed, worst quality, low quality, normal quality, "
       "jpeg artifacts, signature, watermark, username, blurry")

BASE_SEED = 20260813
FRAME0_STR = {"img2img": 0.55, "txt2img": 1.0}  # 帧 0 的 strength
FRAME_STR = 0.35                                 # 帧 1-7 从帧 0 微调
STEPS = 30
GUIDANCE = 6.0
SIZE = 1024

# 各状态：mode + 动作 prompt（身份由 IP-Adapter 锁定，动作词控制姿势）
BASE = "1girl, chibi, blue hair, whale tail, maid outfit, "
STATES = {
    # 站立/坐姿类：从 idle 基准 img2img 派生
    "idle":  ("img2img", BASE + "standing, arms at sides, looking at viewer, "
              "white background, simple background, solo"),
    "happy": ("img2img", BASE + "smile, open mouth, happy, jumping, arms raised, "
              "excited, white background, simple background, solo"),
    "walk":  ("img2img", BASE + "walking, side view, arms swinging, one leg forward, "
              "white background, simple background, solo"),
    "hide":  ("img2img", BASE + "crouching, sneaking away, shrinking, embarrassed, "
              "white background, simple background, solo"),
    "peek":  ("img2img", BASE + "peeking from edge, curious, half body, holding onto edge, "
              "white background, simple background, solo"),
    "sleep": ("img2img", BASE + "sleeping, curled up, hugging knees, eyes closed, relaxed, "
              "white background, simple background, solo"),
    # 悬空/横飞/横趴：构图差异大，单独 txt2img 生成基准
    "lying": ("txt2img", BASE + "lying on stomach, horizontal pose, resting head on hands, "
              "relaxed, white background, simple background, solo"),
    "held":  ("txt2img", BASE + "dangling in the air, limbs flailing, scared, surprised, "
              "open mouth, wide eyes, white background, simple background, solo"),
    "flying": ("txt2img", BASE + "flying through the air, horizontal pose, arms and legs spread, "
               "screaming, eyes closed, tears, open mouth, motion lines, "
               "white background, simple background, solo"),
}


def gen(pipe, prompt, image, ip_image, strength, seed):
    return pipe(
        prompt=prompt,
        negative_prompt=NEG,
        image=image,
        ip_adapter_image=ip_image,
        num_inference_steps=STEPS,
        strength=strength,
        guidance_scale=GUIDANCE,
        height=SIZE, width=SIZE,
        generator=torch.Generator("cuda").manual_seed(seed),
    ).images[0]


def main():
    states = sys.argv[1:] or list(STATES.keys())
    print(f"目标状态：{states}", flush=True)

    print("[1/3] 加载 SDXL (Animagine XL 4.0) ...", flush=True)
    pipe = StableDiffusionXLImg2ImgPipeline.from_single_file(
        MODEL, torch_dtype=torch.float16)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(
        pipe.scheduler.config, use_karras_sigmas=True)

    print("[2/3] 加载 IP-Adapter ...", flush=True)
    pipe.load_ip_adapter(IPA, subfolder="sdxl_models",
                         weight_name="ip-adapter-plus_sdxl_vit-h.safetensors")
    pipe.set_ip_adapter_scale(0.8)
    pipe.to("cuda")

    print("[3/3] 读基准图 ...", flush=True)
    ref = load_image(REF).convert("RGB").resize((SIZE, SIZE))

    for si, state in enumerate(states):
        mode, prompt = STATES[state]
        outdir = os.path.join(OUTDIR, state)
        os.makedirs(outdir, exist_ok=True)
        t0 = time.time()

        # 帧 0：基准帧
        if state == "idle":
            frame0 = ref.copy()  # idle 帧 0 直接用基准图，不重画
        else:
            frame0 = gen(pipe, prompt, ref, ref, FRAME0_STR[mode], BASE_SEED + si * 8)
        frame0.save(os.path.join(outdir, f"{state}_00.png"))

        # 帧 1-7：从帧 0 微调
        for fi in range(1, 8):
            frame = gen(pipe, prompt, frame0, ref, FRAME_STR, BASE_SEED + si * 8 + fi)
            frame.save(os.path.join(outdir, f"{state}_{fi:02d}.png"))

        print(f"[{state}] 8 帧完成，耗时 {time.time()-t0:.1f}s -> {outdir}", flush=True)


if __name__ == "__main__":
    main()
