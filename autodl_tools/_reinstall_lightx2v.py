"""重新 pip install -e lightx2v，使 editable finder 包含 lightx2v_platform"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

script = '''cd /root/autodl-tmp/lightx2v && /root/miniconda3/bin/pip install -e . --no-deps 2>&1 | tail -3 && /root/miniconda3/bin/python -c "import lightx2v; print('OK import lightx2v'); from lightx2v import LightX2VPipeline; print('OK LightX2VPipeline')"'''
c = conn.connect()
_, out, err = c.exec_command(script, timeout=180)
print(out.read().decode(errors="replace"))
e = err.read().decode(errors="replace")
if e:
    print("STDERR:", e[-800:])
c.close()
