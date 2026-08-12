# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 运行 & 打包

```powershell
# 运行桌宠（开发模式）
python main.py

# 打包为单文件 exe
pip install pyinstaller
pyinstaller --onefile --windowed --name DeepSeaPet main.py
```

依赖只有 3 个 pip 包：`PySide6`、`openai`、`send2trash`，其余全是标准库。

## 架构

10 个源文件构成桌宠本体（含入口 main.py），其余是 AutoDL 远程精灵图生成的辅助脚本。托盘逻辑内联在 `main.py`——没有独立的 `tray.py`。

### 启动链

`main.py` → `App.__init__` → 创建 `ConfigManager`（单例）→ 托盘图标（代码绘制鲸鱼娘 icon）→ `PetWindow` → 启动打招呼气泡。点击桌宠懒加载 `ChatWindow`。托盘菜单集成 API 配置、自启开关、退出。

### 配置流

`ConfigManager` 是全局单例，所有模块通过 `ConfigManager.instance()` 获取。配置保存在 `%APPDATA%/DeepSeaPet/config.json`，每次 `set()` 即时写盘。对话存在同目录 `conversations.json`。

### 动画流

`AnimationController` 管理状态机（idle/walk/hide/peek/sleep/happy/**lying**），优先从 `module_5_assets/sprites/{state}_*.png` 加载帧序列，无素材时用 `make_placeholder_frames()` 代码绘制 Q版鲸鱼娘。`PetWindow` 通过 Qt 信号 `frame_changed` 接收帧更新，QTimer 驱动 8fps 循环。`lying` 状态为横向趴姿，用于聊天窗口。

### 聊天流

`ChatWindow._send()` → 后台线程调 `ApiClient.chat_stream()` → 逐 token 通过 `Signal` 跨线程回主线程 → `_on_stream_tick` 更新 HTML 气泡。`ApiClient` 包装 OpenAI SDK，自动兼容 DeepSeek 和自定义 OpenAI 兼容 API。

**聊天窗口 UI**：500×380 全透明无边框悬浮窗。上部透明消息区（气泡浮动在桌面），底部 `InputBar`（`paintEvent` 自绘圆角蓝边白底输入条，22px 圆角，3px `#4A9EFF` 边框）。左上角鲸鱼娘趴姿叠在输入条左上方，独立透明 QWidget。窗口 80% 透明度，拖拽移动，Ctrl+Enter 发送。

### 贴边隐藏

`PetWindow._check_edge()` 每 200ms 检查窗口距屏幕边缘距离。阈值 50px 内自动吸附，只露出 30px；鼠标靠近露出部分时展开。注意 PySide6 光标位置用 `QCursor.pos()`（静态方法），不是 `QScreen.cursor().pos()`。

### 垃圾桶

拖放文件到桌宠 → `PetWindow.dropEvent` → 信号 `files_dropped` → `TrashHandler.handle` → `send2trash`。默认弹确认框，可勾选"不再提示"写入 config。

### 开机自启

`AutoStartManager` → Windows 注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`，指向当前 Python 解释器 + main.py 路径（打包后指向 exe 自身）。

## AutoDL 精灵图生成

### 模型下载策略：先本地下载再上传

AutoDL 上直接下载大模型极慢且易断连（7GB 下了 6 小时）。**正确做法**：本地用 ModelScope 下载 → SFTP 上传到 AutoDL。

**注意**：AutoDL 数据盘只有 50GB，不能用大于 50GB 的模型（如 Wan2.1 FP16 原版 ~60GB）。

### 当前方案：Wan2.1 I2V 视频模型（`generate_video.py`）

SDXL img2img 方案已确认失败——帧间角色一致性无法保证（邻帧差异 ~71）。改为视频模型方案：

1. SDXL 生成每状态 1 张基准图（`{state}_00.png`）
2. Wan2.1 I2V 将基准图转为 25 帧短视频（通过文本 prompt 控制动作）
3. 从视频中均匀提取 8 帧作为精灵图

**模型**：`Wan-AI/Wan2.1-I2V-14B-480P-Diffusers`，FP8 量化版（~16GB），32GB 显存可用。

```powershell
# 本地下载 Wan2.1 FP8 模型
pip install modelscope
python -c "
from modelscope import snapshot_download
print(snapshot_download('Wan-AI/Wan2.1-I2V-14B-480P-Diffusers', cache_dir='E:/code/deepseek的桌宠/wan_model'))
"
```

### 上传到 AutoDL + 生成视频精灵图

**连接信息**：`autodl_tools/ssh`（每次克隆实例后端口和密码会变）。实例需手动开机。

**工作流程**：
1. 无卡模式开机（省钱），用 `autodl_tools/multi_upload.py` 多线程续传模型文件
2. 切换到 GPU 模式，`python autodl_tools/run_remote.py "nvidia-smi"` 验证 GPU 可用
3. `python autodl_tools/upload_and_run.py autodl_tools/generate_video.py` 上传并执行
4. 下载 `/root/autodl-tmp/sprites_video/` 到本地 → rembg 抠图 → 覆盖 `module_5_assets/sprites/`

### 辅助脚本 (`autodl_tools/`)

| 文件 | 用途 |
|------|------|
| `generate_video.py` | **当前方案**：Wan2.1 I2V 视频→帧精灵图 |
| `generate_sprites.py` | SDXL img2img 精灵图（**已弃用**，帧间一致性不达标） |
| `animation_design.md` | 7 状态 × 8 帧的详细动画设计文档（中文） |
| `upload_and_run.py` | paramiko SFTP 上传 + 远程执行 |
| `run_remote.py` | paramiko SSH 执行单条命令 |
| `multi_upload.py` | 多线程断点续传（4 路并行） |
| `resume_upload.py` | 单线程断点续传（备选） |
| `test_net.py` | 测试 AutoDL 网络连通性 |
| `check_server.py` | 检查服务器环境（已弃用） |
| `setup_comfyui.py` | ComfyUI 安装脚本（已弃用） |
| `ssh` | 当前实例连接信息 |

### 帧间一致性检查

`_check_coherence.py` 量化分析精灵图帧间一致性（像素差异），用于验证生成质量。
