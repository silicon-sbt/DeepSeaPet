"""测试 AutoencoderKLWan.from_single_file 从原版权重加载"""
import torch

from diffusers import AutoencoderKLWan

try:
    vae = AutoencoderKLWan.from_single_file(
        '/root/autodl-tmp/ms_cache/distill_fp8/Wan2.1_VAE.pth', torch_dtype=torch.float16
    )
    print('VAE_SINGLE_FILE_OK', flush=True)
    n_param = sum(p.numel() for p in vae.parameters())
    print('params:', n_param, flush=True)
except Exception as e:
    print('FAIL:', str(e)[:400], flush=True)
