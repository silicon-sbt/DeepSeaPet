"""组装 diffusers WanPipeline 目录（LightX2V distill_fp8 + 官方小件）并测试加载"""
import os, sys, glob, json, shutil
import torch
from safetensors.torch import save_file

sys.stdout.reconfigure(encoding='utf-8')

MS = '/root/autodl-tmp/ms_cache'
OUT = '/root/autodl-tmp/wan_pipeline'

def find(pat):
    hits = sorted(glob.glob(pat, recursive=True))
    return hits[0] if hits else None

def convert_pth(pth, cfg_src, out_dir, out_name):
    """pth → safetensors；legacy tar 需 weights_only=False（ModelScope 可信源）"""
    os.makedirs(out_dir, exist_ok=True)
    shutil.copy(cfg_src, f'{out_dir}/config.json')
    print(f'加载 {pth}...')
    sd = torch.load(pth, map_location='cpu', weights_only=False)
    if isinstance(sd, dict) and 'state_dict' in sd:
        sd = sd['state_dict']
    save_file(sd, f'{out_dir}/{out_name}')
    print(f'{out_dir}: {out_name} 写出 ✓')

# ===== 定位下载内容 =====
lx = find(f'{MS}/**/distill_fp8')
assert lx, 'distill_fp8 未找到'
print(f'distill_fp8: {lx}')

img_enc_file = find(f'{MS}/**/image_encoder/model.safetensors')
img_enc_cfg  = find(f'{MS}/**/image_encoder/config.json')
vae_cfg      = find(f'{MS}/**/vae/config.json')
sch_cfg      = find(f'{MS}/**/scheduler/scheduler_config.json')
tok_dir      = find(f'{MS}/**/tokenizer')
te_cfg       = find(f'{MS}/**/text_encoder/config.json')
mi           = find(f'{MS}/**/model_index.json')
print(f'官方小件: img_enc={img_enc_file} vae_cfg={vae_cfg} sch={sch_cfg} tok={tok_dir} te_cfg={te_cfg} mi={mi}')

assert all([img_enc_file, img_enc_cfg, vae_cfg, sch_cfg, tok_dir, te_cfg, mi]), '官方小件不齐'

os.makedirs(OUT, exist_ok=True)

# ===== transformer（硬链接 distill_fp8 分片，同盘零拷贝省磁盘）=====
os.makedirs(f'{OUT}/transformer', exist_ok=True)
for f in os.listdir(lx):
    if f.endswith('.safetensors') or f in ('config.json', 'diffusion_pytorch_model.safetensors.index.json'):
        dst = f'{OUT}/transformer/{f}'
        if not os.path.exists(dst):
            os.link(os.path.join(lx, f), dst)
print('transformer: 硬链接完成')

# 检查 index.json 指向的文件都存在
idx_path = f'{OUT}/transformer/diffusion_pytorch_model.safetensors.index.json'
idx = json.load(open(idx_path))
need = set(idx.get('weight_map', {}).values())
have = set(os.listdir(f'{OUT}/transformer'))
missing = need - have
if missing:
    print(f'!! index 指向缺失文件: {missing}')
else:
    print(f'transformer: index 指向 {len(need)} 个分片，全部存在 ✓')

# ===== text_encoder / vae：pth → safetensors =====
convert_pth(os.path.join(lx, 'models_t5_umt5-xxl-enc-fp8.pth'), te_cfg, f'{OUT}/text_encoder', 'model.safetensors')
convert_pth(os.path.join(lx, 'Wan2.1_VAE.pth'), vae_cfg, f'{OUT}/vae', 'diffusion_pytorch_model.safetensors')

# ===== image_encoder / scheduler / tokenizer =====
os.makedirs(f'{OUT}/image_encoder', exist_ok=True)
shutil.copy(img_enc_file, f'{OUT}/image_encoder/model.safetensors')
shutil.copy(img_enc_cfg, f'{OUT}/image_encoder/config.json')
os.makedirs(f'{OUT}/scheduler', exist_ok=True)
shutil.copy(sch_cfg, f'{OUT}/scheduler/scheduler_config.json')
os.makedirs(f'{OUT}/tokenizer', exist_ok=True)
for f in os.listdir(tok_dir):
    shutil.copy(os.path.join(tok_dir, f), f'{OUT}/tokenizer/{f}')
print('image_encoder / scheduler / tokenizer: 复制完成')

# ===== model_index.json =====
shutil.copy(mi, f'{OUT}/model_index.json')
print('model_index.json: 复制完成')

print(f'\n组装完成: {OUT}')
