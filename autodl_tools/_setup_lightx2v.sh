#!/bin/bash
# 安装 LightX2V + fp8 推理依赖（AutoDL GPU 模式运行）
set -x
PIP=/root/miniconda3/bin/pip
PY=/root/miniconda3/bin/python

# 1. lightx2v 本体（源码已上传 /root/autodl-tmp/lightx2v，不装依赖避免与现有环境冲突）
$PIP install -e /root/autodl-tmp/lightx2v --no-deps 2>&1 | tail -3

# 2. fp8-sgl 量化算子（要求 torch==2.8.0，环境已满足）
$PIP install sgl-kernel --upgrade 2>&1 | tail -3

# 3. 核心运行时依赖（轻量，AutoDL 可能已装部分）
$PIP install opencv-python imageio imageio-ffmpeg einops loguru omegaconf peft accelerate ftfy qtorch 2>&1 | tail -3

# 4. 验证
$PY -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
$PY -c "import lightx2v; print('lightx2v OK', lightx2v.__file__)"
$PY -c "import sgl_kernel; print('sgl_kernel OK')"
$PY -c "import cv2; print('opencv OK', cv2.__version__)"

echo SETUP_DONE
