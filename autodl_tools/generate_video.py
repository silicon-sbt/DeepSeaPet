"""Wan2.1 I2V 视频生成精灵图 — 1张基准图 → AI视频 → 提取8帧"""
import os, sys, torch, glob
from PIL import Image
import numpy as np

OUTPUT_DIR = "/root/autodl-tmp/sprites_video"
BASE_DIR = "/root/autodl-tmp/sprites_output"  # SDXL 已生成的基准图
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"CUDA: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory/1024**3:.1f} GB")

# ===== 加载 Wan2.1 I2V =====
from diffusers import WanPipeline
from diffusers.utils import export_to_video

MODEL_ID = "Wan-AI/Wan2.1-I2V-14B-480P-Diffusers"

print(f"\n加载 Wan2.1 I2V 模型: {MODEL_ID}")
print("下载+加载约需 5-10 分钟...")

pipe = WanPipeline.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
).to("cuda")

# 使用 CPU offload 节省显存（14B 模型 fp16≈28GB，加激活值可能超 32GB）
try:
    pipe.enable_model_cpu_offload()
    print("已启用 CPU offload")
except Exception as e:
    print(f"CPU offload 失败: {e}，尝试直接加载...")

print("模型就绪!")

# ===== 每个状态的动作描述（英文，Wan2.1 对英文效果更好）=====
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

# ===== 逐状态生成 =====
NUM_FRAMES_TO_GENERATE = 25  # Wan2.1 生成帧数
EXTRACT_FRAMES = 8            # 提取 8 帧

print(f"\n{'='*60}")
print(f"Wan2.1 I2V 精灵图生成 — {len(MOTION_PROMPTS)} 状态")
print(f"每状态生成 {NUM_FRAMES_TO_GENERATE} 帧视频 → 提取 {EXTRACT_FRAMES} 帧")
print(f"{'='*60}\n")

for state_name, motion_prompt in MOTION_PROMPTS.items():
    base_frame_path = os.path.join(BASE_DIR, state_name, f"{state_name}_00.png")
    if not os.path.exists(base_frame_path):
        print(f"[{state_name}] 基准图不存在: {base_frame_path}，跳过", flush=True)
        continue

    state_dir = os.path.join(OUTPUT_DIR, state_name)
    os.makedirs(state_dir, exist_ok=True)

    # 检查是否已有输出
    existing = glob.glob(os.path.join(state_dir, f"{state_name}_*.png"))
    if len(existing) >= EXTRACT_FRAMES:
        print(f"[{state_name}] 已完成 ({len(existing)} 帧)，跳过", flush=True)
        continue

    print(f"\n[{state_name}]", flush=True)
    print(f"  动作: {motion_prompt[:80]}...", flush=True)

    # 加载基准图并调整为 480P
    base_img = Image.open(base_frame_path).convert("RGB")
    base_img = base_img.resize((832, 480), Image.LANCZOS)  # Wan2.1 480P 标准尺寸

    print(f"  生成视频中 (seed=42789631)...", flush=True)

    try:
        output = pipe(
            image=base_img,
            prompt=motion_prompt,
            height=480,
            width=832,
            num_frames=NUM_FRAMES_TO_GENERATE,
            num_inference_steps=30,
            generator=torch.Generator("cuda").manual_seed(42789631),
        )
    except torch.cuda.OutOfMemoryError:
        print("  OOM! 降低参数重试...", flush=True)
        torch.cuda.empty_cache()
        output = pipe(
            image=base_img,
            prompt=motion_prompt,
            height=480,
            width=832,
            num_frames=NUM_FRAMES_TO_GENERATE,
            num_inference_steps=20,
            generator=torch.Generator("cuda").manual_seed(42789631),
        )

    video_frames = output.frames[0]  # list of PIL Images
    print(f"  视频生成完成: {len(video_frames)} 帧", flush=True)

    # 提取均匀分布的 8 帧
    indices = np.linspace(0, len(video_frames) - 1, EXTRACT_FRAMES, dtype=int)
    for i, idx in enumerate(indices):
        frame = video_frames[idx]
        # 调整回 768×768（居中裁剪或缩放）
        frame = frame.resize((768, 768), Image.LANCZOS)
        fpath = os.path.join(state_dir, f"{state_name}_{i:02d}.png")
        frame.save(fpath)

    print(f"  提取 {EXTRACT_FRAMES} 帧完成", flush=True)
    base_img.close()

    # 清理显存
    torch.cuda.empty_cache()

print(f"\n{'='*60}")
print(f"全部完成! 输出: {OUTPUT_DIR}")
total = sum(1 for _ in os.walk(OUTPUT_DIR) for f in _[2] if f.endswith('.png'))
print(f"文件总数: {total}")
print(f"{'='*60}")
