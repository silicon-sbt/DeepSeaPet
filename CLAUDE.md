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

`AnimationController` 管理状态机（idle/walk/hide/peek/sleep/happy/**lying**/**held**/**flying**），优先从 `module_5_assets/sprites/{state}_*.png` 加载帧序列，无素材时用 `make_placeholder_frames()` 代码绘制 Q版鲸鱼娘。`PetWindow` 通过 Qt 信号 `frame_changed` 接收帧更新，QTimer 驱动 8fps 循环。`lying` 状态为横向趴姿，用于聊天窗口。

### 聊天流

`ChatWindow._send()` → 后台线程调 `ApiClient.chat_stream()` → 逐 token 通过 `Signal` 跨线程回主线程 → `_on_stream_tick` 更新 HTML 气泡。`ApiClient` 包装 OpenAI SDK，自动兼容 DeepSeek 和自定义 OpenAI 兼容 API。

**聊天窗口 UI**：500×380 全透明无边框悬浮窗。上部透明消息区（气泡浮动在桌面），底部 `InputBar`（`paintEvent` 自绘圆角蓝边白底输入条，22px 圆角，3px `#4A9EFF` 边框）。左上角鲸鱼娘趴姿叠在输入条左上方，独立透明 QWidget。窗口 80% 透明度，拖拽移动，Ctrl+Enter 发送。

### 贴边隐藏

`PetWindow._check_edge()` 每 200ms 检查窗口距屏幕边缘距离。阈值 50px 内自动吸附，只露出 30px；鼠标靠近露出部分时展开。注意 PySide6 光标位置用 `QCursor.pos()`（静态方法），不是 `QScreen.cursor().pos()`。

### 拎起甩物理

`PetWindow` 拖拽改为物理驱动（非直接平移）。鼠标按住超 5px 触发 `_start_grab`（held 惊慌表情）→ 弹簧-阻尼跟随（`_step_grabbed`，K=70/C=17 临界阻尼，滞后惯性无震荡）→ 松手按甩速 + 重力落地弹跳（`_step_flying`，G=2000/REST=0.55，进入 flying 态切 `set_state("flying")` 闭眼尖叫）→ `_render` 用 QPainter 绕中心旋转倾斜（`_step_tilt` 限 ±12°）。物理 `_phys_timer` 16ms 与 8fps 动画 timer 解耦；`_check_edge` 在 `_mode != "idle"` 时停用。**参数待真实精灵图到位后调手感**（占位图看不出效果）。

### 垃圾桶

拖放文件到桌宠 → `PetWindow.dropEvent` → 信号 `files_dropped` → `TrashHandler.handle` → `send2trash`。默认弹确认框，可勾选"不再提示"写入 config。

### 开机自启

`AutoStartManager` → Windows 注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`，指向当前 Python 解释器 + main.py 路径（打包后指向 exe 自身）。

## AutoDL 精灵图生成

### 硬约束

- **数据盘 50GB**，不能用 >50GB 的模型（官方 Wan2.1 90GB / FP16 原版 60GB 都超）。
- 连接信息在 `autodl_tools/ssh`（克隆实例后端口和密码会变），实例需手动开机。
- AutoDL 上 Python 在 `/root/miniconda3/bin/python`（不在 PATH），已装 diffusers 0.39 + torch 2.8.0+cu128。
- 常开**无卡模式**省钱，只有跑生成时才切 GPU。
- **无卡模式内存仅 2GB**（cgroup `memory.max`）：加载大权重（UMT5 6.7GB 转换峰值 ~13GB）必 OOM（退出码 137）。**组装也必须 GPU 模式跑**。`free` 显示 754GB 是宿主机，容器真实限制查 `/sys/fs/cgroup/memory.max`。

### 当前方案：SDXL img2img + IP-Adapter 身份锁定（`generate_sdxl.py`）

两条已放弃的路：LightX2V Wan2.1 I2V 视频模型、纯 SDXL img2img 都在帧间角色一致性上失败（邻帧差异 ~71）。当前用 2dimg2motion 思路——**身份层 + 姿势层分离**：

1. **身份层**：IP-Adapter Plus SDXL 用基准图锁住 Q 版角色身份（`ip_adapter_image` + `set_ip_adapter_scale(0.8)`）
2. **姿势层**：SDXL img2img 以基准图为构图/姿势起点（`strength=0.55`）
3. 先跑 `generate_sdxl.py happy` 单图，本地 llava 验证身份锁住后，再批量 7 状态

**模型**：Animagine XL 4.0（6.9G，`from_single_file`）+ IP-Adapter Plus SDXL（808M），均已在 `/root/autodl-tmp/`。状态：**未验证**（等切 GPU 跑测试图）。

### 模型下载

> 以下「模型下载 / 组装 diffusers 目录」是**已放弃的 Wan2.1 路径**记录，保留因下载技巧（Range 分块、modelscope 坑）仍通用。

在 AutoDL 上用 ModelScope 下载（官方小件快，单大文件慢）。**关键经验**：

- `modelscope download --model ... --include 'p1' 'p2' ... --local-dir ...`：`--include` 是 `nargs='+'`，多个 pattern 各自独立引号。
- **单大文件（6.7GB UMT5）modelscope 极慢** → 改用 `_fast_download.py` 多线程 Range 分块下载：urllib 请求带 `Range: bytes=x-y`，16 线程并发，`os.pwrite` 写不重叠偏移。**必须流式写（每块 2MB）**，否则 OOM（退出码 137）。
- **小文件（<1MB）别用 Range 分块**：modelscope CDN 对并发 Range 小请求返回 404（config.json/index.json 曾全部 404）。`_fast_download.py` 已自动改单请求直下。
- 拿文件总大小：HEAD 无 Content-Length，用 `GET Range: bytes=0-0` 从 `Content-Range` 头解析。

### 组装 diffusers 目录

distill_fp8 是分片格式但**无 `model_index.json`**，需 `_build_pipeline.py` 组装成 `WanPipeline.from_pretrained()` 可加载的目录：

- **必须在 GPU 模式跑**（无卡模式 2GB 内存必 OOM，见硬约束），并加 `python -u`（stdout 全缓冲，后台日志会 0 字节）。
- UMT5/VAE 的 `.pth` 是 **ZIP 格式**（文件头 `PK\x03\x04`），`tar -tf` 打不开是正常现象；`torch.load` 自动识别，无需解包。
- `transformer/` = distill_fp8 的 40 个 block + non_block + config + index（硬链接直接复制，省磁盘）
- `text_encoder/` = `models_t5_umt5-xxl-enc-fp8.pth` → safetensors + 官方 config
- `vae/` = `Wan2.1_VAE.pth` → safetensors + 官方 config
- `image_encoder/` + `scheduler/` + `tokenizer/` + `model_index.json` 从官方仓库小件复制
- 组装完成后 `ms_cache/distill_fp8/block_*.safetensors`（16GB）可删——`wan_pipeline/transformer` 持有独立副本不受影响。

### 生成工作流（SDXL + IP-Adapter）

1. 无卡模式开机，下载模型（Animagine XL 4.0 + IP-Adapter 三文件）
2. 本地 `_prep_base.py` 抠图基准图合白底 → 上传到 `/root/autodl-tmp/sprites_output/{state}/{state}_00.png`
3. 切 GPU 模式开机，`run_remote.py "nvidia-smi"` 验证 CUDA
4. `upload_and_run.py autodl_tools/generate_sdxl.py happy` 跑单图测试
5. 下载测试图 → 本地 llava 验证 IP-Adapter 是否锁住身份 → 确认后批量 7 状态
6. 下载 `/root/autodl-tmp/sprites_video/` → rembg 抠图 → 覆盖 `module_5_assets/sprites/`

### 辅助脚本 (`autodl_tools/`)

| 文件 | 用途 |
|------|------|
| `conn.py` | **连接统一入口**：解析 `ssh` 文件返回 (host,port,user,pw)，克隆实例后只改一处 |
| `launch_remote.py` | 通用：上传本地文件 + nohup 后台启动，日志 `/root/autodl-tmp/{basename}.log` |
| `_poll_remote.py` | 通用：复用 SSH 连接轮询远端日志，出现完成词/失败标记即退出 |
| `generate_sdxl.py` | **当前方案**：SDXL img2img + IP-Adapter 身份锁定（未验证） |
| `generate_video.py` | LightX2V 蒸馏 Wan2.1 I2V 视频→帧精灵图（**已弃用**，帧一致性 ~71 不达标） |
| `_build_pipeline.py` | 组装 distill_fp8 + 官方小件 → `wan_pipeline/`（transformer 硬链接省盘；UMT5/VAE 统一 `convert_pth`） |
| `_fast_download.py` | 多线程 Range 分块下载 + `.done` 完整性标记（分块全成功才算完成，`os.pwrite` 免锁） |
| `_upload_build.py` | 上传组装脚本+基准图，nohup 后台启动组装 |
| `_prep_base.py` | rembg 抠图基准图 → 白底 RGB 720×720 基准图 |
| `_check_wan.py` | HTTP API 探测 ModelScope 仓库结构 |
| `generate_sprites.py` | 纯 SDXL img2img 精灵图（**已弃用**，无 IP-Adapter，一致性不达标） |
| `animation_design.md` | 7 状态 × 8 帧的详细动画设计文档（中文） |
| `upload_and_run.py` | SFTP 上传 + 前台执行（实时打印输出） |
| `run_remote.py` | SSH 执行单条命令 |
| `multi_upload.py` | 多线程断点续传（上传模型用，已弃用） |
| `resume_upload.py` | 单线程断点续传（已弃用，密码过期勿用） |
| `test_net.py` | 测试 AutoDL 网络连通性 |
| `check_server.py` | 检查服务器环境（已弃用） |
| `setup_comfyui.py` | ComfyUI 安装脚本（已弃用） |
| `ssh` | 当前实例连接信息（唯一凭据源，conn.py 读取） |

根目录 `_check_coherence.py`：量化分析精灵图帧间一致性（像素差异），验证生成质量。

### 操作注意

- **连接信息只改 `autodl_tools/ssh`**：克隆实例后端口/密码必变，只改这一个文件，`conn.py` 自动解析；勿在脚本里硬编码（resume_upload.py 等遗留脚本的密码已过期）。
- **run_remote.py 传参坑**：PowerShell 传双引号给 python.exe 会被 Windows C runtime 剥掉。远端命令用**单引号**：`run_remote.py "/root/miniconda3/bin/python -c 'import torch; print(torch.cuda.is_available())'"`
- **pkill 自杀陷阱**：`pkill -f` 的 pattern 会匹配到当前执行命令自身命令行，杀掉自己。后台任务重启时不要带 pkill。
- **下载完整性**：文件大小对≠内容完整——分块下载失败会留空洞（UMT5 曾因此损坏，`torch.load` 报 `KeyError: 'storages' not found`）。以 `_fast_download.py` 的 `.done` 标记为准；UMT5 是 ZIP 格式，用文件头 `PK\x03\x04` 验证，不是 `tar -tf`。
- **stdout 全缓冲**：nohup 后台 + print 是块缓冲，进程被杀后日志 0 字节。诊断问题用 `python -u` 前台跑。
- **free 显示的是宿主机**：容器内存限制看 `/sys/fs/cgroup/memory.max`（无卡模式 2GB），不是 `free -h` 的 754GB。
- **磁盘管理**：50GB 数据盘容易满（曾 95%）。组装完成后删 `ms_cache/distill_fp8/block_*.safetensors`（16GB）；大文件只下 E 盘或 AutoDL，别下 C 盘。
- **IP-Adapter 下载**：IP-Adapter Plus SDXL 真实大小 808MB（847,517,512 字节），常见误记 1.44G。image_encoder 在 HF 仓库路径是 `models/image_encoder/`（不是 `image_encoder/`）。
- **`load_ip_adapter` 子目录**：`image_encoder_folder` 默认 `'image_encoder'`，与 `subfolder` 组合成 `sdxl_models/image_encoder/`。本地按此布局放，别传绝对路径。
- **学术加速**：`source /etc/network_turbo` 后直连 HF ~8MB/s（hf-mirror 仅 1.1MB/s）；但 HF `resolve/main` 302 会丢 Range 头，续传前先 `curl -sIL -o /dev/null -w '%{url_effective}'` 解析 CDN URL。
- **下载脚本必须 `set -e`**：否则 curl/wget 中途失败仍跑完并误写 `.done`，轮询误判完成（本次踩坑）。
