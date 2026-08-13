# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

本目录是 AutoDL 精灵图生成的质量分析与收尾工具集。**主操作规范（连接、下载、组装、生成工作流、AutoDL 坑）在上层 `../CLAUDE.md`，此处只写上层未覆盖的增量**。上层是权威，冲突以它为准。

## 数据目录映射

| 路径（相对本目录） | 内容 |
|------|------|
| `sprites_video_dl/{state}/{state}_00..07.png` | AutoDL 下载的原始生成帧（8 帧/状态，每张是 **2×2 四格拼图**，每格 512） |
| `base_refs/{state}_00.png` | 豆包基准图（7 状态）；只有 idle 是白底单角色 |
| `sprites_new/` | `_eat_shit.py` 输出：切最佳格 + 色度键抠图 → 512×512 透明帧（7 状态 × 8 帧 = 56 帧） |
| `../module_5_assets/sprites/` | 桌宠实际加载的帧（已用 `sprites_new/` 覆盖） |
| `../module_5_assets/sprites_backup/` | 原四格拼图备份（要回滚就拷这里） |
| `_ref_lightx2v/` | LightX2V 官方仓库的 git clone（参考源码 + docs/skills），**不是本项目代码，别在里面改东西** |

## 核心病根：四格拼图（本会话血泪结论）

- 豆包生成的基准图/精灵图全是 **2×2 四格拼图**（4 个不同角色方案）。
- Wan I2V 把**整张拼图当一张图**做视频 → 四格一起动、互相干扰 → 结果猎奇。
- **只有 idle 是豆包的白底单角色图**（`_prep_base.py` 硬编码只处理 `idle_00`），其他 6 状态都是绿幕多角色拼图。
- 「生成帧 vs 基准图色差 ~10/255」是假象——I2V 物理约束首帧必须等于输入图；真崩坏在**后续帧**（happy 帧1 就 60-72/255，walk 38-50）。
- 判断质量问题别只看首帧，要看帧间色差。

## 质量分析工具链（本会话新增，上层表格没有）

| 脚本 | 用途 |
|------|------|
| `_ascii_view.py [state...]` | ASCII 渲染基准图 vs 生成首帧，无视觉环境"看"图 |
| `_split_sprites.py` | 量化筛选每状态四格中最健康的一格（角色占比/绿幕/居中/帧间色差） |
| `_eat_shit.py` | **切最佳格 + 色度键抠图 → 透明精灵帧**（`BEST_CELL` 每状态选格，输出 `sprites_new/`） |
| `_vlm_look.py <img> [prompt] [model]` | Ollama 本地视觉模型描述图片，弥补无视觉输入 |

## 色度键抠图（纯 numpy，无需 rembg）

```python
green = (g > r + 40) & (g > b + 40)   # 绿幕
white = (r > 225) & (g > 225) & (b > 225)  # 白底
bg = green | white; alpha = np.where(bg, 0, 255)
```

## 本地视觉模型（Ollama）

- 模型 `llava:7b` 装在 **E 盘** `../ollama_models`（别下 C 盘），`OLLAMA_MODELS` 用户级环境变量指向它。
- HTTP API：`POST localhost:11434/api/generate`，`images` 字段 base64，`stream: false`。`_vlm_look.py` 封装好了，零依赖。
- **迁移模型目录后必须杀干净 ollama/llama-server 进程再重启服务**，否则残留进程仍读旧路径（list 为空即此坑）。

## 无头测试桌宠素材

`_test_animation.py` 需要 `QT_QPA_PLATFORM=offscreen` + `QApplication`（否则 QPixmap 崩溃），且 `sys.path` 硬编码了 `E:\code\deepseek的桌宠`。验证加载：每状态应 8 帧、0 空帧、512×512。
