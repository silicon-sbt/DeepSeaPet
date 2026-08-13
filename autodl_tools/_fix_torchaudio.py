"""装回与 torch 2.8.0 匹配的 torchaudio（+cu128），避免 libcudart.so.13 问题"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

c = conn.connect()
script = '''/root/miniconda3/bin/pip install "torchaudio==2.8.0" --timeout 60 --retries 1 2>&1 | tail -4'''
_, out, err = c.exec_command(script, timeout=300)
print(out.read().decode(errors="replace"))
e = err.read().decode(errors="replace")
if e:
    print("STDERR:", e[-300:])

# 验证 import torchaudio 不崩
_, out2, err2 = c.exec_command('/root/miniconda3/bin/python -c "import torchaudio; print(torchaudio.__version__)"', timeout=60)
print("验证:", out2.read().decode(errors="replace").strip())
e2 = err2.read().decode(errors="replace")
if e2:
    print("验证ERR:", e2[-200:])
c.close()
