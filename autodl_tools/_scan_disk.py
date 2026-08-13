"""扫盘：每 30 秒检查克隆实例数据盘关键文件是否完整，全部到位后打印 ALL_OK 退出。"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

# 精确比对字节数；None = 只查存在（大小 > 0）
EXPECT = [
    ("/root/autodl-tmp/ip_adapter/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors", 847517512),
    ("/root/autodl-tmp/ip_adapter/sdxl_models/image_encoder/model.safetensors", 2528373448),
    ("/root/autodl-tmp/ip_adapter/sdxl_models/image_encoder/config.json", 560),
    ("/root/autodl-tmp/models/animagineXL40_v40.safetensors", 6938434056),
    ("/root/autodl-tmp/sprites_output/idle/idle_00.png", 458966),
    ("/root/autodl-tmp/generate_sdxl.py", None),
]

STAT = "for p in " + " ".join(f'"{p}"' for p, _ in EXPECT) + \
       "; do stat -c%s \"$p\" 2>/dev/null || echo X; done"

def check():
    c = connect(timeout=15)
    _, out, _ = c.exec_command(STAT, timeout=30)
    sizes = [l.strip() for l in out.read().decode().split() if l.strip()]
    c.close()
    return sizes

while True:
    stamp = time.strftime("%H:%M:%S")
    try:
        sizes = check()
    except Exception as e:
        print(f"[{stamp}] 连接失败（克隆/开机中）: {str(e)[:60]}", flush=True)
        time.sleep(30)
        continue

    ok = True
    for (path, want), got in zip(EXPECT, sizes):
        if want is None:
            if got in ("X", "0"):
                print(f"[{stamp}] 缺失 {path}", flush=True); ok = False
        elif got != str(want):
            print(f"[{stamp}] 大小不符 {path}: 期望 {want} 实际 {got}", flush=True); ok = False

    if ok:
        print(f"[{stamp}] ALL_OK 全部文件完整", flush=True)
        break
    print(f"[{stamp}] 未就绪，30s 后再查", flush=True)
    time.sleep(30)
