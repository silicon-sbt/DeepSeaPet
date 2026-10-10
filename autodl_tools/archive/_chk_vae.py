"""校验 VAE safetensors 完整性：遍历读取所有 tensor（触发空洞校验）"""
import os

from safetensors import safe_open

p = '/root/autodl-tmp/wan_pipeline/vae/diffusion_pytorch_model.safetensors'
print('file size:', os.path.getsize(p), flush=True)
n = 0
with safe_open(p, framework='pt') as f:
    for k in f.keys():
        t = f.get_tensor(k)
        n += 1
        t.item() if t.numel() == 1 else t.flatten()[0].item()
print('tensors read OK:', n, flush=True)
