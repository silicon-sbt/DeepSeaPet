"""诊断远端 torch/attn/fp8 能力（绕开 PowerShell 引号问题）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

PY = "/root/miniconda3/bin/python"
CMDS = [
    PY + " -c \"import torch; print('torch', torch.__version__); print('scaled_mm', hasattr(torch, '_scaled_mm')); print('cuda', torch.cuda.is_available())\"",
    PY + " -c \"import triton; print('triton', triton.__version__)\"",
    PY + " -c \"import flash_attn; print('flash_attn OK')\"",
    PY + " -c \"import sageattention; print('sageattention OK')\"",
    PY + " -c \"import sgl_kernel; print('sgl_kernel OK')\"",
    PY + " -c \"import cv2; print('opencv', cv2.__version__)\"",
    PY + " -c \"import einops, loguru, omegaconf; print('einops/loguru/omegaconf OK')\"",
]

c = conn.connect()
for cmd in CMDS:
    _, out, err = c.exec_command(cmd, timeout=30)
    o = out.read().decode(errors="replace").strip()
    e = err.read().decode(errors="replace").strip()
    status = "OK" if o else ("FAIL" if "No module" in e else "??")
    print(f"[{status}] {cmd[:80]}")
    if o:
        print(f"    {o}")
    elif e:
        print(f"    {e.splitlines()[-1][:100]}")
c.close()
