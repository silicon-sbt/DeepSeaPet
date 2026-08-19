# DEVLOG - DeepSeek Harness 交接后工作记录

> 本文件记录 HANDOFF_walk_video.md 交接给 DeepSeek Harness 之后的全部工作：每一步干了什么、思路、踩过的坑。
> 交接前的事（即梦 API 用法、素材生成管线）见 HANDOFF_walk_video.md（已 gitignore，含 API key，勿提交）。
> 本文件不含任何密钥，可随仓库提交。

---

## 1. 工作时间线（按顺序）

### 1.1 双击跳舞时长 4s 改 10s
- **需求**：用户"给跳舞的循环时间调长一点"
- **做法**：module_1_core/pet_window.py 的 mouseDoubleClickEvent 里 QTimer.singleShot(4000 -> 10000) 回 idle
- **思路**：dance 是双击触发的独立状态，时长就是"跳多久自动回 idle"

### 1.2 待机图"出问题"排查（最大坑，多轮才定位）
- **现象**：用户"待机的图出问题了"，截图显示角色异常
- **第一轮**：发现 idle_00 foot_y=447 与其他帧（423/424）不一致 -> 判定是混入的旧图 -> 用 idle_01 内容替换（先备份）
- **第二轮**：用户又说"待机显示出来的只有尾巴" -> 各种像素对比全部不匹配（素材都完整）-> 发现用户桌宠贴边隐藏（窗口 L 约屏幕右缘-30，snap_to_edge 切到 peek 状态），peek_00 躲藏图显示怪异像"只有尾巴"
  - 修复：贴边隐藏改用 idle（set_state("peek") -> set_state("idle")），PEEK_PX 30->60
- **第三轮**：用户澄清"正常待机就只有尾巴" -> 用 PrintWindow API 抓窗口内容 -> 抓到完整角色！但用户仍看到"只有尾巴" -> 结论：PrintWindow 抓取 != 屏幕实际合成（Qt layered window 的 DWM 合成问题）
- **换图**：用即梦原始帧（sprites_video_dl/idle/idle_00.png，768x768）重新 flood-fill 抠图 -> 新 idle_00
- **教训**：1) 用户看到的"显示异常"不一定是素材问题，可能是贴边隐藏/peek 状态/DWM 合成；2) 诊断必须抓"用户实际看到的"，但 CopyFromScreen 抓不到 Qt 透明窗口（layered window），PrintWindow 抓的是窗口内容（可能与屏幕合成不一致）

### 1.3 统一精灵图大小（两轮理解）
- **用户第一轮**："统一各个精灵图的大小" -> 我统一了站立状态（idle/happy/walk/dance/held/flying）到 490 高、脚底 499、居中（hide/peek/sleep/lying 保留姿势特征）
- **用户第二轮**："不是动作统一，是角色统一、画风统一……除了跳舞走路待机其他得重做"
- **理解**：用户要的是角色形象/画风统一（所有状态同一个角色的同一种画风），不是尺寸统一
  - idle/walk/dance = 即梦新画风（同一角色）
  - happy/hide/peek/sleep/lying/held/flying = 旧 SDXL 素材（画风/角色不一致）
- **待办**：用即梦重新生成其他 7 状态（需用户充值，约 5 元/状态，共约 35 元），目前余额不足

### 1.4 绿幕残留处理（角色内部的绿，不是边缘残留）
- **现象**：用户红色标注"角色中下部都是绿幕"
- **像素分析**：绿色（g>r+40 且 g>b+40）全在角色 alpha=255 内部（x131-403, y177-402，2017px），不在边缘/背景
- **关键判断**：绿色区域周围是深蓝灰（68/90/115），区域内有亮蓝（111/167/220）-> 蓝裙子被绿幕色污染（即梦生成时绿幕背景色混入裙子蓝色），不是抠图残留
- **处理历程**：去绿（G'=(R+B)/2，偏灰）-> 用户不要灰 -> 透明化（alpha=0）-> 用户认可"那不是洞，是没处理干净的绿幕"
- **教训**：绿幕可能混在角色主体内部（alpha 255 的裙子颜色被污染），flood-fill/边缘检测发现不了；要查颜色通道差（g > r+40）而非边缘

### 1.5 待机朝向"跳反"
- **需求**：用户"在右侧朝左、左侧朝右"（始终面向屏幕中心，不要随机）
- **做法**：新增 _facing_toward_center()（按窗口中心 vs 屏幕中心决定 facing），walk 与 idle 都用它
- **用户反馈"跳反"** -> 像素分析发现 idle_00 素材朝左（头偏左），而 walk/dance 朝右 -> facing 逻辑按"朝右"设计，idle 镜像后反了
- **修复**：flip idle_00 -> 朝右统一
- **教训**：所有素材朝向必须统一（facing>0=朝右），否则镜像逻辑会跳反；判断朝向用"上半身质心 vs 身体质心"

### 1.6 自动启动桌宠
- **需求**："每次自动启动桌宠"
- **两层实现**：
  1. 开机自启：AutoStartManager.enable() 写注册表 HKCU Run 键 + config auto_start: true
  2. 改完代码自动重启桌宠：杀旧 pythonw 进程 -> Start-Process pythonw main.py（无控制台窗口）
- **经验**：桌宠用 pythonw 启动无黑框；Start-Process 不阻塞

### 1.7 上传 GitHub + 更新 README
- **安全检查**：HANDOFF 已 gitignore；grep 3ezVS 只命中 HANDOFF；imeng_walk.py 纯 env-only
- **README**：9->10 状态、加双击跳舞/散步朝向/即梦生成/统一尺寸说明
- **推送**：GFW 下 443 端口 SSH + 小批量（21 批素材，每批 <=1MB），全部一次成功
  - 命令：git -c core.sshCommand="ssh -p 443 -o HostName=ssh.github.com" push

### 1.8 代码审查（修复双击 bug + 朝向/性能优化）
- **审查范围**：pet_window.py（633 行）+ main.py（188 行）通读
- **修复的高优先级 bug**：
  1. **双击跳舞会先打开聊天窗口**——双击序列中第一次 mouseReleaseEvent 触发 clicked.emit()（打开聊天），然后才进 mouseDoubleClickEvent 跳舞。修复：单击改为延迟判定（等 doubleClickInterval() 窗口期），双击时取消挂起单击
  2. **多次双击跳舞 timer 堆叠**——每次双击都 singleShot(10000, 回idle)，多个 timer 竞争提前打断舞蹈。修复：记录 _dance_until 截止时间，timer 到期校验
  3. **待机朝向每帧查询屏幕（性能）**——_step_idle 60fps 每帧 screenAt。修复：降频
- **报告未改**：托盘"隐藏"后无法恢复（无显示入口）；_settle 朝向重置跳变；魔法数字可提常量

### 1.9 朝向判定延迟优化（松手立即转身）
- **需求**：用户觉得"松手后才做方向判定"奇怪，要求延迟缩短到看不出来
- **修改**：
  1. 待机朝向更新 0.5s -> 0.1s（肉眼无感，screenAt 每 0.1s 一次）
  2. 松手停住时立即 _facing_toward_center()（不等 tick）
  3. _settle 落地时立即转身（替代固定 _facing = 1）
- **踩坑补充**：拖拽松手后方向判定有两个时机——拖拽中跟鼠标方向、待机按位置朝中心，中间可能跳变；应在松手瞬间就按位置定朝向，避免等待

---

## 2. 踩坑记录（按重要性）

| # | 坑 | 现象 | 原因 | 教训 |
|---|-----|------|------|------|
| 1 | PrintWindow 不等于屏幕显示 | PrintWindow 抓到完整角色，用户看到"只有尾巴" | Qt 透明窗口（WS_EX_LAYERED）的 DWM 合成与窗口内容可能不一致 | 诊断显示问题要看用户实际所见；CopyFromScreen 抓不到 layered window，PrintWindow 抓内容（可能与屏幕合成不同） |
| 2 | 贴边隐藏 = peek 状态 | "待机显示只有尾巴" | 桌宠贴边时 snap_to_edge 切 peek，peek_00 躲藏图怪异 | 用户说的"待机"可能是贴边隐藏状态；查窗口位置是否在屏幕边缘外 |
| 3 | 素材朝向不统一 | 待机朝向"跳反" | idle_00 素材朝左，walk/dance 朝右 | 所有素材统一朝向（facing>0=朝右）；flip 前先验证朝向 |
| 4 | 绿幕混在角色内部 | 角色裙子有绿色 | 即梦生成时绿幕背景色混入裙子蓝色（alpha 仍 255） | 检测绿色用颜色通道差（g>r+40），不能只查边缘/背景 |
| 5 | PowerShell 中文/引号坑 | 中文路径乱码、变量吞、语法错 | GBK 编码 + PS 变量解析 | ps1 文件避免中文路径；变量用 ${} 界定；&& PS5.1 不支持 |
| 6 | shutil.copy2 保留 mtime | 替换文件后 mtime 不变 | copy2 复制元数据 | 判断"文件何时被改"要用内容对比，别信 mtime |
| 7 | SetWindowPos 移动后桌宠自己接管 | 窗口位置又变了 | 桌宠内部 _px 未同步，物理 timer 会 move 回去 | 移动桌宠窗口要用它自己的机制（config 位置 + 重启） |
| 8 | 进程不重启 = 旧素材 | 改了素材用户还看到旧的 | QPixmap 在进程启动时加载到内存 | 改素材后必须重启桌宠（已养成自动重启习惯） |
## 2. DeepSeek Harness 会话（2026-08，余额云朵 + 聊天 UI 重做 + 交互重排）

### 2.1 余额云朵（理念来自 DeepSeek-Balance-Whale-Widget）
- **需求**：把 MeteorNOX/DeepSeek-Balance-Whale-Widget 的"显示余额"理念搬过来，做成云朵气泡，显示在角色上方
- **实现**：
  1. `ApiClient.get_balance()`：urllib 直调 `GET /user/balance`（无新依赖，仅 DeepSeek；401→AuthError、超时→NetworkError、自定义 API→None）
  2. `BalanceBubble`：独立透明悬浮窗（Tool|Frameless|StaysOnTop），云朵 = QPainterPath 5 圆并集 + 底部小尾巴，显示在桌宠正上方（place_above，顶部放不下自动落下+尾巴翻转）
  3. 点击刷新、60s 自动刷新、金额滚动动画（QTimer 20ms 缓动）、启动 1.5s 后台预取缓存秒显、moveEvent 跟随、贴边隐藏自动收起
- **踩坑（重要）**：
  1. `QPainterPath` 默认 OddEvenFill → 多圆并集的重叠区被镂空成洞（2868px 空洞）→ 必须 `setFillRule(Qt.WindingFill)`
  2. 透明顶层窗口挂 `QGraphicsDropShadowEffect` → 阴影外扩超出窗口边界 → Windows `UpdateLayeredWindowIndirect` 持续报"参数错误" → 阴影改 paintEvent 内手绘（clip 在云朵内）
  3. 多圆并集时 QPainter 抗锯齿会在圆交界处留单像素缝隙（不可见，可忽略）

### 2.2 聊天窗口 UI 重做
- **需求**：旧聊天 UI"太丑"，要求重做成好看的卡片式，可拖动可自由调整大小
- **实现**：深海主题卡片（手绘 7 层阴影+渐变背景）、header（圆形头像+名字+在线点+32px 关闭钮）、尾巴气泡（四角独立圆角 QPainterPath + 三角尾巴 + 渐变 + 圆形头像）、TypingBubble 三点弹跳打字指示器（首 token 自动替换）、胶囊输入区、app 级 eventFilter 统一接管拖拽/边缘 resize（startSystemResize）/光标反馈
- **视觉自审**：本地 Ollama qwen2.5vl:7b 多轮审查（deepseek-img skill 同款管线），最终 8-9 分

### 2.3 交互重排（单击/双击/三击）
- 单击 = 余额云朵（toggle）、双击 = 聊天窗、三击 = 跳舞（原双击跳舞、单击聊天）
- **三击自研判定**：750ms 内三次独立点击即跳舞，不依赖 Qt 双击事件（Qt 判定慢时三击会退化成单击）；`_click_gen` 代际作废旧确认定时；`_start_dance` 先强制 `_mode="idle"` 放行 set_state 门控（贴边滑行/散步中也能跳舞）
- **坑**：Qt 定时器可能提前几毫秒触发，严格 `>= TRIPLE_WINDOW` 边界会漏判（双击开聊天失效）→ 判定留 20ms 余量 + 定时延后 50ms

### 2.4 其他
- 余额/聊天回归测试：`_pet_balance_test.py`（32 项）+ `_regression_test.py`（35 项），offscreen 离屏渲染 + qwen2.5vl 视觉自审
- 打包：PyInstaller --onefile --windowed

| 9 | GFW git push | SSH 22 端口大流量被重置 | GFW 阻断 | 443 端口 SSH + 每批 <=1MB commit 逐批 push |
| 10 | llava 视觉判断不可靠 | 尾巴/绿幕多次误判 | llava:7b 对细节理解差 | 关键判断用像素分析（颜色/位置/alpha），llava 只做辅助 |

---

## 3. 关键决策备忘

- **待机图**：用即梦原始帧（sprites_video_dl/idle/idle_00.png）flood-fill 抠图（白+绿双阈值），对齐 490/499/居中，绿色（裙子绿幕混色）透明化
- **精灵图规格**：所有状态统一 490px 高、脚底 y=499、水平居中（hide_07/peek_02 因角色宽用 contain 472-477）
- **朝向逻辑**：_facing_toward_center() - 屏幕右半朝左(-1)、左半朝右(1)；walk 和 idle 都用
- **贴边隐藏**：显示 idle（不用 peek），露出 60px
- **跳舞**：双击触发，10s 自动回 idle，8 帧即梦舞蹈循环

## 4. 当前待办

- [ ] **重做其他 7 状态画风**（happy/hide/peek/sleep/lying/held/flying）：需即梦余额（约 35 元），充值后以 idle 锚点为底 I2V 生成
- [ ] idle_01-07 右上区域也有绿色（2000+px，疑似同款绿幕混色）-- 桌宠不显示可暂缓
- [x] 用户最终确认：待机朝向、绿幕透明化效果（已完成，见 1.5/1.4/1.9）

## 5. 常用命令速查

- 重启桌宠：Get-Process pythonw | Stop-Process -Force; Start-Process "C:\Users\A\AppData\Local\Programs\Python\Python314\pythonw.exe" main.py -WorkingDirectory "E:\code\deepseek的桌宠"
- GFW push：git -c core.sshCommand="ssh -p 443 -o HostName=ssh.github.com" push origin master
