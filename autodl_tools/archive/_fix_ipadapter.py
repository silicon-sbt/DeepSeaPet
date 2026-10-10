"""修复被 curl -C 续传污染的 IP-Adapter image_encoder 文件。

污染机制：目标文件残留 15 字节 "Entry not found"（首次用错 URL 下错），
curl -C 从 offset 15 续传 → 前 15 字节错位、丢失真正文件头。
- config.json：内容已知，直接重写
- model.safetensors（2.36G）：删旧文件，学术加速 + curl 完整重下（不用 -C）
"""
import os, json, subprocess

D = "/root/autodl-tmp/ip_adapter/sdxl_models/image_encoder"
MODEL_SIZE = 2528373448

# 1. 重写 config.json（标准 OpenCLIP ViT-H/14 image_encoder 配置）
cfg = {
    "_name_or_path": "./image_encoder",
    "architectures": ["CLIPVisionModelWithProjection"],
    "attention_dropout": 0.0,
    "dropout": 0.0,
    "hidden_act": "gelu",
    "hidden_size": 1280,
    "image_size": 224,
    "initializer_factor": 1.0,
    "initializer_range": 0.02,
    "intermediate_size": 5120,
    "layer_norm_eps": 1e-05,
    "model_type": "clip_vision_model",
    "num_attention_heads": 16,
    "num_channels": 3,
    "num_hidden_layers": 32,
    "patch_size": 14,
    "projection_dim": 1024,
    "torch_dtype": "float16",
    "transformers_version": "4.28.0.dev0",
}
with open(os.path.join(D, "config.json"), "w") as f:
    json.dump(cfg, f, indent=2)
print("[1/2] config.json 已重写", flush=True)

# 2. 重新下载 model.safetensors（删旧 + 完整下载，不用 -C）
out = os.path.join(D, "model.safetensors")
if os.path.exists(out):
    os.remove(out)
url = "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors"
cmd = f"source /etc/network_turbo && curl -sSL --retry 5 -o '{out}' '{url}'"
print("[2/2] 重新下载 model.safetensors (2.36G) ...", flush=True)
r = subprocess.run(["bash", "-c", cmd])
size = os.path.getsize(out) if os.path.exists(out) else 0
assert r.returncode == 0 and size == MODEL_SIZE, f"下载失败 returncode={r.returncode} size={size}"
print(f"下载完成，大小 {size} 正确", flush=True)

# 3. 文件头验证（safetensors 前 8 字节 = 小端 u64 header 长度）
with open(out, "rb") as f:
    head = f.read(8)
hlen = int.from_bytes(head, "little")
assert 0 < hlen < 10_000_000, f"model.safetensors 文件头仍异常: {head.hex()}"
print(f"验证通过：safetensors header 长度 {hlen}（正常应为数千）", flush=True)
print("修复完成，可重跑 generate_sdxl.py", flush=True)
