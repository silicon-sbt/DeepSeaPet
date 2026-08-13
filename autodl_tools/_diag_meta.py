"""递归定位 float16 加载后所有 meta param/buffer（enable_model_cpu_offload 崩溃根源）
v3: 跳过非 nn.Module（tokenizer/scheduler），每组件 try/except 崩溃不中断，打印组件类型
"""
import torch

from diffusers import WanPipeline

pipe = WanPipeline.from_pretrained('/root/autodl-tmp/wan_pipeline', torch_dtype=torch.float16)


def stat(m, prefix, depth=0):
    if m is None or depth > 3 or not isinstance(m, torch.nn.Module):
        return
    ps = list(m.parameters())
    bs = list(m.buffers())
    mp = [p for p in ps if p.is_meta]
    mb = [b for b in bs if b.is_meta]
    if mp or mb:
        keys = list(m.state_dict().keys())
        for i, p in enumerate(ps):
            if p.is_meta:
                print(f'  META_P {prefix}.{keys[i]} {tuple(p.shape)}', flush=True)
        for i, b in enumerate(bs):
            if b.is_meta:
                print(f'  META_B {prefix}.{keys[len(ps) + i]} {tuple(b.shape)}', flush=True)
    for n, c in m.named_children():
        stat(c, f'{prefix}.{n}', depth + 1)


for name, m in pipe.components.items():
    if m is None:
        continue
    tag = type(m).__name__
    if isinstance(m, torch.nn.Module):
        print(f'== {name} ({tag})', flush=True)
        try:
            stat(m, name)
        except Exception as e:
            print(f'  ERR {name}: {type(e).__name__}: {e}', flush=True)
    else:
        print(f'== {name} ({tag}, 非Module跳过)', flush=True)
print('DIAG_DONE', flush=True)
