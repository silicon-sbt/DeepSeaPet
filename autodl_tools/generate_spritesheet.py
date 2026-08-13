"""精灵表模式 — 每状态 1 次 SDXL 调用产出 8 帧(2×4 网格)+ 绿幕背景"""
import os, sys, torch, glob
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
from diffusers import StableDiffusionXLPipeline, EulerAncestralDiscreteScheduler
from PIL import Image

OUTPUT_DIR = "/root/autodl-tmp/sprites_output"
CACHE_DIR = "/root/autodl-tmp/models"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"CUDA: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory/1024**3:.1f} GB")

# ===== 加载模型 =====
safetensors_path = glob.glob(os.path.join(CACHE_DIR, "**", "*.safetensors"), recursive=True)[0]
print(f"\n加载模型: {safetensors_path}")
pipe = StableDiffusionXLPipeline.from_single_file(
    safetensors_path, torch_dtype=torch.float16, use_safetensors=True,
).to("cuda")
pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
pipe.enable_vae_slicing()
print("模型就绪!")

# ===== 精灵表参数 =====
SEED = 42789631
STEPS = 35
CFG = 8
SIZE = 1024  # 1024×1024, 2行×4列, 每格 256×512 (够 chibi 站立)

# 固定角色描述（精灵表格式）
CHARACTER = (
    "exactly the same chibi anime girl in every frame, "
    "blue long gradient hair with bangs between eyes, blue whale tail hairpin, "
    "maid headdress, dark blue maid dress with white apron, gold bow at collar, "
    "large sparkling blue eyes, blush, cute small mouth, "
    "chibi proportions, big head small body, "
    "consistent identical character design across ALL 8 frames"
)

# ===== 各状态精灵表 prompt =====
SHEET_PROMPTS = {}

SHEET_PROMPTS["idle"] = """spritesheet, 8 frames in 2 rows 4 columns grid,
flat solid #00ff00 bright green background, no grid lines, no shadows on background,
exactly the same chibi anime girl in every frame, blue long gradient hair, blue whale tail hairpin, maid headdress, dark blue maid dress, white apron, gold bow, large blue eyes,
standing idle breathing animation cycle:
frame1: standing relaxed, hands clasped in front, neutral gentle smile, tail curved behind
frame2: slight inhale, chest slightly raised, eyes slightly wider, tail tip raised
frame3: full inhale, hair floating slightly, tail swaying upward, slight smile
frame4: beginning exhale, body slightly lowering, tail relaxing, eyes half-closed
frame5: mid exhale, settled relaxed posture, tail drooped relaxed, calm expression
frame6: weight shift slightly left, tail sway right, playful slight smirk
frame7: weight shift slightly right, tail sway left, gentle smile returning
frame8: centered balanced, tail slowly returning center, relaxed gentle warm smile, loop ready
game animation spritesheet, pixel art reference, consistent art style"""

SHEET_PROMPTS["hide"] = """spritesheet, 8 frames in 2 rows 4 columns grid,
flat solid #00ff00 bright green background, no grid lines, no shadows on background,
exactly the same chibi anime girl in every frame, blue long gradient hair, blue whale tail hairpin, maid headdress, dark blue maid dress, white apron, gold bow, large blue eyes,
hiding sneaking away animation cycle, character moves toward right and disappears:
frame1: standing center, looking right with mischievous sly expression, about to sneak
frame2: leaning body to right, tiptoe stance, arms slightly raised for balance, sneaking
frame3: knees bending, body lowering, hands lifting skirt hem, tail curled into spiral
frame4: half crouching, body smaller in frame, tail tightly spiraled, nervous looking back
frame5: deep crouching, only upper body visible, peeking expression, tail hidden
frame6: only head and eyes barely visible at frame bottom, big curious peeking eyes
frame7: only top of head and whale hairpin visible, few strands of blue hair
frame8: frame almost empty, just hint of blue hair at edge, character hidden
game animation spritesheet, consistent art style, same character throughout"""

SHEET_PROMPTS["peek"] = """spritesheet, 8 frames in 2 rows 4 columns grid,
flat solid #00ff00 bright green background, no grid lines, no shadows on background,
exactly the same chibi anime girl in every frame, blue long gradient hair, blue whale tail hairpin, maid headdress, dark blue maid dress, white apron, gold bow, large blue eyes,
peeking out emerging from edge animation cycle:
frame1: only top of head and whale hairpin at frame edge, mostly hidden, curious
frame2: upper half of face visible, eyes wide open curious, alert watching
frame3: entire head visible, hair falling naturally, surprised curious expression
frame4: head and shoulders visible, hands resting on imaginary surface, leaning forward
frame5: upper body to waist visible, hands folded, tsundere hmpf expression but curious
frame6: most of body visible crouching, tail slowly uncurling, playful, about to stand
frame7: almost fully standing, only feet hidden, tail extended, slight confident smile
frame8: fully standing in frame center, composed confident pose, hands clasped, tail swaying
game animation spritesheet, consistent art style, same character throughout"""

SHEET_PROMPTS["walk"] = """spritesheet, 8 frames in 2 rows 4 columns grid,
flat solid #00ff00 bright green background, no grid lines, no shadows on background,
exactly the same chibi anime girl in every frame, blue long gradient hair, blue whale tail hairpin, maid headdress, dark blue maid dress, white apron, gold bow, large blue eyes,
side view walking animation cycle from right to left, seamless walking loop:
frame1: side view, right leg forward left leg back, arms in walking swing, tail streaming behind
frame2: right leg stepping forward, left arm forward right arm back, walking motion
frame3: weight on right leg, left leg lifting off ground, mid-stride, body bobbing slightly up
frame4: left leg swinging forward, right arm swinging forward, dynamic walking mid-stride
frame5: left leg landing taking weight, right leg starting to lift, arms crossing midpoint
frame6: right leg swinging forward, left arm forward, steady walking pace, tail gently waving
frame7: right leg landing, weight shifting forward, left leg preparing to lift, smooth rhythm
frame8: left leg forward right leg back, mirror of frame1 opposite legs, seamless loop ready
game animation spritesheet, consistent art style, same character throughout"""

SHEET_PROMPTS["sleep"] = """spritesheet, 8 frames in 2 rows 4 columns grid,
flat solid #00ff00 bright green background, no grid lines, no shadows on background,
exactly the same chibi anime girl in every frame, blue long gradient hair, blue whale tail hairpin, maid headdress, dark blue maid dress, white apron, gold bow, large blue eyes,
curled up sleeping breathing animation cycle, peaceful cozy:
frame1: curled up sitting, knees hugged to chest, head resting on knees, eyes closed, tail wrapped like blanket
frame2: slight inhale, back raising slightly, tail tip twitching, eyes closed peacefully
frame3: continuing inhale, tail tip curling, peaceful sleeping face, deeply asleep
frame4: inhale peak, body slightly expanded, whale hairpin glinting softly, serene peaceful face
frame5: beginning exhale, body relaxing, head tilting slightly, tail loosening, soft sleepy
frame6: exhaling, head tilted more, small cute sleep bubble near mouth, tail relaxed, deep sleep
frame7: exhale lowest, body fully relaxed, sleep bubble floating away, most relaxed angelic face
frame8: returning to neutral sleeping pose, bubble gone, tail wrapping back, peaceful loop ready
game animation spritesheet, consistent art style, same character throughout"""

SHEET_PROMPTS["happy"] = """spritesheet, 8 frames in 2 rows 4 columns grid,
flat solid #00ff00 bright green background, no grid lines, no shadows on background,
exactly the same chibi anime girl in every frame, blue long gradient hair, blue whale tail hairpin, maid headdress, dark blue maid dress, white apron, gold bow, large blue eyes,
happy jumping bouncing celebration animation cycle:
frame1: standing on tiptoes, both hands fists at chest, sparkling eyes, big happy grin, tail raised high curled
frame2: knees bending, body crouching preparing to jump, tail lowering for power, arms pulling back, excited
frame3: jumping up, body rising, hair flying upward, arms spreading wide, tail swinging, mouth open joyful laugh
frame4: peak of jump, highest point, skirt fluttering, tail whipped to side, hair spread out, arms raised high, pure joy
frame5: starting to descend, body rotating slightly, hair settling, arms lowering, tail swinging back, happy laughing
frame6: landing from jump, knees bent absorbing impact, body slightly rotated, tail swinging fast, joyful bouncy landing
frame7: bouncing back up halfway, body rotating back to front, tail rapidly wagging, arms coming back to chest, excited
frame8: returning to tiptoe pose, body back front-facing, tail slowing, cheeks flushed, happy satisfied grin, loop ready
game animation spritesheet, consistent art style, same character throughout"""

SHEET_PROMPTS["lying"] = """spritesheet, 8 frames in 2 rows 4 columns grid,
flat solid #00ff00 bright green background, no grid lines, no shadows on background,
exactly the same chibi anime girl in every frame, blue long gradient hair, blue whale tail hairpin, maid headdress, dark blue maid dress, white apron, gold bow, large blue eyes,
lying on stomach horizontal prone pose lazy animation cycle:
frame1: lying on stomach horizontal, chin on crossed arms, legs bent up with crossed ankles, tail lazily swaying to one side, half-lidded relaxed eyes
frame2: head tilted slightly right, one eye winking, tail swaying to right, playful wink
frame3: chin tucked slightly into arms, eyes fully open, tail swinging back left, attentive watching
frame4: arms stretched forward in small stretch, upper body reaching, legs still crossed, tail tip curled, cute stretching
frame5: arms folded back under chin, body slightly more compact, looking toward side, tail relaxed drooping
frame6: head resting fully on arms, eyes curved in happy closed smile, legs kicking up alternately, tail curled into spiral
frame7: head turned slightly to side, half face buried in arm, shy expression with blush, tail slowly uncurling, legs still
frame8: back to relaxed pose, head on crossed arms, gentle smile returning, tail lazily swaying, calm half-lidded eyes, loop ready
game animation spritesheet, consistent art style, same character throughout"""

# ===== 生成 =====
# ===== 切帧工具 =====
def slice_sheet(sheet_path, state_dir, state_name, size):
    """把 1024×1024, 2行×4列 的精灵表切成 8 帧"""
    sheet = Image.open(sheet_path)
    cell_w = size // 4  # 256
    cell_h = size // 2  # 512
    frame_idx = 0
    for row in range(2):
        for col in range(4):
            left = col * cell_w
            top = row * cell_h
            right = left + cell_w
            bottom = top + cell_h
            frame = sheet.crop((left, top, right, bottom))
            frame = frame.resize((768, 768), Image.LANCZOS)
            fpath = os.path.join(state_dir, f"{state_name}_{frame_idx:02d}.png")
            frame.save(fpath)
            frame_idx += 1
    sheet.close()
    print(f"  切帧完成: {frame_idx} 帧 → {state_dir}", flush=True)


NEGATIVE = (
    "different characters, different faces, different hair colors, different outfits, "
    "inconsistent design, varying proportions, character design changes, "
    "white background, blue background, gradient background, complex background, "
    "grid lines, borders between frames, shadows on ground, motion blur, "
    "bad anatomy, bad hands, missing fingers, extra fingers, deformed, ugly, "
    "blurry, low quality, jpeg artifacts, watermark, text, signature, "
    "realistic, 3d, multiple girls, different girls"
)

print(f"\n{'='*60}")
print(f"精灵表模式 — {len(SHEET_PROMPTS)} 状态 × 1 次调用/状态")
print(f"分辨率: {SIZE}×{SIZE}, 2行×4列 = 8帧/状态")
print(f"seed={SEED}, steps={STEPS}, cfg={CFG}")
print(f"{'='*60}\n")

for state_name, prompt in SHEET_PROMPTS.items():
    state_dir = os.path.join(OUTPUT_DIR, state_name)
    os.makedirs(state_dir, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{state_name}_sheet.png")

    # 检查是否已生成
    if os.path.exists(out_path):
        print(f"[{state_name}] 已存在，跳过", flush=True)
        slice_sheet(out_path, state_dir, state_name, SIZE)
        continue

    print(f"\n[{state_name}] 生成精灵表...", flush=True)
    print(f"  prompt 前80字: {prompt[:80]}...", flush=True)

    try:
        result = pipe(
            prompt=prompt,
            negative_prompt=NEGATIVE,
            num_inference_steps=STEPS,
            guidance_scale=CFG,
            generator=torch.Generator("cuda").manual_seed(SEED),
            width=SIZE, height=SIZE,
        )
        sheet = result.images[0]
        sheet.save(out_path)
        print(f"  精灵表保存: {out_path}", flush=True)

        slice_sheet(out_path, state_dir, state_name, SIZE)

    except torch.cuda.OutOfMemoryError:
        print(f"  OOM! 清理显存重试...", flush=True)
        torch.cuda.empty_cache()
        try:
            result = pipe(
                prompt=prompt,
                negative_prompt=NEGATIVE,
                num_inference_steps=25,
                guidance_scale=CFG,
                generator=torch.Generator("cuda").manual_seed(SEED),
                width=SIZE, height=SIZE,
            )
            sheet = result.images[0]
            sheet.save(out_path)
            print(f"  精灵表保存(降steps): {out_path}", flush=True)
            _slice_sheet(out_path, state_dir, state_name, SIZE)
        except Exception as e2:
            print(f"  重试也失败: {e2}", flush=True)

    except Exception as e:
        print(f"  生成失败: {e}", flush=True)

    torch.cuda.empty_cache()


print(f"\n{'='*60}")
print(f"全部完成! 输出: {OUTPUT_DIR}")
for state_name in SHEET_PROMPTS:
    state_dir = os.path.join(OUTPUT_DIR, state_name)
    count = len(glob.glob(os.path.join(state_dir, f"{state_name}_*.png")))
    print(f"  {state_name}: {count} 帧")
print(f"{'='*60}")
