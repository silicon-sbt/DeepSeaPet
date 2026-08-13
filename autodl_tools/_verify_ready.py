"""切 GPU 前的内容级核验：验证 IP-Adapter / SDXL / 基准图 / 脚本都完整可加载。
只读文件头，不加载权重，无卡模式可跑。全过打印 ALL_READY，任一失败打印 HAS_PROBLEM。
"""
import os, json

checks = []

# 1. config.json 是有效 JSON 且架构正确
p = "/root/autodl-tmp/ip_adapter/sdxl_models/image_encoder/config.json"
try:
    with open(p) as f:
        cfg = json.load(f)
    ok = cfg.get("architectures") == ["CLIPVisionModelWithProjection"]
    checks.append(("image_encoder config.json", ok, f"arch={cfg.get('architectures')}"))
except Exception as e:
    checks.append(("image_encoder config.json", False, f"JSON 无效: {str(e)[:50]}"))

# 2. safetensors 文件头：前 8 字节 = 小端 u64 header 长度（正常 1000~100M）
def check_st(path, name):
    try:
        with open(path, "rb") as f:
            head = f.read(8)
        if head[:4] == b"Entr":
            return (name, False, f"污染文件头 {head}")
        hlen = int.from_bytes(head, "little")
        ok = 1000 < hlen < 100_000_000
        return (name, ok, f"header_len={hlen} size={os.path.getsize(path)}")
    except Exception as e:
        return (name, False, str(e))

checks.append(check_st("/root/autodl-tmp/ip_adapter/sdxl_models/image_encoder/model.safetensors",
                       "image_encoder model.safetensors"))
checks.append(check_st("/root/autodl-tmp/ip_adapter/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors",
                       "ip-adapter-plus 主权重"))
checks.append(check_st("/root/autodl-tmp/models/animagineXL40_v40.safetensors",
                       "Animagine XL 4.0"))

# 3. 基准图 PNG 头
p = "/root/autodl-tmp/sprites_output/idle/idle_00.png"
try:
    with open(p, "rb") as f:
        head = f.read(8)
    checks.append(("基准图 idle_00.png", head[:4] == b"\x89PNG", f"size={os.path.getsize(p)}"))
except Exception as e:
    checks.append(("基准图 idle_00.png", False, str(e)))

# 4. 生成脚本存在且完整
p = "/root/autodl-tmp/generate_sdxl.py"
ok = os.path.exists(p) and os.path.getsize(p) > 1000
checks.append(("generate_sdxl.py", ok, f"size={os.path.getsize(p) if os.path.exists(p) else 0}"))

# 输出
allok = True
for name, ok, detail in checks:
    print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}", flush=True)
    allok = allok and ok
print("ALL_READY" if allok else "HAS_PROBLEM", flush=True)
