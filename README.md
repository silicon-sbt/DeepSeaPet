# DeepSeaPet — 深海鲸鱼娘桌宠

用 PySide6 做的桌面宠物：一只傲娇的深海鲸鱼娘（DeepSeek 的娘化形象，蓝色长发 + 鲸鱼尾巴 + 女仆装）。会陪你聊天、在桌面散步、贴边藏起来、被拎起来甩飞、帮你扔垃圾。

## 功能

- **桌宠本体**：10 种动画状态（待机 / 行走 / 跳舞 / 隐藏 / 探头 / 睡觉 / 开心 / 趴姿 / 拎起 / 飞落），动作由物理驱动（60fps 弹簧阻尼 + 重力 + 镜像/倾斜/缩放），精灵图来自即梦 I2V 和 SDXL 生成
- **交互**：
  - **单击** — 头顶弹出余额云朵：DeepSeek 账户余额（¥ 大字、点击刷新、60 秒自动刷新、金额滚动动画），贴边隐藏时云朵自动收起；启动时后台预取余额，单击即显示
  - **双击** — 打开聊天窗：卡片式悬浮窗（可拖动、可拖边自由调整大小），流式对话，气泡带尾巴和头像
  - **三击** — 跳舞（即梦生成的 8 帧舞蹈循环，跳 10 秒自动回待机）
  - **拖拽** — 拎起甩飞：弹簧跟随 + 松手按甩速抛飞 + 落地弹跳
- **贴边隐藏**：靠近屏幕边缘自动吸附只露 60px，鼠标靠近平滑探出
- **垃圾桶**：把文件拖到桌宠身上，确认后进回收站（可记住偏好）
- **开机自启**：写 Windows 注册表 Run 键，打包后指向 exe 自身
- **聊天**：支持 DeepSeek 和任意 OpenAI 兼容 API，对话持久化存本地

## 运行

```powershell
pip install PySide6 openai send2trash
python main.py
```

打包成单文件 exe：

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name DeepSeaPet --add-data "module_5_assets;module_5_assets" main.py
```

## 目录

```
main.py                 # 入口 + 托盘 + 应用生命周期
module_1_core/          # 桌宠窗口 + 动画控制器（程序化动画 + 余额云朵）
module_2_api/           # API 客户端（对话 / 余额查询）+ 配置
module_3_chat/          # 聊天窗口 + 对话存储 + 打招呼
module_4_system/        # 垃圾桶 + 开机自启
module_5_assets/        # 精灵图素材（10 状态 × 8 帧 PNG）
autodl_tools/           # 精灵图远程生成脚本（即梦 I2V / SDXL）
```

## 致谢

余额云朵的灵感来自 [DeepSeek-Balance-Whale-Widget](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget)（MeteorNOX 的 DSH 小鲸鱼余额挂件：盯着 DeepSeek 账户余额的小鲸鱼，¥ 大字金额、点击刷新、金额滚动动画——这些理念都搬了过来）。

## 许可

开发中，暂未确定。
