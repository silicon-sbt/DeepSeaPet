# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 运行 & 打包

```powershell
# 运行桌宠（开发模式）
python main.py

# 打包为单文件 exe（必须 --add-data 带上精灵图素材，否则 exe 里没有 sprites → 全部回退占位图）
pip install pyinstaller
pyinstaller --onefile --windowed --name DeepSeaPet --add-data "module_5_assets;module_5_assets" main.py
```

依赖只有 3 个 pip 包：`PySide6`、`openai`、`send2trash`，其余全是标准库。

## 架构

10 个源文件构成桌宠本体（含入口 main.py），其余是 AutoDL 远程精灵图生成的辅助脚本。托盘逻辑内联在 `main.py`——没有独立的 `tray.py`。

### 启动链

`main.py` → `App.__init__` → 创建 `ConfigManager`（单例）→ 托盘图标（代码绘制鲸鱼娘 icon）→ `PetWindow` → 启动打招呼气泡 + 1.5s 后台预取余额（`_prefetch_balance` → 模块缓存 `_balance_cache`，单击云朵秒显余额）。托盘菜单集成 API 配置、自启开关、退出。

**桌宠交互**（全部在 `PetWindow` 鼠标事件内判定）：**单击** = 余额云朵（`show_balance_bubble` toggle；贴边隐藏时 `snap_to_edge` 自动收起）、**双击** = 聊天窗（信号 `chat_requested` → `_on_pet_chat_requested` 懒加载 `ChatWindow`）、**三击** = 跳舞（自研判定：`TRIPLE_SPAN=0.75`s 内三次点击即跳舞，不依赖 Qt 双击事件；`_start_dance` 先强制 `_mode="idle"` 放行 `set_state` 门控）。单击确认 `CLICK_CONFIRM_MS=300`、双击/三击保护期 `_dbl_guard_until`、三击窗口 `TRIPLE_WINDOW=0.45`、单击代际 `_click_gen` 作废旧确认定时。

### 配置流

`ConfigManager` 是全局单例，所有模块通过 `ConfigManager.instance()` 获取。配置保存在 `%APPDATA%/DeepSeaPet/config.json`，每次 `set()` 即时写盘。对话存在同目录 `conversations.json`。

### 动画流

`AnimationController` 管理状态机（idle/walk/hide/peek/sleep/happy/**lying**/**held**/**flying**），每状态只从 `module_5_assets/sprites/{state}_*.png` 加载**帧 0 作静态底图**（`load_from_dir` 只取 `[:1]`），无素材时用 `make_placeholder_frames()` 代码绘制 Q版鲸鱼娘。动作交给**程序化变换**而非逐帧序列：`PetWindow._render` 用 QPainter 叠加 **镜像(`_facing`)**+倾斜(`_tilt_angle`)+缩放(`_scale_x/_scale_y`)+位移(`_bob_x/_bob_y`)，60fps 物理 timer 常驻驱动。变换顺序 `translate(half) → scale(_facing,1) → rotate(_tilt_angle*_facing) → scale(sx,sy) → translate(bob) → draw(-half,-half)`；镜像用 `rotate(angle*_facing)` 反角补偿，使视觉倾倒方向不随镜像翻转。idle 呼吸 `sin(t*1.5)*0.02`、happy 双击跳跃 `-40*sin(π*t/2)`、held/flying 走弹簧+重力物理、hide/peek 走弹簧逼近 `_start_slide`。`_anim_t` 为统一动画相位，`set_state` 切状态时重置。`lying` 状态为横向趴姿。**注意** `set_state` 有门控：`_mode != "idle"` 时只放行 held/flying，其余状态被拒（跳舞前需先回 idle）。

### 聊天流

`ChatWindow._send()` → 后台线程调 `ApiClient.chat_stream()` → 逐 token 通过 `Signal` 跨线程回主线程 → `_on_stream_tick` 更新 HTML 气泡。`ApiClient` 包装 OpenAI SDK，自动兼容 DeepSeek 和自定义 OpenAI 兼容 API。

**聊天窗口 UI**（`module_3_chat/chat_window.py`，520×450 可调整大小）：深海主题卡片式悬浮窗——`paintEvent` 手绘 7 层柔和阴影 + 渐变卡片背景（`WA_TranslucentBackground`），**四边/四角可自由调整大小**（最小 400×360；app 级 `eventFilter` 统一接管鼠标：8px 边缘检测 → `startSystemResize` 原生缩放、悬停光标反馈、空白区拖拽移动、输入框内按下不误拖）。结构：header（圆形鲸鱼娘头像 idle 图 + 名字 + 在线点 + 32px 圆润关闭钮）→ 1px 淡蓝分隔线 → 消息区（**尾巴气泡** `ChatBubble`：QPainter 四角独立圆角 + 三角尾巴 + 渐变，AI 白→浅蓝左尾配圆形头像，用户蓝渐变右尾配蓝底"我"头像；**打字指示器** `TypingBubble` 三点弹跳动画，首 token 到达自动替换为真实气泡）→ 胶囊输入区（浅蓝底圆角输入框 + 圆形渐变发送钮）。气泡淡入动画，Ctrl+Enter 发送。

### 余额云朵（BalanceBubble）

**独立透明悬浮窗**（`Qt.Tool|Frameless|StaysOnTop`，340×200），显示在桌宠**正上方**（`place_above`：水平居中、顶部 18px、底部小尾巴指向角色；顶部放不下时自动落到下方、尾巴翻转朝上）。**云朵形状**：`QPainterPath` 5 圆并集（必须 `setFillRule(Qt.WindingFill)`——默认 OddEvenFill 会把圆重叠区镂空成洞！）+ 内部底部渐变阴影（clip 在云朵内，无外溢像素；**透明顶层窗口禁用 `QGraphicsDropShadowEffect`**——阴影外扩超出窗口边界会触发 Windows `UpdateLayeredWindowIndirect` 报错）。功能：点击刷新、60s 自动刷新（`_auto_timer`）、金额滚动动画（QTimer 20ms 缓动插值）、启动预取缓存秒显。`moveEvent` 跟随桌宠移动。

### 贴边隐藏

`PetWindow._check_edge()` 每 200ms 检查窗口距屏幕边缘距离。阈值 50px 内自动吸附，只露出 30px；鼠标靠近露出部分时展开。注意 PySide6 光标位置用 `QCursor.pos()`（静态方法），不是 `QScreen.cursor().pos()`。

### 拎起甩物理

`PetWindow` 拖拽改为物理驱动（非直接平移）。鼠标按住超 5px 触发 `_start_grab`（held 惊慌表情，抓取锚点设在领口 `QPointF(PET_SIZE*0.52, PET_SIZE*0.64)`）→ 弹簧-阻尼跟随（`_step_grabbed`，K=200/C=28 临界阻尼，滞后惯性无震荡）→ 松手按甩速 + 重力落地弹跳（`_step_flying`，G=2000/REST=0.55，进入 flying 态切 `set_state("flying")` 闭眼尖叫）→ `_render` 用 QPainter 绕中心旋转倾斜（`_step_tilt` 限 ±30°）。**转身**由鼠标位移驱动：grabbed 态用指数平滑位移 `_drag_dx = _drag_dx*0.6 + Δx`（阈值 ±6px，解决稳态 `_vx≈0` 慢拖不翻转），flying 态用甩速 `_vx` 方向（阈值 ±5）。物理 `_phys_timer` 16ms 与 8fps 动画 timer 解耦；`_check_edge` 在 `_mode != "idle"` 时停用。

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
3. happy 单图已验证（llava 确认身份锁定），批量脚本就绪：9 状态 × 8 帧

**模型**：Animagine XL 4.0（6.9G，`from_single_file`）+ IP-Adapter Plus SDXL（808M），均已在 `/root/autodl-tmp/`。状态：**✅ 已完成**——9 状态 × 8 帧全部生成 + rembg 抠图 + 入库 `module_5_assets/sprites/`（72 帧，llava 目测身份锁定达标）。

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

> **✅ 已完成**（2026-08）：9 状态 × 8 帧全部生成并入库。流程留档备用：

1. 切 GPU 模式开机，`run_remote.py "nvidia-smi"` 验证 CUDA
2. 上传黑皮鞋基准图 → 覆盖 `/root/autodl-tmp/sprites_output/idle/idle_00.png`
3. `upload_and_run.py autodl_tools/generate_sdxl.py` 批量 9 状态（held/flying/lying 走 txt2img 单独生成基准）
4. 下载 `/root/autodl-tmp/sprites_output/{state}/` → rembg 抠图 → 覆盖 `module_5_assets/sprites/`

### 当前活跃：即梦 I2V 行走视频（`imeng_walk.py`）

> 完整管线/状态/坐标备忘在 **`HANDOFF_walk_video.md`**（交接 deepseek harness 的文档），本节只记要点。

- **目标**：AutoDL 即梦 (Seedance 2.0) I2V API，以干净锚点 `_walk_gen/anchor_clean.png` 生成 **2D 横版行走循环**，抽 8 关键帧替换 `module_5_assets/sprites/walk_00..07.png`（替代已弃用的 LightX2V 视频方案）。
- **用法**：`python autodl_tools/imeng_walk.py --anchor "E:\code\deepseek的桌宠\_walk_gen\anchor_clean.png"` → 下载 `_walk_gen/walk_raw.mp4`；`--dry-run` 只看请求体不花钱。
- **计费**：一次 5s 720p ≈ 108900 tokens ≈ **¥5**；`video_url` 24h 有效，拿到立刻下载。
- **⚠️ API key 红线**：即梦 key 只在用户全局 `C:\Users\A\.claude\CLAUDE.md`，经环境变量 `IMENG_KEY` 注入（**`imeng_walk.py` 无硬编码默认值，设了才跑**）。**绝不能写进本仓库任何文件**（DeepSeaPet 是 PUBLIC 仓库）。
- **桌宠加载真相**：`animation.py:46` `load_from_dir` 只取 `[:1]`——**walk_01..07 不会显示**，walk 动画是程序化 bob/tilt 叠在单帧上；要真步态须先改它（方案见交接文档 §7）。

### 辅助脚本 (`autodl_tools/`)

| 文件 | 用途 |
|------|------|
| `conn.py` | **连接统一入口**：解析 `ssh` 文件返回 (host,port,user,pw)，克隆实例后只改一处 |
| `launch_remote.py` | 通用：上传本地文件 + nohup 后台启动，日志 `/root/autodl-tmp/{basename}.log` |
| `_poll_remote.py` | 通用：复用 SSH 连接轮询远端日志，出现完成词/失败标记即退出 |
| `generate_sdxl.py` | **当前方案**：SDXL img2img + IP-Adapter 身份锁定，批量 9 状态 × 8 帧（单图已验证） |
| `imeng_walk.py` | **当前活跃**：即梦 Seedance 2.0 I2V 生成行走循环视频（¥5/次 → `_walk_gen/walk_raw.mp4`） |
| `generate_video.py` | LightX2V 蒸馏 Wan2.1 I2V 视频→帧精灵图（**已弃用**，帧一致性 ~71 不达标） |
| `_build_pipeline.py` | 组装 distill_fp8 + 官方小件 → `wan_pipeline/`（transformer 硬链接省盘；UMT5/VAE 统一 `convert_pth`） |
| `_fast_download.py` | 多线程 Range 分块下载 + `.done` 完整性标记（分块全成功才算完成，`os.pwrite` 免锁） |
| `_upload_build.py` | 上传组装脚本+基准图，nohup 后台启动组装 |
| `_prep_base.py` | rembg 抠图基准图 → 白底 RGB 720×720 基准图 |
| `_check_wan.py` | HTTP API 探测 ModelScope 仓库结构 |
| `_vlm_look.py` | 本地 Ollama llava:7b 视觉自审（无视觉环境下"看"图） |
| `_ascii_view.py` | ASCII 渲染基准图/生成帧（无视觉环境备选） |
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
- **关机命令**：用 `shutdown -h now`（SysV），别用 `poweroff`——AutoDL 容器非 systemd，`poweroff` 是 systemd 符号链接，报 `System has not been booted with systemd` 且不关机。生成跑完自动关机时务必用 `shutdown -h now`。

### GitHub 推送（GFW 踩坑）

仓库：`github.com/silicon-sbt/DeepSeaPet.git`（**PUBLIC**）。本地上传经 GFW 时大流量 SSH 会被重置（`Connection reset by peer` / `send-pack: unexpected disconnect while reading sideband packet`），认证正常但传输中断。实测经验：

- **22 端口 SSH**：316KB 代码勉强能过，≥2MB 必被重置。
- **443 端口 SSH**（`git -c core.sshCommand="ssh -p 443 -o HostName=ssh.github.com" push`）：阈值更高，但 ~2.4MB 以上仍是概率性失败。
- **稳定方案**：443 端口 + **小批量拆分**——每批 ≤1.2MB（约 4 帧 PNG）连续成功；失败就 `git reset --soft HEAD~1 && git reset HEAD` 拆更小再推。21MB 素材最终拆成 ~20 个 commit 推完。
- **敏感文件**（`api火山`、`autodl_tools/ssh`、`config.json`、`conversations.json`、硬编码密码的 `_test_ssh.py/_deploy.py/_check_env.py`）已在 `.gitignore`，提交前用 `git ls-files | grep -iE ...` 复查。`imeng_walk.py` **不在** gitignore，但已改纯 env-only（无 key 默认值）——提交前必须再 grep 确认无 `IMENG_KEY` 硬编码。
