"""冒烟测试：LightX2V pipeline 初始化（fp8-torchao + torch_sdpa），不做实际生成。
验证 RTX 5090 上 fp8 权重能加载、torch_sdpa 生成器能创建，通过了再跑全量。
"""
import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "/root/autodl-tmp/lightx2v")  # 源码包目录：CWD=/root/autodl-tmp 时同名目录会抢占 namespace，须显式优先

MS_CACHE = "/root/autodl-tmp/ms_cache"
DISTILL_DIR = os.path.join(MS_CACHE, "distill_fp8")
T5_CKPT = os.path.join(DISTILL_DIR, "models_t5_umt5-xxl-enc-fp8.pth")
CLIP_CKPT = os.path.join(DISTILL_DIR, "clip-fp8.pth")

import torch
print(f"CUDA: {torch.cuda.is_available()}", flush=True)
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}", flush=True)

print("加载 LightX2VPipeline (fp8-torchao)...", flush=True)
from lightx2v import LightX2VPipeline

pipe = LightX2VPipeline(model_path=MS_CACHE, model_cls="wan2.1_distill", task="i2v")

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
print("SMOKE_OK: pipeline + fp8-torchao + torch_sdpa 初始化成功", flush=True)
