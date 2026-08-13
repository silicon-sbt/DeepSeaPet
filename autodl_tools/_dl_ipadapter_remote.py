"""下载 IP-Adapter 权重：SSH 通道 heredoc 写脚本 + nohup 后台执行（绕过 SFTP 中文路径问题）"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

SCRIPT = '''#!/bin/bash
set -e
D=/root/autodl-tmp/ip_adapter
mkdir -p "$D/sdxl_models" "$D/image_encoder"
BASE="https://hf-mirror.com/h94/IP-Adapter/resolve/main"
echo "[1/3] IP-Adapter Plus SDXL"
wget -q -O "$D/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors" "$BASE/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"
echo "[2/3] image_encoder config"
wget -q -O "$D/image_encoder/config.json" "$BASE/image_encoder/config.json"
echo "[3/3] image_encoder model"
wget -q -O "$D/image_encoder/model.safetensors" "$BASE/image_encoder/model.safetensors"
echo DONE > "$D/.done"
ls -la "$D/sdxl_models" "$D/image_encoder"
'''

c = connect()
write_cmd = "cat > /root/autodl-tmp/_dl_ipadapter.sh << 'SH_EOF'\n" + SCRIPT + "SH_EOF\n"
_, out, err = c.exec_command(write_cmd)
out.read(); err.read()

_, out, err = c.exec_command("nohup bash /root/autodl-tmp/_dl_ipadapter.sh > /root/autodl-tmp/ip_dl.log 2>&1 & echo started pid=$!")
print(out.read().decode().strip(), flush=True)
c.close()
print("下载已在后台启动，日志 /root/autodl-tmp/ip_dl.log")
