# 🐋 深海鲸鱼娘 — DeepSeaPet

一只傲娇的深海鲸鱼娘桌面宠物，基于 PySide6。她是 DeepSeek 的娘化形象 —— 蓝色渐变长发、鲸鱼尾巴头饰、深蓝女仆装。会陪你聊天、在桌面漫步、贴边隐藏、被拎起来甩飞、帮你丢垃圾。

## 特性

- 🎭 **9 状态动画桌宠** — 待机/行走/隐藏/探头/睡觉/开心/趴姿/拎起/飞落，动作由**程序化物理**驱动（60fps 弹簧-阻尼 + 重力 + 镜像/倾斜/缩放变换），非逐帧动画
- 🖐️ **拎起甩物理** — 按住拖拽弹簧跟随（惊慌表情），松手按甩速抛飞、落地弹跳（闭眼尖叫），拖动方向决定转身
- 📎 **贴边隐藏** — 靠近屏幕边缘自动吸附只露 30px，鼠标靠近平滑探出
- 💬 **流式聊天** — 支持 DeepSeek 及任意 OpenAI 兼容 API，对话持久化，透明无边框悬浮气泡窗口
- 🗑️ **垃圾桶** — 拖放文件到桌宠 → 确认后移入回收站（可记住偏好不再提示）
- 🚀 **开机自启** — Windows 注册表 Run 键，打包后指向 exe 自身
- 🎨 **精灵图素材** — SDXL + IP-Adapter 生成的真实 Q 版底图（9 状态 × 8 帧），无素材时自动回退到代码绘制占位图

## 运行

```powershell
pip install PySide6 openai send2trash
python main.py
```

打包为单文件 exe：

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name DeepSeaPet main.py
```

依赖只有 3 个 pip 包：`PySide6`、`openai`、`send2trash`，其余全是标准库。

## 技术栈

| 层 | 技术 |
|---|---|
| UI | PySide6（透明无边框置顶窗口，QPainter 程序化变换渲染） |
| AI 对话 | OpenAI SDK（兼容 DeepSeek / 自定义 API，流式输出） |
| 精灵图 | SDXL img2img + IP-Adapter 身份锁定（AutoDL GPU，`autodl_tools/`） |
| 配置 | JSON（%APPDATA%/DeepSeaPet/） |
| 打包 | PyInstaller → 单文件 exe |

## 动画机制

`AnimationController` 管理状态机（idle/walk/hide/peek/sleep/happy/lying/held/flying），每状态只从 `module_5_assets/sprites/{state}_*.png` 加载帧 0 作静态底图。动作交给程序化变换而非逐帧序列：`PetWindow._render` 用 QPainter 叠加**镜像 + 倾斜 + 缩放 + 位移**，60fps 物理 timer 常驻驱动。

- **idle** 呼吸：`sin(t*1.5)*0.02` Y 向缩放
- **happy** 双击跳跃：`-40*sin(π*t/2)` 抛物线
- **held/flying** 拎起甩物理：弹簧-阻尼跟随（K=200/C=28），松手后重力落地弹跳（G=2000/REST=0.55），甩速方向决定转身
- **hide/peek** 贴边：弹簧平滑逼近目标位置

## 结构

```
deepseek桌宠/
├── main.py                 # 入口 + 托盘 + App 生命周期
├── module_1_core/          # 桌宠窗口 + 动画控制器（程序化动画核心）
├── module_2_api/           # API 客户端 + 配置管理
├── module_3_chat/          # 聊天窗口 + 对话存储 + 打招呼
├── module_4_system/        # 垃圾桶 + 开机自启
├── module_5_assets/        # 精灵图素材（9 状态 × 8 帧 PNG）
└── autodl_tools/           # AutoDL 远程精灵图生成辅助脚本
```

## 贡献者

| 角色 | 贡献 |
|---|---|
| 🧑‍💻 **silicon-sbt** | 项目发起、架构设计 |
| 🤖 **DeepSeek** | AI 代码生成 & 精灵图创作 |
| 🤖 **Claude Code** | AI 编程助手，全程参与开发 |

> 本项目由人类与 AI 协作完成 ✨

## 许可

开发中，暂未确定。
