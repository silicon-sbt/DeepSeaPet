"""诊断 lightx2v.pipeline 导入具体报错"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

script = "/root/miniconda3/bin/python -c \"import lightx2v; from lightx2v import LightX2VPipeline; print('LightX2VPipeline OK')\""
c = conn.connect()
_, out, err = c.exec_command(script, timeout=120)
print(out.read().decode(errors="replace"))
e = err.read().decode(errors="replace")
if e:
    print("STDERR:", e[-1500:])
c.close()
