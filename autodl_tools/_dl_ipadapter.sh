#!/bin/bash
# 下载 IP-Adapter SDXL 权重 + image encoder（从 hf-mirror 国内镜像）
set -e
D=/root/autodl-tmp/ip_adapter
mkdir -p "$D/sdxl_models" "$D/image_encoder"
BASE="https://hf-mirror.com/h94/IP-Adapter/resolve/main"

echo "=== [1/3] IP-Adapter Plus SDXL 权重 ==="
wget -q --show-progress -O "$D/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors" \
  "$BASE/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"

echo "=== [2/3] image encoder config ==="
wget -q -O "$D/image_encoder/config.json" "$BASE/image_encoder/config.json"

echo "=== [3/3] image encoder model (OpenCLIP) ==="
wget -q --show-progress -O "$D/image_encoder/model.safetensors" \
  "$BASE/image_encoder/model.safetensors"

echo "DONE" > "$D/.done"
echo "=== 下载完成 ==="
ls -la "$D/sdxl_models" "$D/image_encoder"
