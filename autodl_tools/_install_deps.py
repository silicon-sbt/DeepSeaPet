"""补装 LightX2V 缺失的纯 Python 小依赖（绕过 sgl-kernel 网络坑）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

PKGS = "gguf qtorch imageio imageio-ffmpeg"
script = f'''/root/miniconda3/bin/pip install {PKGS} --timeout 30 --retries 1 2>&1 | tail -5'''
c = conn.connect()
_, out, err = c.exec_command(script, timeout=300)
print(out.read().decode(errors="replace"))
e = err.read().decode(errors="replace")
if e:
    print("STDERR:", e[-400:])
c.close()
