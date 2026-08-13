"""重下 IP-Adapter（修复版）：curl 断点续传 + 自动重试 + set -e。
上一版漏了 set -e，wget 断连后脚本跑完误写 .done；此版 curl -C 续传保住 847MB 进度。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

c = connect()

# 先删误写的 .done（防止后台轮询误判完成）
c.exec_command("rm -f /root/autodl-tmp/ip_adapter/.done")[1].read()

SCRIPT = '''#!/bin/bash
set -e
source /etc/network_turbo
D=/root/autodl-tmp/ip_adapter
mkdir -p "$D/sdxl_models" "$D/image_encoder"
BASE="https://huggingface.co/h94/IP-Adapter/resolve/main"
rm -f "$D/.done"

echo "[1/3] IP-Adapter (curl -C retry)"
curl -L -C - --retry 30 --retry-delay 5 --retry-all-errors -sS \
  -o "$D/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors" \
  "$BASE/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"
echo "[2/3] config"
curl -L -C - --retry 30 --retry-delay 5 --retry-all-errors -sS \
  -o "$D/image_encoder/config.json" "$BASE/image_encoder/config.json"
echo "[3/3] model"
curl -L -C - --retry 30 --retry-delay 5 --retry-all-errors -sS \
  -o "$D/image_encoder/model.safetensors" "$BASE/image_encoder/model.safetensors"
echo DONE > "$D/.done"
ls -la "$D/sdxl_models" "$D/image_encoder"
'''

write_cmd = "cat > /root/autodl-tmp/_dl_ipadapter_turbo.sh << 'SH_EOF'\n" + SCRIPT + "SH_EOF\n"
c.exec_command(write_cmd)[1].read()

_, out, err = c.exec_command("nohup bash /root/autodl-tmp/_dl_ipadapter_turbo.sh > /root/autodl-tmp/ip_dl.log 2>&1 & echo started pid=$!")
print(out.read().decode().strip(), flush=True)
c.close()
print("重试下载已启动（curl 续传 + set -e）")
