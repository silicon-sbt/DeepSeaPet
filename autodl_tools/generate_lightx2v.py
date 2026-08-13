"""LightX2V fp8 蒸馏 Wan2.1 I2V 生成精灵图 — 1基准图 → 视频 → 提取8帧
依赖: lightx2v (pip install -e --no-deps) + opencv-python
算子: fp8-torchao (torch._scaled_mm) + torch_sdpa 注意力 —— RTX 5090 sm_120 可用，零外部依赖
模型: ModelScope lightx2v/Wan2.1-I2V-14B-480P-StepDistill-CfgDistill-Lightx2v 的 distill_fp8/ 分片
"""
import os, sys, glob, json
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "/root/autodl-tmp/lightx2v")  # 源码包目录：CWD=/root/autodl-tmp 时同名目录会抢占 namespace，须显式优先

# ===== 路径 =====
MS_CACHE = "/root/autodl-tmp/ms_cache"
MODEL_PATH = MS_CACHE                              # find_torch_model_path 从 {model_path}/distill_fp8/ 找 T5/CLIP/VAE
DISTILL_DIR = os.path.join(MS_CACHE, "distill_fp8")  # transformer 分片目录（block_* + non_block + config）
T5_CKPT = os.path.join(DISTILL_DIR, "models_t5_umt5-xxl-enc-fp8.pth")
CLIP_CKPT = os.path.join(DISTILL_DIR, "clip-fp8.pth")  # 与默认名不符，显式指定

BASE_DIR = "/root/autodl-tmp/sprites_output"     # 基准图 {state}/{state}_00.png
OUTPUT_DIR = "/root/autodl-tmp/sprites_video"    # 输出 {state}/{state}_{i:02d}.png
EXTRACT_FRAMES = 8

# ===== 动作描述（英文，Wan2.1 对英文效果更好）=====
MOTION_PROMPTS = {
    "idle": (
        "The cute chibi anime girl stands still, breathing gently. "
        "Her chest rises and falls very subtly. Her long blue hair sways slightly. "
        "Her whale tail accessory behind her gently sways left and right. "
        "She has a relaxed gentle smile, blinking occasionally. "
        "Static camera, subtle breathing idle animation, seamless loop."
    ),
    "hide": (
        "The cute chibi anime girl sneakily moves toward the right edge of frame. "
        "She crouches down lower and lower, body shrinking, until only her head peeks from the right edge. "
        "Then she completely disappears off screen to the right. "
        "Her blue hair trails behind. Playful mischievous sneaking motion."
    ),
    "peek": (
        "The cute chibi anime girl peeks out from the left edge of frame. "
        "First only her eyes and hair are visible, then her whole head emerges, "
        "then shoulders, then she slowly stands up fully in the center of frame. "
        "Her expression changes from curious to confident tsundere look. "
        "Her whale tail uncurls from a spiral as she emerges."
    ),
    "walk": (
        "The cute chibi anime girl walks sideways from left to right in a smooth cycle. "
        "Her arms and legs move naturally in walking motion. Her blue hair bounces gently. "
        "Her maid dress sways with each step. Her whale tail accessory streams behind her. "
        "Side view, seamless walking loop, gentle bouncing gait."
    ),
    "sleep": (
        "The cute chibi anime girl sleeps curled up, hugging her knees. "
        "Her body rises and falls very gently with breathing. "
        "A small sleep bubble appears and pops near her mouth. "
        "Her tail tip twitches occasionally. Peaceful sleeping, almost completely still. "
        "Soft cozy atmosphere, seamless sleeping loop."
    ),
    "happy": (
        "The cute chibi anime girl jumps up and down excitedly in place. "
        "She bounces from tiptoes to a small jump and back. "
        "Her arms wave up and down, her blue hair bounces wildly. "
        "Her tail wags rapidly behind her like an excited dog. "
        "Big happy grin, sparkling eyes, joyful bouncing loop."
    ),
    "lying": (
        "The cute chibi anime girl lies on her stomach, horizontal across the frame. "
        "Her chin rests on crossed arms. Her legs are bent up behind her. "
        "Her tail sways lazily from side to side. She blinks sleepily, "
        "occasionally kicking her feet gently. Relaxed cozy prone pose, subtle lazy movements."
    ),
}

# ===== 加载模型 =====
import torch
print(f"CUDA: {torch.cuda.is_available()}", flush=True)
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}", flush=True)
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory/1024**3:.1f} GB", flush=True)

print(f"\n加载 LightX2V fp8 蒸馏模型...", flush=True)
print(f"  model_path : {MODEL_PATH}", flush=True)
print(f"  distill_fp8: {DISTILL_DIR}", flush=True)
print(f"  首次加载含 fp8 反量化，约 5-15 分钟", flush=True)

from lightx2v import LightX2VPipeline

pipe = LightX2VPipeline(model_path=MODEL_PATH, model_cls="wan2.1_distill", task="i2v")

pipe.enable_quantize(
    dit_quantized=True,
    text_encoder_quantized=True,
    image_encoder_quantized=True,
    dit_quantized_ckpt=DISTILL_DIR,
    text_encoder_quantized_ckpt=T5_CKPT,
    image_encoder_quantized_ckpt=CLIP_CKPT,
    quant_scheme="fp8-torchao",
)
pipe.enable_offload(
    cpu_offload=True,
    offload_granularity="block",
    text_encoder_offload=True,
    image_encoder_offload=False,
    vae_offload=False,
)

# 用 config_json 初始化（官方推荐方式）：create_generator 传参走 set_args2config，
# 会把 target_video_length 等 InputInfo key 排除掉；json 则由 auto_calc_config 直接
# update 进 config，是蒸馏 i2v 的正规路径。
# attn 用 torch_sdpa（纯 F.scaled_dot_product_attention，RTX 5090 sm_120 零依赖可用）。
# guidance_scale=1（CFG-free，蒸馏模型不需要 CFG，官方 distill 示例同款）。
CFG_JSON = "/root/autodl-tmp/lightx2v_i2v_cfg.json"
with open(CFG_JSON, "w", encoding="utf-8") as f:
    json.dump({
        "infer_steps": 4,
        "target_video_length": 81,
        "text_len": 512,
        "target_height": 480,
        "target_width": 832,
        "self_attn_1_type": "torch_sdpa",
        "cross_attn_1_type": "torch_sdpa",
        "cross_attn_2_type": "torch_sdpa",
        "sample_guide_scale": 1,
        "sample_shift": 5.0,
        "rope_type": "torch_complex_rope",  # 纯 torch 实现；不指定会 fallback 到 flashinfer_rope（需 flashinfer 包）
        "enable_cfg": False,
        "denoising_step_list": [1000, 750, 500, 250],
    }, f, indent=2)
pipe.config_json = CFG_JSON  # 必须设属性：auto_calc_config 靠 config["config_json"] 加载 json 补 target_video_length 等 InputInfo key
pipe.create_generator(config_json=CFG_JSON)
print("attn=torch_sdpa / fp8-torchao 生成器初始化成功", flush=True)

print("模型就绪!\n", flush=True)

# ===== 逐状态生成 =====
import cv2
from PIL import Image

print(f"{'='*60}", flush=True)
print(f"LightX2V 精灵图生成 — {len(MOTION_PROMPTS)} 状态", flush=True)
print(f"{'='*60}\n", flush=True)

for state_name, motion_prompt in MOTION_PROMPTS.items():
    base_frame_path = os.path.join(BASE_DIR, state_name, f"{state_name}_00.png")
    if not os.path.exists(base_frame_path):
        print(f"[{state_name}] 基准图不存在: {base_frame_path}，跳过", flush=True)
        continue

    state_dir = os.path.join(OUTPUT_DIR, state_name)
    os.makedirs(state_dir, exist_ok=True)

    # 幂等：已有 8 帧则跳过
    existing = glob.glob(os.path.join(state_dir, f"{state_name}_*.png"))
    if len(existing) >= EXTRACT_FRAMES:
        print(f"[{state_name}] 已完成 ({len(existing)} 帧)，跳过", flush=True)
        continue

    print(f"\n[{state_name}]", flush=True)
    print(f"  动作: {motion_prompt[:80]}...", flush=True)

    mp4_path = os.path.join(state_dir, f"{state_name}.mp4")
    try:
        pipe.generate(
            seed=42789631,
            image_path=base_frame_path,
            prompt=motion_prompt,
            negative_prompt="",
            save_result_path=mp4_path,
        )
    except Exception as e:
        print(f"  [{state_name}] 生成失败: {type(e).__name__}: {str(e)[:200]}", flush=True)
        torch.cuda.empty_cache()
        continue

    if not os.path.exists(mp4_path):
        print(f"  [{state_name}] 输出 mp4 未生成，跳过", flush=True)
        continue
    print(f"  视频生成完成: {mp4_path}", flush=True)

    # 从 mp4 提取均匀分布的 8 帧
    cap = cv2.VideoCapture(mp4_path)
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    print(f"  共 {len(frames)} 帧", flush=True)

    indices = np.linspace(0, len(frames) - 1, EXTRACT_FRAMES, dtype=int)
    for i, idx in enumerate(indices):
        frame = cv2.cvtColor(frames[idx], cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame).resize((768, 768), Image.LANCZOS)
        img.save(os.path.join(state_dir, f"{state_name}_{i:02d}.png"))
    print(f"  提取 {EXTRACT_FRAMES} 帧完成", flush=True)

    torch.cuda.empty_cache()

print(f"\n{'='*60}", flush=True)
print(f"全部完成! 输出: {OUTPUT_DIR}", flush=True)
total = sum(1 for _ in os.walk(OUTPUT_DIR) for f in _[2] if f.endswith('.png'))
print(f"文件总数: {total}", flush=True)
print(f"{'='*60}", flush=True)
