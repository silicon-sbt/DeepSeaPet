# 🐋 深海鲸鱼娘 — DeepSeaPet

> ⚠️ **还在开发中，请勿使用！** 本项目尚未完成，API 接口和行为随时可能改变。

一只傲娇的深海鲸鱼娘桌面宠物，基于 PySide6。她是 DeepSeek 的娘化形象 —— 蓝色渐变长发、鲸鱼尾巴头饰、深蓝女仆装。会陪你聊天、在桌面散步、贴边隐藏、帮你丢垃圾。

## 特性

- 🎭 **帧动画桌宠** — 7 种状态（待机/行走/隐藏/探头/睡觉/开心/趴姿），8fps 精灵图动画
- 💬 **流式聊天** — 支持 DeepSeek 及任意 OpenAI 兼容 API，对话持久化
- 📎 **贴边隐藏** — 靠近屏幕边缘自动吸附隐藏，鼠标靠近展开
- 🗑️ **垃圾桶** — 拖放文件到桌宠 → 确认后移入回收站
- 🚀 **开机自启** — Windows 注册表 Run 键
- 🎨 **Q 版占位图** — 无素材时代码绘制 chibi 鲸鱼娘，开箱即用

## 运行

```powershell
pip install PySide6 openai send2trash
python main.py
```

## 技术栈

| 层 | 技术 |
|---|---|
| UI | PySide6（透明无边框置顶窗口） |
| AI 对话 | OpenAI SDK（兼容 DeepSeek / 自定义 API） |
| 精灵图 | Wan2.1 I2V 视频模型生成（AutoDL A100） |
| 配置 | JSON（%APPDATA%/DeepSeaPet/） |
| 打包 | PyInstaller → 单文件 exe |

## 结构

```
deepseek桌宠/
├── main.py                 # 入口 + 托盘 + App 生命周期
├── module_1_core/          # 桌宠窗口 + 动画控制器
├── module_2_api/           # API 客户端 + 配置管理
├── module_3_chat/          # 聊天窗口 + 对话存储 + 打招呼
├── module_4_system/        # 垃圾桶 + 开机自启
├── module_5_assets/        # 精灵图素材（7×8 帧 PNG）
└── autodl_tools/           # AutoDL 远程精灵图生成脚本
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
