"""下载 image_encoder（主权重已完整，跳过）。修正：URL 是 models/image_encoder/，本地输出 image_encoder/。
用「解析最终 CDN URL + curl -C 续传」绕过 302 丢 Range 的问题。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

c = connect()
c.exec_command("rm -f /root/autodl-tmp/ip_adapter/.done")[1].read()

SCRIPT = '''#!/bin/bash
set -e
source /etc/network_turbo
D=/root/autodl-tmp/ip_adapter
mkdir -p "$D/image_encoder"
BASE="https://huggingface.co/h94/IP-Adapter/resolve/main"
rm -f "$D/.done"

dl() {
  local path="$1" out="$2"
  local final
  final=$(curl -sIL -o /dev/null -w "%{url_effective}" "$BASE/$path")
  echo "downloading $path ($(echo "$final" | cut -c1-50)...)"
  curl -L -C - --retry 30 --retry-delay 5 --retry-all-errors -sS -o "$out" "$final"
}

dl "models/image_encoder/config.json" "$D/image_encoder/config.json"
dl "models/image_encoder/model.safetensors" "$D/image_encoder/model.safetensors"
echo DONE > "$D/.done"
ls -la "$D/image_encoder"
'''

write_cmd = "cat > /root/autodl-tmp/_dl_ipadapter_final.sh << 'SH_EOF'\n" + SCRIPT + "SH_EOF\n"
c.exec_command(write_cmd)[1].read()

_, out, err = c.exec_command("nohup bash /root/autodl-tmp/_dl_ipadapter_final.sh > /root/autodl-tmp/ip_dl.log 2>&1 & echo started pid=$!")
print(out.read().decode().strip(), flush=True)
c.close()
print("image_encoder 下载已启动（curl 续传 + set -e）")
