"""img2img 精灵图生成 — 每状态1张基准 + 7张img2img变体保证帧间连贯"""
import os, sys, torch, glob
from diffusers import StableDiffusionXLPipeline, EulerAncestralDiscreteScheduler
from PIL import Image

OUTPUT_DIR = "/root/autodl-tmp/sprites_output"
CACHE_DIR = "/root/autodl-tmp/models"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

print(f"CUDA: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory/1024**3:.1f} GB")

# ===== 加载模型 =====
existing_models = glob.glob(os.path.join(CACHE_DIR, "**", "*.safetensors"), recursive=True)
existing_diffusers = glob.glob(os.path.join(CACHE_DIR, "**", "model_index.json"), recursive=True)

if existing_models:
    safetensors_path = existing_models[0]
    print(f"\n找到本地模型: {safetensors_path}")
    pipe = StableDiffusionXLPipeline.from_single_file(
        safetensors_path, torch_dtype=torch.float16, use_safetensors=True,
    ).to("cuda")
elif existing_diffusers:
    model_dir = os.path.dirname(existing_diffusers[0])
    print(f"\n找到本地模型(Diffusers): {model_dir}")
    pipe = StableDiffusionXLPipeline.from_pretrained(
        model_dir, torch_dtype=torch.float16, use_safetensors=True,
    ).to("cuda")
else:
    print("\n未找到本地模型，从 ModelScope 下载 Animagine-XL...")
    from modelscope import snapshot_download
    model_dir = snapshot_download('ModelE/Animagine-XL', cache_dir=CACHE_DIR)
    files = os.listdir(model_dir)
    safetensors_file = [f for f in files if f.endswith('.safetensors')][0]
    pipe = StableDiffusionXLPipeline.from_single_file(
        os.path.join(model_dir, safetensors_file),
        torch_dtype=torch.float16, use_safetensors=True,
    ).to("cuda")

pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
pipe.enable_vae_slicing()

# ===== 参数 =====
CHARACTER = (
    "masterpiece, best quality, 1girl, chibi, cute, "
    "blue long hair with gradient, hair between eyes, blue hair ornament, "
    "maid headdress, maid dress, white apron, "
    "whale tail hairpin, whale tail accessory, "
    "large sparkling blue eyes, blush, "
    "solid light green background, full body"
)
NEGATIVE = (
    "lowres, bad anatomy, bad hands, text, error, missing fingers, "
    "extra digit, fewer digits, cropped, worst quality, low quality, "
    "normal quality, jpeg artifacts, signature, watermark, username, "
    "blurry, ugly, deformed, messy drawing, out of frame, multiple girls, "
    "realistic, 3d, white background, complex background, gradient background"
)

SEED = 42789631
STEPS = 30
CFG = 7.5
SIZE = 768
DENOISE = 0.32

# ===== 动画帧描述 =====
def make_prompt(state_prompt):
    return f"{CHARACTER}, {state_prompt}"

STATES = {}

# --- idle: 待机呼吸 ---
STATES["idle"] = [
    make_prompt("standing, hands clasped in front, tail gently curved behind, looking at viewer, relaxed expression, slight smile, calm breathing pose"),
    make_prompt("standing, hands clasped in front, tail tip slightly raised, chest slightly lifted, subtle inhale pose, looking at viewer, eyes slightly wider"),
    make_prompt("standing, body very slightly raised, hair floating slightly, tail swaying gently upward, chest expanded, eyes open wide, gentle expression"),
    make_prompt("standing, head tilted very slightly to right, body slightly lowering, exhale starting, tail relaxing, relaxed gentle expression"),
    make_prompt("standing, body settled down slightly, tail drooping relaxed, eyes half-closed, enjoying expression, shoulders lowered, calm breathing out"),
    make_prompt("standing, weight shifted slightly to left leg, tail swaying to right, body leaning very subtly left, playful slight smirk"),
    make_prompt("standing, weight shifted slightly to right leg, tail swaying to left, body leaning very subtly right, gentle smile returning"),
    make_prompt("standing, centered balanced posture, tail slowly returning center, hands clasped in front, gentle warm smile, relaxed breathing"),
]

# --- hide: 侧边隐藏 ---
STATES["hide"] = [
    make_prompt("standing, head turned to right looking sideways, mischievous sly expression, hands together in front, tail curled slightly, about to sneak away pose, full body"),
    make_prompt("leaning body to right side, left foot slightly lifted on tiptoe, arms slightly raised for balance, sneaking motion, tail curved to right, playful sneaky face"),
    make_prompt("knees bending, body lowering, hands lightly lifting skirt hem, tail curled into spiral, shy embarrassed blush, crouching slightly, preparing to hide"),
    make_prompt("half crouching, body 20 percent smaller in frame, tail tightly spiraled, nervous expression, looking back over shoulder, sneaking away"),
    make_prompt("deep crouching, only upper body and head visible, hands gripping imaginary edge, peeking expression, tail hidden behind body, playful hiding"),
    make_prompt("only head and eyes visible at bottom corner of frame, big curious eyes peeking, playful shy expression, hair draping down, character mostly offscreen"),
    make_prompt("only top of head and whale hairpin visible at frame edge, few strands of blue hair floating, barely visible, almost hidden"),
    make_prompt("just a single strand of blue hair at frame edge, character completely hidden, empty light green background dominating frame"),
]

# --- peek: 边缘探头 ---
STATES["peek"] = [
    make_prompt("only top of head and whale hairpin visible at frame edge, few strands of blue hair, character mostly hidden"),
    make_prompt("upper half of face visible above frame edge, eyes wide open round and curious, alert watching expression, blue hair draping down"),
    make_prompt("entire head visible, hair naturally falling, surprised curious expression, who is there look, just head peeking"),
    make_prompt("head and shoulders visible above edge, hands resting on imaginary surface, body leaning slightly forward, curious but cautious expression, tail tip appearing"),
    make_prompt("upper body visible above waist level, hands folded on imaginary surface, tsundere expression, hmpf look but curious, leaning forward more"),
    make_prompt("most of body visible but still crouching, tail slowly uncurling from spiral, playful expression, about to stand up pose, hands on knees"),
    make_prompt("almost fully standing, only feet still behind imaginary edge, tail extended behind, slight smile, recovering composure"),
    make_prompt("fully standing back in frame center, relaxed composed expression, hands clasped, tail gently swaying, back to normal idle-like pose"),
]

# --- walk: 侧面行走 ---
STATES["walk"] = [
    make_prompt("side view, walking pose, body slightly leaning forward, right leg forward left leg back, arms in walking swing, tail streaming behind, gentle walking smile, full body side profile"),
    make_prompt("side view, right leg stepping forward, left arm swinging forward, right arm swinging back, walking motion, tail swaying with movement, hair flowing slightly, full body side profile"),
    make_prompt("side view, weight on right leg, left leg starting to lift off ground, walking stride middle, arms at midpoint, body bobbing slightly up, tail bouncing, full body side profile"),
    make_prompt("side view, left leg swinging forward, right arm swinging forward, mid-stride walking, dynamic gentle motion, skirt slightly swaying, tail flowing behind, full body side profile"),
    make_prompt("side view, left leg landing forward taking weight, right leg starting to lift, arms crossing midpoint, walking cycle continuing, hair bouncing, full body side profile"),
    make_prompt("side view, right leg swinging forward, left arm forward, right arm back, steady walking pace, tail gently waving, relaxed walking face, full body side profile"),
    make_prompt("side view, right leg landing, weight shifting forward, left leg preparing to lift, arms at midpoint again, smooth walking rhythm, full body side profile"),
    make_prompt("side view, left leg forward right leg back, similar to frame 0 but opposite leg position for seamless loop, tail streaming behind, gentle walking expression, full body side profile"),
]

# --- sleep: 蜷缩睡觉 ---
STATES["sleep"] = [
    make_prompt("curled up sitting pose, knees hugged to chest, head resting on knees, eyes closed peacefully, tail wrapped around body like blanket, cozy sleeping"),
    make_prompt("curled up sitting, slight inhale raising back slightly, tail tip twitching gently, eyes closed, peaceful sleeping face, soft breathing"),
    make_prompt("curled up sitting, continuing gentle inhale, tail tip curling slightly, ears twitching, sleeping deeply, relaxed expression"),
    make_prompt("curled up sitting, inhale peak, body slightly expanded, whale hairpin glinting softly, peaceful maximum inhale, eyes gently closed, serene face"),
    make_prompt("curled up sitting, beginning exhale, body relaxing slightly, head tilting very slightly to one side, tail loosening, soft sleepy expression, breathing out"),
    make_prompt("curled up sitting, exhaling, head tilted slightly more, small cute sleep bubble near mouth, tail relaxed, deep peaceful sleep, soft breathing out"),
    make_prompt("curled up sitting, exhale at lowest, body fully relaxed, sleep bubble floating away, most relaxed state, angelic sleeping face, completely at peace"),
    make_prompt("curled up sitting, returning to neutral sleeping pose, bubble gone, tail wrapping back around body, eyes closed peacefully, loop back"),
]

# --- happy: 开心蹦跳 ---
STATES["happy"] = [
    make_prompt("standing on tiptoes, both hands clenched in fists at chest, sparkling eyes, big happy grin, tail raised high and curled, excited joyful pose, full body, energetic"),
    make_prompt("knees bending, body crouching down preparing to jump, tail lowering for power, arms pulling back, anticipating excited face, ready to spring"),
    make_prompt("jumping up, body rising, hair flying upward, arms spreading wide open, tail swinging to one side, mouth open in joyful laugh, mid-air rising"),
    make_prompt("at peak of jump, highest point, skirt fluttering, tail whipped to far side, hair spread out, mouth wide laughing, arms raised high, pure joy"),
    make_prompt("starting to descend from jump, body rotating slightly 10 degrees, hair still floating but settling, arms lowering slightly, tail starting to swing back, happy laughing face"),
    make_prompt("landing from jump, knees bent absorbing impact, body still slightly rotated, tail swinging fast, joyful bouncy landing, arms forward for balance"),
    make_prompt("bouncing back up halfway, body rotating back to front, tail rapidly wagging with motion blur effect, arms coming back to chest, excited happy face"),
    make_prompt("returning to tiptoe pose, body back to front-facing, tail slowing down from fast wagging, cheeks flushed, happy satisfied grin, fists at chest"),
]

# --- lying: 聊天趴姿 ---
STATES["lying"] = [
    make_prompt("lying on stomach, horizontal pose, body stretched across frame, resting chin on crossed arms, legs bent up behind with crossed ankles, tail lazily swaying to one side, looking at viewer with half-lidded eyes, relaxed slight smile, maid dress spread out around body"),
    make_prompt("lying on stomach horizontal, head tilted slightly right, one eye winking, tail swaying to right side, playful wink expression, legs still crossed behind"),
    make_prompt("lying on stomach horizontal, chin tucked slightly into arms, eyes fully open, tail swinging back to left, attentive watching expression, slight smile"),
    make_prompt("lying on stomach horizontal, arms stretched forward in small stretch, upper body reaching forward, hair sliding forward over shoulders, tail tip curled up, stretching cute expression"),
    make_prompt("lying on stomach horizontal, arms folded back under chin, body slightly more compact, looking toward side, tail relaxed drooping down, gentle interested expression"),
    make_prompt("lying on stomach horizontal, head resting fully on arms, eyes curved in happy closed smile, legs kicking up alternately, tail curled into small spiral, very happy content expression"),
    make_prompt("lying on stomach horizontal, head turned slightly to side, half face buried in arm, shy expression with blush, tail slowly uncurling, legs still"),
    make_prompt("lying on stomach horizontal, back to relaxed pose, head on crossed arms, gentle smile returning, tail lazily swaying, calm relaxed half-lidded eyes"),
]

# ===== 开始生成 =====
print(f"\n{'='*60}")
print(f"img2img 精灵图生成 — denoising={DENOISE}, seed={SEED}")
print(f"{'='*60}\n")

for state_name, frame_prompts in STATES.items():
    print(f"\n[{state_name}] ({len(frame_prompts)} frames)", flush=True)
    state_dir = os.path.join(OUTPUT_DIR, state_name)
    os.makedirs(state_dir, exist_ok=True)

    base_image = None

    for frame_idx, pose_prompt in enumerate(frame_prompts):
        fname = f"{state_name}_{frame_idx:02d}.png"
        fpath = os.path.join(state_dir, fname)

        if os.path.exists(fpath):
            print(f"  frame {frame_idx}: (skip)", flush=True)
            if frame_idx == 0:
                base_image = Image.open(fpath)
            continue

        frame_seed = SEED + frame_idx * 7

        if frame_idx == 0:
            # txt2img 生成基准帧
            print(f"  frame 0 (txt2img)...", flush=True)
            result = pipe(
                prompt=pose_prompt,
                negative_prompt=NEGATIVE,
                num_inference_steps=STEPS,
                guidance_scale=CFG,
                generator=torch.Generator("cuda").manual_seed(frame_seed),
                width=SIZE, height=SIZE,
            )
            base_image = result.images[0]
            base_image.save(fpath)
            print(f"    OK", flush=True)

        else:
            # img2img 基于帧0生成变体
            if base_image is None:
                base_image = Image.open(os.path.join(state_dir, f"{state_name}_00.png"))

            result = pipe(
                prompt=pose_prompt,
                negative_prompt=NEGATIVE,
                image=base_image,
                strength=DENOISE,
                num_inference_steps=STEPS,
                guidance_scale=CFG,
                generator=torch.Generator("cuda").manual_seed(frame_seed),
            )
            img = result.images[0]
            img.save(fpath)
            print(f"  frame {frame_idx}: OK", flush=True)

print(f"\n{'='*60}")
print(f"全部完成! 输出: {OUTPUT_DIR}")
total = sum(1 for _ in os.walk(OUTPUT_DIR) for f in _[2] if f.endswith('.png'))
print(f"文件总数: {total}")
print(f"{'='*60}")
