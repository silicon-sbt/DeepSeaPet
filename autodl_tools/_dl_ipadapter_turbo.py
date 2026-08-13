"""用 AutoDL 学术加速（/etc/network_turbo）直连 HuggingFace 官方源，重下 IP-Adapter。
先 kill 旧的 hf-mirror 慢速 wget，再 source network_turbo 重下。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

c = connect()

# 杀旧 wget（进程名精确匹配，不自杀）
_, out, err = c.exec_command("pkill -x wget; sleep 1; echo killed_old_wget")
out.read(); err.read()

SCRIPT = '''#!/bin/bash
source /etc/network_turbo
D=/root/autodl-tmp/ip_adapter
rm -f "$D/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors" "$D/.done"
mkdir -p "$D/sdxl_models" "$D/image_encoder"
BASE="https://huggingface.co/h94/IP-Adapter/resolve/main"
echo "[1/3] IP-Adapter Plus SDXL (turbo)"
wget -q -O "$D/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors" "$BASE/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"
echo "[2/3] image_encoder config"
wget -q -O "$D/image_encoder/config.json" "$BASE/image_encoder/config.json"
echo "[3/3] image_encoder model (turbo)"
wget -q -O "$D/image_encoder/model.safetensors" "$BASE/image_encoder/model.safetensors"
echo DONE > "$D/.done"
ls -la "$D/sdxl_models" "$D/image_encoder"
'''

write_cmd = "cat > /root/autodl-tmp/_dl_ipadapter_turbo.sh << 'SH_EOF'\n" + SCRIPT + "SH_EOF\n"
_, out, err = c.exec_command(write_cmd)
out.read(); err.read()

_, out, err = c.exec_command("nohup bash /root/autodl-tmp/_dl_ipadapter_turbo.sh > /root/autodl-tmp/ip_dl.log 2>&1 & echo started pid=$!")
print(out.read().decode().strip(), flush=True)
c.close()
print("学术加速下载已启动，日志 /root/autodl-tmp/ip_dl.log")
