"""在 AutoDL 5090 上安装 ComfyUI + 模型"""
import paramiko, time, sys

host = 'connect.weste.seetacloud.com'
port = 26891
user = 'root'
pwd = 'REDACTED'

def run(cmd, timeout=120):
    """执行远程命令并返回输出"""
    print(f'  >>> {cmd[:80]}...', flush=True)
    _, out, err = c.exec_command(cmd, timeout=timeout)
    out_str = out.read().decode().strip()
    err_str = err.read().decode().strip()
    if out_str:
        print(out_str[:500], flush=True)
    if err_str:
        print(err_str[:300], flush=True)
    return out_str, err_str

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, port=port, username=user, password=pwd, timeout=30)
print('=== AutoDL 5090 环境 ===', flush=True)

# 1. 激活 conda
print('\n[1] 检查 Conda...', flush=True)
run('source /root/miniconda3/etc/profile.d/conda.sh && conda --version')
run('source /root/miniconda3/etc/profile.d/conda.sh && python -V')

# 2. 创建 ComfyUI 环境
print('\n[2] Clone ComfyUI...', flush=True)
run('cd /root/autodl-tmp && git clone https://github.com/comfyanonymous/ComfyUI.git 2>&1 || echo "已存在"')

# 3. 安装 PyTorch (CUDA 12.4)
print('\n[3] 装 PyTorch...', flush=True)
run('source /root/miniconda3/etc/profile.d/conda.sh && pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -5', timeout=300)

# 4. 装 ComfyUI 依赖
print('\n[4] 装 ComfyUI 依赖...', flush=True)
run('source /root/miniconda3/etc/profile.d/conda.sh && pip install -r /root/autodl-tmp/ComfyUI/requirements.txt 2>&1 | tail -5', timeout=300)

# 5. 检查 CUDA
print('\n[5] 验证 CUDA...', flush=True)
run('source /root/miniconda3/etc/profile.d/conda.sh && python -c "import torch; print(f\"CUDA:{torch.cuda.is_available()} GPU:{torch.cuda.get_device_name(0)}\")"')

# 6. 下载 SDXL 模型
print('\n[6] 下载模型...', flush=True)
run('mkdir -p /root/autodl-tmp/ComfyUI/models/checkpoints', timeout=10)
# 使用 Animagine XL (专门优化动漫角色)
run('cd /root/autodl-tmp/ComfyUI/models/checkpoints && wget -q --show-progress -O animagineXL40.safetensors "https://huggingface.co/cagliostrolab/animagine-xl-4.0/resolve/main/animagine-xl-4.0.safetensors" 2>&1 | tail -3', timeout=600)

c.close()
print('\n=== 完成! ===', flush=True)
