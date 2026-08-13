"""迭代补装缺失依赖直到 lightx2v 完整 import 成功"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

c = conn.connect()
sftp = c.open_sftp()
# 上传一个探测脚本到远端
PROBE = r'''
import importlib, sys, re
missing = []
mods = ["lightx2v"]
try:
    import lightx2v
    from lightx2v import LightX2VPipeline
    print("IMPORT_FULL_OK")
except ModuleNotFoundError as e:
    m = re.search(r"No module named '([^']+)'", str(e))
    print("MISSING:", m.group(1) if m else repr(e)[:200])
    sys.exit(0)
except Exception as e:
    print("OTHER_ERR:", repr(e)[:200])
    sys.exit(0)
'''
with sftp.open("/tmp/_probe.py", "w") as f:
    f.write(PROBE)
sftp.close()

# 候选依赖包（纯 Python 小包，不装 gradio/modelscope/swanlab 等大件）
CANDIDATES = [
    "pydantic", "prometheus-client", "fastapi", "uvicorn", "aiohttp",
    "PyJWT", "zmq", "jsonschema", "pymongo",
    "aio-pika", "asyncpg", "aioboto3", "redis", "tos",
    "langdetect", "decord", "swanlab", "requests", "av", "torchao", "torchvision",
]

for _ in range(12):
    _, out, err = c.exec_command("/root/miniconda3/bin/python /tmp/_probe.py", timeout=120)
    o = out.read().decode(errors="replace")
    if "IMPORT_FULL_OK" in o:
        print("=== lightx2v 完整导入成功 ===")
        print(o)
        break
    m = re.search(r"MISSING: (\S+)", o)
    if not m:
        print("无法解析的失败:", o, err.read().decode(errors="replace")[-300:])
        break
    mod = m.group(1)
    # 从候选里找能提供该模块的包
    pkg = None
    for cand in CANDIDATES:
        base = cand.lower().replace("_", "")
        if base in mod.lower() or mod.lower() in base:
            pkg = cand
            break
    if not pkg:
        pkg = mod  # 直接用模块名试
    print(f"缺 {mod} → 尝试安装 {pkg}")
    _, out2, err2 = c.exec_command(f"/root/miniconda3/bin/pip install {pkg} --timeout 30 --retries 1 2>&1 | tail -2", timeout=300)
    print(out2.read().decode(errors="replace"))
c.close()
