"""验证 wan_pipeline 加载——与 generate_video.py 完全同款：fp8 优先，TypeError 回退 float16"""
import torch

from diffusers import WanPipeline

print(f'CUDA: {torch.cuda.is_available()}', flush=True)
try:
    pipe = WanPipeline.from_pretrained('/root/autodl-tmp/wan_pipeline', torch_dtype=torch.float8_e4m3fn)
except TypeError:
    print('fp8 不可用（text_encoder 不支持 float8），回退 float16', flush=True)
    pipe = WanPipeline.from_pretrained('/root/autodl-tmp/wan_pipeline', torch_dtype=torch.float16)
pipe.enable_model_cpu_offload()
print('LOAD_OK', flush=True)
