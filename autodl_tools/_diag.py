"""诊断 VAE config 与权重的 key 格式差异"""
import json

from safetensors import safe_open

vae_cfg = json.load(open('/root/autodl-tmp/wan_pipeline/vae/config.json'))
print('VAE config _diffusers_version:', vae_cfg.get('_diffusers_version'))
print('VAE config _class_name:', vae_cfg.get('_class_name'))
print('关键字段:', {k: v for k, v in vae_cfg.items() if k in ('in_channels', 'out_channels', 'latent_channels', 'block_out_channels', 'layers_per_block', 'norm_num_groups', 'scaling_factor', 'scaling_factor_latents', 'shift_factor', 'use_tiling')})

with safe_open('/root/autodl-tmp/wan_pipeline/vae/diffusion_pytorch_model.safetensors', framework='pt') as f:
    ks = list(f.keys())
    print('\nVAE 权重 key 数:', len(ks))
    print('开头 6 个:', ks[:6])
    downsamples = [k for k in ks if 'downsamples' in k]
    print('downsamples 样例:', downsamples[:3] if downsamples else '无')
    down_blocks = [k for k in ks if 'down_blocks' in k]
    print('down_blocks 样例:', down_blocks[:3] if down_blocks else '无')

te_cfg = json.load(open('/root/autodl-tmp/wan_pipeline/text_encoder/config.json'))
print('\ntext_encoder config 字段数:', len(te_cfg), 'model_type:', te_cfg.get('model_type'), 'hidden_size:', te_cfg.get('d_model'), te_cfg.get('hidden_size'))
print('_name_or_path:', te_cfg.get('_name_or_path'))
