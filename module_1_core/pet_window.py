"""桌宠窗口 — 透明无边框置顶、拖拽、贴边隐藏、文件拖放、余额气泡"""
import sys
import time
import math
import random
import threading
from collections import deque
from PySide6.QtWidgets import QWidget, QLabel, QMenu, QApplication, QGraphicsDropShadowEffect, QVBoxLayout
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QPointF, QRectF
from PySide6.QtGui import (QPixmap, QPainter, QMouseEvent, QDropEvent,
                           QDragEnterEvent, QCursor, QColor, QPen, QBrush, QLinearGradient,
                           QPolygonF, QPainterPath)

from module_1_core.animation import (AnimationController, PetState,
                                       make_placeholder_frames, SPRITE_DIR)
from module_2_api.config_manager import ConfigManager
from module_2_api.api_client import ApiClient, ApiConfigError, ApiAuthError, ApiNetworkError


# 余额预取缓存：启动时后台查一次，单击气泡时秒显（无需等网络）
_balance_cache = {"ts": 0.0, "balance": None, "currency": None}


def _prefetch_balance(config):
    """后台预取 DeepSeek 余额到模块缓存（不阻塞启动，失败静默）"""
    def work():
        try:
            result = ApiClient(config).get_balance()
            if result is not None:
                _balance_cache["balance"], _balance_cache["currency"] = result
                _balance_cache["ts"] = time.monotonic()
        except Exception:
            pass
    threading.Thread(target=work, daemon=True).start()


class BalanceBubble(QWidget):
    """余额气泡 — 云朵形悬浮气泡，显示在桌宠正上方（尾巴指向角色）。

    蓬松云朵轮廓（多圆并集渐变填充）+ 底部小尾巴；点击刷新、60s 自动刷新、
    金额滚动动画。理念致敬 MeteorNOX/DeepSeek-Balance-Whale-Widget。
    """

    _result = Signal(object)  # (ok, balance, currency, message)

    def __init__(self, fetch_balance, parent=None):
        super().__init__(parent)
        self._fetch = fetch_balance
        self._tail_dir = "down"     # "down" 云朵在角色上方（尾巴朝下）| "up"
        self._balance = None
        self._currency = "CNY"
        self._shown = None          # 当前显示金额（动画插值目标）
        self._status = "loading"    # loading | ok | error | unsupported
        self._message = ""
        self._anim_phase = 0.0
        self._anim_from = 0.0
        self._anim_to = 0.0
        self.setFixedSize(340, 200)
        self.setCursor(Qt.PointingHandCursor)
        # 独立悬浮窗（跟随桌宠窗口移动/置顶）
        # 注意：透明顶层窗口不能挂 QGraphicsDropShadowEffect —— 阴影外扩会超出
        # 窗口边界，导致 Windows UpdateLayeredWindowIndirect 报错（参数错误）。
        # 阴影改为 paintEvent 内手绘（见 paintEvent）。
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._label = QLabel("🐋 DeepSeek 余额", self)
        self._label.setStyleSheet("color: #536BA9; font-size: 14px; font-weight: 600; background: transparent;")
        self._amount = QLabel("…", self)
        self._amount.setStyleSheet("color: #2C3E50; font-size: 34px; font-weight: 800; background: transparent;")
        self._amount.setAlignment(Qt.AlignCenter)
        self._hint = QLabel("点击刷新 · 60s 自动", self)
        self._hint.setStyleSheet("color: #9FB0D9; font-size: 12px; background: transparent;")
        self._hint.setAlignment(Qt.AlignCenter)

        # 顶部留白 ≥ 顶部圆上沿：保证三行文字完全被云朵主体包裹
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 40, 36, 42)
        lay.setSpacing(3)
        lay.addWidget(self._label, 0, Qt.AlignCenter)
        lay.addWidget(self._amount)
        lay.addWidget(self._hint)

        self._result.connect(self._on_result)
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(60000)
        self._auto_timer.timeout.connect(lambda: self.refresh())
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(20)
        self._anim_timer.timeout.connect(self._anim_step)

    # ── 云朵轮廓（多圆并集 + 尾巴）──

    def _cloud_path(self, w, h):
        path = QPainterPath()
        # WindingFill：多个圆并集的重叠区（绕数 2）必须填充；
        # 默认 OddEvenFill 会把重叠区当偶数镂空 → 云朵内部出现孔洞
        path.setFillRule(Qt.WindingFill)
        cx = w * 0.5
        if self._tail_dir == "down":
            # 云朵主体 + 底部小尾巴（指向下方角色）
            circles = [
                (cx, h * 0.52, h * 0.30),
                (cx - w * 0.21, h * 0.56, h * 0.22),
                (cx + w * 0.21, h * 0.56, h * 0.22),
                (cx - w * 0.10, h * 0.34, h * 0.21),
                (cx + w * 0.10, h * 0.34, h * 0.21),
            ]
            tail = [(cx - 8, h * 0.68), (cx + 8, h * 0.68), (cx, h * 0.90)]
        else:
            # 翻转：云朵在角色下方，尾巴朝上
            circles = [
                (cx, h * 0.44, h * 0.30),
                (cx - w * 0.21, h * 0.40, h * 0.22),
                (cx + w * 0.21, h * 0.40, h * 0.22),
                (cx - w * 0.10, h * 0.60, h * 0.19),
                (cx + w * 0.10, h * 0.60, h * 0.19),
            ]
            tail = [(cx - 7, h * 0.26), (cx + 7, h * 0.26), (cx, h * 0.06)]
        for (x, y, r) in circles:
            path.addEllipse(QPointF(x, y), r, r)
        path.addPolygon(QPolygonF([QPointF(px, py) for px, py in tail]))
        return path

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        path = self._cloud_path(w, h)
        # 云朵本体（白→浅蓝渐变）
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor("#FFFFFF"))
        grad.setColorAt(1, QColor("#EAF3FF"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawPath(path)
        # 底部内侧柔和阴影：clip 在云朵形状内绘制渐变，
        # 不产生任何云朵外的像素 → 透明窗口无脏边/抠穿
        p.save()
        p.setClipPath(path)
        inner = QLinearGradient(0, h * 0.60, 0, h)
        inner.setColorAt(0, QColor(20, 40, 90, 0))
        inner.setColorAt(1, QColor(20, 40, 90, 40))
        p.setBrush(QBrush(inner))
        p.drawRect(0, 0, w, h)
        p.restore()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.refresh(manual=True)

    def place_above(self, pet_rect):
        """定位到桌宠正上方（水平居中，尾巴朝下指向角色）；顶部空间不足时放下方"""
        w, h = self.width(), self.height()
        x = pet_rect.center().x() - w // 2
        y = pet_rect.top() - h - 18
        self._tail_dir = "down"
        screen = QApplication.screenAt(pet_rect.center())
        if screen is not None:
            sg = screen.availableGeometry()
            if y < sg.top() + 4:
                # 上方放不下 → 桌宠下方，尾巴朝上
                y = pet_rect.bottom() + 18
                self._tail_dir = "up"
            x = max(sg.left() + 4, min(x, sg.right() - w - 4))
            y = max(sg.top() + 4, min(y, sg.bottom() - h - 4))
        self.move(x, y)
        self.update()

    # ── 状态与刷新 ──

    def refresh(self, manual=False):
        cached = _balance_cache
        if (cached["ts"] and time.monotonic() - cached["ts"] < 60
                and cached["balance"] is not None):
            # 命中启动预取缓存 → 立即显示余额（随后台刷新覆盖）
            self._on_result((True, cached["balance"], cached["currency"], ""))
        elif manual or self._balance is None:
            if self._status != "error":
                self._status = "loading"
            self._render()
        self._auto_timer.start()
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            result = self._fetch()
            if result is None:
                self._result.emit((False, None, None, "仅 DeepSeek 支持余额查询"))
            else:
                balance, currency = result
                self._result.emit((True, balance, currency, ""))
        except ApiConfigError as e:
            self._result.emit((False, None, None, str(e)))
        except ApiAuthError:
            self._result.emit((False, None, None, "API Key 无效"))
        except ApiNetworkError as e:
            self._result.emit((False, None, None, str(e)))
        except Exception:
            self._result.emit((False, None, None, "查询失败"))

    def _on_result(self, payload):
        ok, balance, currency, message = payload
        if not ok:
            self._status = "unsupported" if "仅 DeepSeek" in message else "error"
            self._message = message
            self._render()
            return
        new_bal = float(balance)
        changed = self._balance is not None and abs(new_bal - self._balance) > 1e-9
        self._balance = new_bal
        self._currency = currency or "CNY"
        self._status = "ok"
        if changed and self._shown is not None:
            self._start_anim(self._shown, new_bal)
        else:
            self._shown = new_bal
            self._render()
        self._message = ""

    def _start_anim(self, fr, to):
        self._anim_from = fr
        self._anim_to = to
        self._anim_phase = 0.0
        self._anim_timer.start()

    def _anim_step(self):
        self._anim_phase += 0.02
        t = min(1.0, self._anim_phase / 0.7)  # 700ms
        eased = 1 - (1 - t) ** 3
        val = self._anim_from + (self._anim_to - self._anim_from) * eased
        self._amount.setText(self._fmt(val))
        if t >= 1.0:
            self._anim_timer.stop()
            self._shown = self._anim_to
            self._render()

    def _fmt(self, num):
        return f"¥ {num:,.2f}" if self._currency == "CNY" else f"{num:,.2f} {self._currency}"

    def _render(self):
        if self._status == "loading":
            self._amount.setText("…")
            self._hint.setText("加载中…")
        elif self._status == "error":
            self._amount.setText(self._fmt(self._balance) if self._balance is not None else "--")
            self._hint.setText((self._message or "获取失败")[:12] + " · 点击重试")
        elif self._status == "unsupported":
            self._amount.setText("--")
            self._hint.setText(self._message[:14])
        else:
            if self._shown is None:
                self._shown = self._balance
            self._amount.setText(self._fmt(self._shown))
            self._hint.setText("点击刷新 · 60s 自动")


class PetWindow(QWidget):
    """主桌宠窗口"""
    clicked = Signal()
    chat_requested = Signal()
    files_dropped = Signal(list)

    # 宠物本体大小
    PET_SIZE = 256
    # 贴边时露出像素
    PEEK_PX = 60
    # 边缘吸附阈值
    EDGE_THRESHOLD = 50
    # 单击判定 — 移动小于此像素算点击
    CLICK_THRESHOLD = 5
    # 单击确认延迟（ms）：在系统双击间隔内取消，保证双击/三击不误弹云朵
    CLICK_CONFIRM_MS = 300
    # 三击窗口（s）：双击后此时间内再击 = 跳舞（覆盖慢速连点）
    TRIPLE_WINDOW = 0.45
    # 自研三击：750ms 内三次独立点击 = 跳舞（不依赖 Qt 双击判定）
    TRIPLE_SPAN = 0.75

    def __init__(self, config: ConfigManager = None):
        super().__init__()
        self.config = config or ConfigManager.instance()
        self._drag_start = None
        self._is_dragging = False
        self._hidden_at_edge = False
        self._snapped_edge = None  # "left" | "right" | "top" | None
        self._bubble = None

        # 拎起来甩 — 物理状态
        self._mode = "idle"            # idle | grabbed | flying | slide | walk
        self._px = 0.0                 # 浮点窗口位置
        self._py = 0.0
        self._vx = 0.0
        self._vy = 0.0
        self._target_x = 0.0           # 滑动目标窗口坐标（hide/peek 平滑过渡）
        self._target_y = 0.0
        self._tilt_angle = 0.0         # 倾斜角（度）
        self._tilt_v = 0.0
        self._scale_x = 1.0            # 呼吸/跳跃 squash
        self._scale_y = 1.0
        self._bob_x = 0.0              # 跳跃位移
        self._bob_y = 0.0
        self._facing = 1               # 1=朝右，-1=镜像朝左（往左甩时转身）
        self._anim_t = 0.0             # 动画相位（秒），set_state 时重置
        self._grab_offset = QPointF()  # 鼠标相对窗口的偏移
        self._mouse = QPointF()        # 鼠标全局坐标
        self._samples = deque(maxlen=6)  # (t, x, y) 甩速采样
        self._cur_frame = None         # 当前动画帧（未倾斜）
        self._tilted = QPixmap(self.PET_SIZE, self.PET_SIZE)  # 倾斜渲染缓冲
        self._screen_geo = None        # 拎起时缓存的屏幕几何
        self._last_tick = time.monotonic()
        self._last_mouse_x = 0.0       # 上一帧鼠标 x（转身用）
        self._drag_dx = 0.0            # 鼠标位移累积（指数平滑，慢拖也稳定翻转）
        self._release_protect_until = 0.0  # 拖拽松手后的贴边冷却截止时间（防误贴边）
        self._click_pending = False     # 待确认的单击（延迟判定，双击时取消）
        self._dance_until = 0.0         # 跳舞结束截止时间（防多次双击 timer 堆叠）
        self._double_at = 0.0           # 双击时刻（三击窗口：双击后 TRIPLE_MS 内再击 = 跳舞）
        self._dbl_guard_until = 0.0     # 双击/三击保护期：期间 release 不产生独立单击
        self._click_times = []          # 最近单击时间戳（自研三击判定，不依赖 Qt 双击事件）
        self._click_gen = 0             # 单击代际：三击/新单击作废旧确认定时
        self._balance_bubble = None     # 余额气泡（懒创建）

        # 闲置散步 — walk 状态触发
        self._walk_ready_at = time.monotonic() + random.uniform(25, 60)  # 闲置多久后开始散步
        self._walk_target_x = 0.0      # 散步目标窗口 x
        self._walk_speed = 0.0         # 散步速度 px/s

        self._init_ui()
        self._init_animation()
        self._setup_physics()
        self._setup_edge_timer()
        # 启动后延迟预取余额：单击余额气泡时秒显，不用等网络
        QTimer.singleShot(1500, lambda: _prefetch_balance(self.config))

    def _init_ui(self):
        # 透明无边框置顶 — 确保在所有窗口前面
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.Window  # 顶层窗口
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # 不抢焦点
        self.setAcceptDrops(True)
        self.setFixedSize(self.PET_SIZE, self.PET_SIZE)

        # 精灵标签
        self.sprite_label = QLabel(self)
        self.sprite_label.setFixedSize(self.PET_SIZE, self.PET_SIZE)
        self.sprite_label.setAttribute(Qt.WA_TranslucentBackground)

        # 气泡标签
        self.bubble_label = QLabel(self)
        self.bubble_label.setStyleSheet("""
            background: white; border: 1px solid #ccc; border-radius: 8px;
            padding: 6px 10px; font-size: 12px;
        """)
        self.bubble_label.setWordWrap(True)
        self.bubble_label.setMaximumWidth(200)
        self.bubble_label.hide()

        # 位置恢复
        x = self.config.pet_x
        y = self.config.pet_y
        self.move(x, y)

    def _init_animation(self):
        self.anim = AnimationController(fps=8)
        self.anim.frame_changed.connect(self._on_frame)

        # 优先用 sprites 目录下的 PNG 素材，无则用代码绘制的 chibi
        for state in PetState:
            if not self.anim.load_from_dir(state):
                frames = make_placeholder_frames(state, count=8, size=self.PET_SIZE)
                self.anim.load_state(state, frames)

        self.anim.switch(PetState.IDLE)
        self.anim.play()

    def _on_frame(self, pixmap: QPixmap):
        self._cur_frame = pixmap.scaled(self.PET_SIZE, self.PET_SIZE,
                                        Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._render()

    def _render(self):
        """把当前帧按 倾斜+缩放+位移 变换后显示（绕窗口中心，固定尺寸防抖动）"""
        if self._cur_frame is None:
            return
        self._tilted.fill(Qt.transparent)
        p = QPainter(self._tilted)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        half = self.PET_SIZE // 2
        p.translate(half, half)
        p.scale(self._facing, 1.0)                 # 镜像：往左甩转身朝左
        p.rotate(self._tilt_angle * self._facing)  # 镜像坐标内反角度，视觉倾斜不随镜像翻转
        p.scale(self._scale_x, self._scale_y)
        p.translate(self._bob_x, self._bob_y)
        p.drawPixmap(-half, -half, self._cur_frame)
        p.end()
        self.sprite_label.setPixmap(self._tilted)

    def _setup_edge_timer(self):
        """定时检测贴边/鼠标靠近"""
        self._edge_timer = QTimer(self)
        self._edge_timer.timeout.connect(self._check_edge)
        self._edge_timer.start(200)

    def _setup_physics(self):
        """物理循环 ~60fps 常驻，与 8fps 动画 timer 解耦。idle 呼吸/滑动/甩飞共用"""
        self._phys_timer = QTimer(self)
        self._phys_timer.setInterval(16)
        self._phys_timer.timeout.connect(self._physics_tick)
        self._phys_timer.start()

    # ── 拎起来甩物理 ─────────────────────

    def _start_grab(self):
        """真正拎起来（拖拽超过点击阈值）"""
        if self._hidden_at_edge:
            self.expand_from_edge()      # 算好展开目标 + 清隐藏标记（内部会起 slide）
            self._px = self._target_x    # 拎起要立即弹出到位，跳过平滑滑动
            self._py = self._target_y
            self.move(round(self._px), round(self._py))
        self._mode = "grabbed"
        self._px = float(self.x())
        self._py = float(self.y())
        self._vx = self._vy = 0.0
        self._tilt_angle = 0.0
        self._tilt_v = 0.0
        self._scale_x = self._scale_y = 1.0  # 拎起时复位呼吸 squash
        self._bob_x = self._bob_y = 0.0
        self._facing = 1
        self._last_mouse_x = self._mouse.x()
        self._drag_dx = 0.0
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        self._screen_geo = screen.availableGeometry()
        self.set_state("held")
        self._last_tick = time.monotonic()

    def _physics_tick(self):
        now = time.monotonic()
        dt = min(0.05, now - self._last_tick)
        self._last_tick = now
        if dt <= 0:
            return

        self._anim_t += dt

        if self._mode == "grabbed":
            self._step_grabbed(dt)
            self._step_tilt(dt)
            self.move(round(self._px), round(self._py))
        elif self._mode == "flying":
            self._step_flying(dt)
            self._step_tilt(dt)
            self.move(round(self._px), round(self._py))
        elif self._mode == "walk":
            self._step_walk(dt)
            self.move(round(self._px), round(self._py))
        elif self._mode == "slide":
            self._step_slide(dt)
            self.move(round(self._px), round(self._py))
        else:  # idle / 贴边停靠
            self._step_idle(dt)

        self._render()

    def _facing_toward_center(self) -> int:
        """按窗口位置决定朝向: 屏幕右半朝左(-1), 左半朝右(1), 始终面向屏幕中心"""
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        if not screen:
            return self._facing
        sg = screen.availableGeometry()
        center_x = (sg.left() + sg.right()) / 2
        return -1 if self.x() + self.PET_SIZE / 2 > center_x else 1

    def _step_idle(self, dt):
        """呼吸（idle/peek 停靠）+ 双击跳跃弧线 + 跳舞纯帧循环，仅视觉变换不动窗口"""
        if self.anim.current_state == PetState.HAPPY:
            pr = min(1.0, self._anim_t / 2.0)
            self._bob_y = -40 * math.sin(math.pi * pr)  # 跳起→落下
            self._scale_x = self._scale_y = 1.0
        elif self.anim.current_state == PetState.DANCE:
            # 跳舞：8 帧帧动画已足够，不叠程序化 bob/tilt
            self._scale_x = self._scale_y = 1.0
            self._bob_y = 0.0
        else:
            # 待机朝向：按位置面向屏幕中心（拖动桌宠后自动转身，不随机）
            # 每 0.1s 更新一次（肉眼无感延迟，避免 60fps 每帧查询屏幕几何）
            if int(self._anim_t * 10) != int((self._anim_t - dt) * 10):
                want = self._facing_toward_center()
                if want != self._facing:
                    self._facing = want
            s = math.sin(self._anim_t * 1.5) * 0.02
            self._scale_y = 1.0 + s
            self._scale_x = 1.0 - s
            self._bob_y = 0.0
        self._bob_x = 0.0

    def _step_slide(self, dt):
        """弹簧-阻尼逼近目标位置（hide/peek 平滑过渡），到位回 idle"""
        K, C = 70.0, 17.0
        self._vx += ((self._target_x - self._px) * K - self._vx * C) * dt
        self._vy += ((self._target_y - self._py) * K - self._vy * C) * dt
        self._px += self._vx * dt
        self._py += self._vy * dt
        if (abs(self._target_x - self._px) < 0.5 and abs(self._target_y - self._py) < 0.5
                and abs(self._vx) < 5.0 and abs(self._vy) < 5.0):
            self._px = self._target_x
            self._py = self._target_y
            self._vx = self._vy = 0.0
            self._mode = "idle"
            self.config.pet_x = round(self._px)
            self.config.pet_y = round(self._py)
            self._schedule_walk()

    # ── 闲置散步（walk 状态：8 帧步态循环 + 水平移动）───

    def _schedule_walk(self):
        """安排下一次散步（闲置 25-60 秒后）"""
        self._walk_ready_at = time.monotonic() + random.uniform(25, 60)

    def _maybe_start_walk(self) -> bool:
        """闲置够久且条件满足 → 开始散步。返回 True 表示已触发（调用方应跳过贴边检测）"""
        if self._mode != "idle" or self._hidden_at_edge:
            return False
        if self.anim.current_state != PetState.IDLE:
            self._schedule_walk()  # happy/peek 等未结束，重新计时
            return False
        if time.monotonic() < self._walk_ready_at:
            return False

        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        sg = screen.availableGeometry()
        lo = sg.left() + 40
        hi = sg.right() - self.PET_SIZE - 40
        if hi - lo < 80:  # 屏幕可用宽度太小，放弃散步
            self._schedule_walk()
            return False

        cx = float(self.x())
        dist = random.uniform(120, 300)
        self._facing = self._facing_toward_center()  # 按位置面向屏幕中心，不随机
        tx = cx + self._facing * dist
        tx = max(lo, min(hi, tx))
        if abs(tx - cx) < 40:  # 目标太近（贴边处），换个时间再走
            self._schedule_walk()
            return False

        self._walk_target_x = tx
        self._walk_speed = random.uniform(55.0, 75.0)
        self._px = cx
        self._py = float(self.y())
        self._vx = self._vy = 0.0
        self._scale_x = self._scale_y = 1.0
        self._bob_x = self._bob_y = 0.0
        self._tilt_angle = 0.0
        self._tilt_v = 0.0
        self.set_state("walk")   # 此时 _mode 仍是 idle，门控放行
        self._mode = "walk"
        return True

    def _step_walk(self, dt):
        """原地步态帧循环（动画 timer 驱动）+ 水平匀速移动，到位回 idle"""
        d = self._walk_speed * dt
        if self._facing > 0:
            self._px = min(self._walk_target_x, self._px + d)
        else:
            self._px = max(self._walk_target_x, self._px - d)
        self._py = float(self.y())
        if abs(self._px - self._walk_target_x) < 1.0:
            self._px = self._walk_target_x
            self._finish_walk()

    def _finish_walk(self):
        """散步结束，站稳回 idle"""
        self._mode = "idle"
        self._vx = self._vy = 0.0
        self.set_state("idle")
        self._schedule_walk()
        self.config.pet_x = round(self._px)
        self.config.pet_y = round(self._py)
        self._render()

    def _step_grabbed(self, dt):
        """弹簧-阻尼跟随鼠标（K 大 → 跟手紧，C≈2√K 临界阻尼无震荡）"""
        K, C = 200.0, 28.0
        tx = self._mouse.x() - self._grab_offset.x()
        ty = self._mouse.y() - self._grab_offset.y()
        self._vx += ((tx - self._px) * K - self._vx * C) * dt
        self._vy += ((ty - self._py) * K - self._vy * C) * dt
        self._px += self._vx * dt
        self._py += self._vy * dt

    def _step_flying(self, dt):
        """松手惯性 + 重力下落 + 落地弹跳 + 墙反弹"""
        G = 2000.0
        self._vy += G * dt
        self._px += self._vx * dt
        self._py += self._vy * dt

        sg = self._screen_geo

        floor = sg.bottom()
        if self._py + self.PET_SIZE >= floor:
            self._py = floor - self.PET_SIZE
            if self._vy > 100.0:
                self._vy = -self._vy * 0.55
                self._vx *= 0.9
            else:
                self._vy = 0.0
                self._vx -= self._vx * 9.0 * dt
                if abs(self._vx) < 20.0:
                    self._vx = 0.0
                    self._settle()

        if self._px <= sg.left():
            self._px = sg.left()
            self._vx = abs(self._vx) * 0.7
        elif self._px + self.PET_SIZE >= sg.right():
            self._px = sg.right() - self.PET_SIZE
            self._vx = -abs(self._vx) * 0.7
        if self._py <= sg.top():
            self._py = sg.top()
            self._vy = 0.0

    def _step_tilt(self, dt):
        """倾斜角由水平速度驱动，自身走阻尼弹簧避免逐帧抖"""
        if self._mode == "grabbed":
            # 转身跟随鼠标运动方向：位移指数平滑，慢速拖也稳定翻转（vx 稳态≈0 会卡在旧方向）
            self._drag_dx = self._drag_dx * 0.6 + (self._mouse.x() - self._last_mouse_x)
            self._last_mouse_x = self._mouse.x()
            if self._drag_dx > 6.0:
                self._facing = 1
            elif self._drag_dx < -6.0:
                self._facing = -1
        else:  # flying：转身跟随甩速方向
            if self._vx > 5.0:
                self._facing = 1
            elif self._vx < -5.0:
                self._facing = -1
        target = max(-30.0, min(30.0, self._vx * 0.016))
        self._tilt_v += ((target - self._tilt_angle) * 60.0 - self._tilt_v * 15.0) * dt
        self._tilt_angle += self._tilt_v * dt

    def _settle(self):
        """站稳，回 idle"""
        self._mode = "idle"
        self._vx = self._vy = 0.0
        self._tilt_angle = 0.0
        self._tilt_v = 0.0
        self._scale_x = self._scale_y = 1.0
        self._bob_x = self._bob_y = 0.0
        self._facing = self._facing_toward_center()  # 落地立即面向屏幕中心（替代固定朝右）
        self._release_protect_until = time.monotonic() + 3.0  # 落地后暂不贴边
        self.move(round(self._px), round(self._py))
        self.set_state("idle")
        self._render()
        self.config.pet_x = round(self._px)
        self.config.pet_y = round(self._py)
        self._schedule_walk()

    # ── 动画状态 ──────────────────────────

    def set_state(self, state_name: str):
        """切换动画状态: "idle"|"walk"|"dance"|"hide"|"peek"|"sleep"|"happy"|"lying"|"held"|"flying" """
        if self._mode != "idle" and state_name not in ("held", "flying"):
            return  # 物理态（拎起/甩飞）拥有表情，落地回 idle 后再响应
        self._anim_t = 0.0  # 换状态重置动画相位（呼吸/跳跃重新起弧）
        try:
            state = PetState(state_name)
            self.anim.switch(state)
            if state != self.anim.current_state:
                self.anim.play()
        except ValueError:
            pass

    def show_bubble(self, text: str, duration_ms: int = 3000):
        """头顶显示气泡"""
        self.bubble_label.setText(text)
        self.bubble_label.adjustSize()
        bx = (self.PET_SIZE - self.bubble_label.width()) // 2
        by = max(0, self.PET_SIZE // 2 - 180)
        self.bubble_label.move(bx, by)
        self.bubble_label.show()
        QTimer.singleShot(duration_ms, self.bubble_label.hide)

    def show_balance_bubble(self):
        """单击触发：显示/隐藏余额气泡（独立悬浮窗，放在桌宠旁边不挡角色）"""
        if self._balance_bubble is None:
            self._balance_bubble = BalanceBubble(
                lambda: ApiClient(self.config).get_balance())
        if self._balance_bubble.isVisible():
            self._balance_bubble.hide()
            return
        self._place_balance_bubble()
        self._balance_bubble.show()
        self._balance_bubble.refresh()

    def _place_balance_bubble(self):
        """把余额气泡放到桌宠正上方（顶部放不下时放下方）"""
        if self._balance_bubble is None:
            return
        self._balance_bubble.place_above(self.geometry())

    def moveEvent(self, event):
        """桌宠移动/散步/拖拽时，余额气泡跟随"""
        super().moveEvent(event)
        if self._balance_bubble is not None and self._balance_bubble.isVisible():
            self._place_balance_bubble()

    # ── 贴边隐藏 ──────────────────────────

    def _check_edge(self):
        """检测是否应贴边隐藏/展开"""
        if self._mode != "idle" or self.anim.current_state == PetState.DANCE:
            return  # 拖拽/飞落中或跳舞时不贴边（防打断）
        if time.monotonic() < self._release_protect_until:
            return  # 拖拽/落地后冷却期内不贴边（防误吸）
        if self._maybe_start_walk():
            return  # 已开始散步，本 tick 不再做贴边检测
        screen = QApplication.screenAt(self.geometry().center())
        if not screen:
            return
        sg = screen.availableGeometry()
        pet_geo = self.geometry()

        # 鼠标位置
        cursor_pos = QCursor.pos()

        if self._hidden_at_edge:
            # 已隐藏：检测鼠标是否靠近隐藏边
            if self._snapped_edge == "left" and cursor_pos.x() <= pet_geo.right() + 20:
                self.expand_from_edge()
            elif self._snapped_edge == "right" and cursor_pos.x() >= pet_geo.left() - 20:
                self.expand_from_edge()
            elif self._snapped_edge == "top" and cursor_pos.y() <= pet_geo.bottom() + 20:
                self.expand_from_edge()
        else:
            # 未隐藏：检测是否贴近边缘
            dist_left = pet_geo.left() - sg.left()
            dist_right = sg.right() - pet_geo.right()
            dist_top = pet_geo.top() - sg.top()

            if dist_left < self.EDGE_THRESHOLD and dist_left <= dist_right:
                self.snap_to_edge("left")
            elif dist_right < self.EDGE_THRESHOLD and dist_right < dist_left:
                self.snap_to_edge("right")
            elif dist_top < self.EDGE_THRESHOLD:
                self.snap_to_edge("top")

    def snap_to_edge(self, edge=None):
        """贴边隐藏"""
        # 贴边隐藏时自动收起余额云朵（展开后需重新单击才显示）
        if self._balance_bubble is not None and self._balance_bubble.isVisible():
            self._balance_bubble.hide()
        if not edge:
            # 自动检测最近边
            screen = QApplication.screenAt(self.geometry().center())
            if not screen:
                return
            sg = screen.availableGeometry()
            geo = self.geometry()
            dists = {
                "left": geo.left() - sg.left(),
                "right": sg.right() - geo.right(),
                "top": geo.top() - sg.top(),
            }
            edge = min(dists, key=lambda k: abs(dists[k]))
        screen = QApplication.screenAt(self.geometry().center())
        if not screen:
            return
        sg = screen.availableGeometry()
        x, y = self.x(), self.y()

        if edge == "left":
            x = sg.left() - self.PET_SIZE + self.PEEK_PX
        elif edge == "right":
            x = sg.right() - self.PEEK_PX
        elif edge == "top":
            y = sg.top() - self.PET_SIZE + self.PEEK_PX

        # 贴边时显示完整角色（idle）而非 peek 躲藏图——peek 素材显示效果像"只有尾巴"，已弃用
        self.set_state("idle")           # 先切动画态（此时 _mode 仍 idle，门控放行）
        self._hidden_at_edge = True
        self._snapped_edge = edge
        self._start_slide(x, y)

    def expand_from_edge(self):
        """从边缘展开"""
        screen = QApplication.screenAt(self.geometry().center())
        if not screen:
            return
        sg = screen.availableGeometry()
        x, y = self.x(), self.y()

        if self._snapped_edge == "left":
            x = sg.left()
        elif self._snapped_edge == "right":
            x = sg.right() - self.PET_SIZE
        elif self._snapped_edge == "top":
            y = sg.top()

        self.set_state("idle")           # 先切回 idle（此时 _mode 仍 idle，门控放行）
        self._hidden_at_edge = False
        self._snapped_edge = None
        self._start_slide(x, y)

    def _start_slide(self, x, y):
        """弹簧逼近目标窗口位置（hide/peek 平滑过渡）"""
        self._target_x = float(x)
        self._target_y = float(y)
        self._px = float(self.x())
        self._py = float(self.y())
        self._vx = self._vy = 0.0
        self._mode = "slide"

    # ── 鼠标交互 ──────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            self._is_dragging = False
            self._mouse = event.globalPosition()
            # 拎住衣领：锚点对准领口（左右白色领子正中，原图 ~267,327 → 窗口比例 0.52,0.64）
            self._grab_offset = QPointF(self.PET_SIZE * 0.52, self.PET_SIZE * 0.64)
            self._samples.clear()
            self._samples.append((time.monotonic(),
                                  self._mouse.x(), self._mouse.y()))

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton and self._drag_start is not None:
            gp = event.globalPosition()
            self._mouse = gp
            self._samples.append((time.monotonic(), gp.x(), gp.y()))
            if not self._is_dragging:
                delta = gp.toPoint() - self._drag_start
                if delta.manhattanLength() > self.CLICK_THRESHOLD:
                    self._is_dragging = True
                    self._start_grab()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self._is_dragging:
                # 拎起来过 → 算甩速抛出
                flick_vx = flick_vy = 0.0
                if len(self._samples) >= 2:
                    (t1, x1, y1), (t2, x2, y2) = self._samples[-2], self._samples[-1]
                    dtt = max(1e-4, t2 - t1)
                    flick_vx = (x2 - x1) / dtt
                    flick_vy = (y2 - y1) / dtt
                self._vx += flick_vx * 0.5
                self._vy += flick_vy * 0.5
                mag = math.hypot(self._vx, self._vy)
                # 松手后 3 秒内不贴边（防止拖到边缘松手就被吸走）
                self._release_protect_until = time.monotonic() + 3.0
                if mag < 300.0:
                    # 甩速小 → 直接停在当前位置（不再重力落回原位）
                    self._mode = "idle"
                    self._vx = self._vy = 0.0
                    self._tilt_angle = 0.0
                    self._tilt_v = 0.0
                    self._scale_x = self._scale_y = 1.0
                    self._bob_x = self._bob_y = 0.0
                    self._facing = self._facing_toward_center()  # 立即转身面向屏幕中心
                    self.set_state("idle")
                    self.config.pet_x = round(self.x())
                    self.config.pet_y = round(self.y())
                    self._schedule_walk()
                else:
                    if mag > 2500.0:
                        self._vx = self._vx / mag * 2500.0
                        self._vy = self._vy / mag * 2500.0
                    self._mode = "flying"
                    self.set_state("flying")
            else:
                # 纯点击 → 延迟判定（等双击窗口期，双击时被取消）
                if self._mode == "walk":
                    self._finish_walk()  # 散步中点击：先站稳
                now = time.monotonic()
                if now >= self._dbl_guard_until:
                    self._click_gen += 1
                    gen = self._click_gen
                    # 自研三击：600ms 内三次独立点击 → 跳舞（不依赖 Qt 双击事件）
                    self._click_times = [t for t in self._click_times if now - t < 0.8]
                    self._click_times.append(now)
                    if (len(self._click_times) >= 3
                            and self._click_times[-1] - self._click_times[-3] < self.TRIPLE_SPAN):
                        self._click_times.clear()
                        self._click_pending = False
                        self._double_at = 0.0
                        self._dbl_guard_until = now + self.TRIPLE_SPAN
                        self._start_dance()
                        self.config.pet_x = self.x()
                        self.config.pet_y = self.y()
                        self._drag_start = None
                        self._is_dragging = False
                        return
                    # 独立单击：CLICK_CONFIRM_MS 快速确认（新点击会以代际作废旧定时）
                    self._click_pending = True
                    QTimer.singleShot(self.CLICK_CONFIRM_MS,
                                      lambda g=gen: self._emit_click_if_pending(g))
                self.config.pet_x = self.x()
                self.config.pet_y = self.y()
            self._drag_start = None
            self._is_dragging = False

    def _emit_click_if_pending(self, gen=None):
        """单击确认（双击窗口期已过仍未取消 → 显示余额气泡）"""
        if self._click_pending and (gen is None or gen == self._click_gen):
            self._click_pending = False
            self.clicked.emit()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """双击 → 打开聊天窗；300ms 内第三次连击 → 跳舞

        Qt 的连击序列中第三次 press 也是 DblClick 事件：距上次双击
        <300ms 的 DblClick 即三击。
        """
        if event.button() == Qt.LeftButton:
            self._click_pending = False  # 取消挂起的单击
            self._click_times.clear()    # 双击序列的 release 不参与三击判定
            # 快速确认可能已弹出余额云朵 → 双击时立即收起
            if self._balance_bubble is not None and self._balance_bubble.isVisible():
                self._balance_bubble.hide()
            now = time.monotonic()
            if self._double_at and now - self._double_at < self.TRIPLE_WINDOW:
                # 三击 → 跳舞
                self._double_at = 0.0
                self._dbl_guard_until = now + self.TRIPLE_WINDOW
                self._start_dance()
            else:
                self._double_at = now
                self._dbl_guard_until = now + self.TRIPLE_WINDOW
                # 定时比窗口略晚（+50ms），并留 20ms 判定余量：
                # Qt 定时器可能提前几毫秒触发，严格 >= 窗口会漏判
                QTimer.singleShot(int(self.TRIPLE_WINDOW * 1000) + 50,
                                  self._emit_chat_if_no_triple)

    def _emit_chat_if_no_triple(self):
        """双击 TRIPLE_WINDOW 后无第三击 → 打开聊天窗"""
        if (self._double_at
                and time.monotonic() - self._double_at >= self.TRIPLE_WINDOW - 0.02):
            self._double_at = 0.0
            self.chat_requested.emit()

    def _start_dance(self):
        """三击 — 跳舞动画（即梦生成 8 帧循环，跳 10 秒自动回 idle）"""
        self._mode = "idle"  # 贴边滑行/散步中三击：先回 idle 放行 set_state 门控
        # 慢三击可能已触发一次单击确认（云朵弹出）→ 跳舞时收起
        if self._balance_bubble is not None and self._balance_bubble.isVisible():
            self._balance_bubble.hide()
        self.set_state("dance")
        self.show_bubble("♪ 来跳支舞吧 ♪", 2000)
        self._dance_until = time.monotonic() + 10
        QTimer.singleShot(10000, self._end_dance)

    def _end_dance(self):
        """跳舞结束回 idle（校验截止时间，防止被旧 timer 提前打断）"""
        if time.monotonic() >= self._dance_until:
            self.set_state("idle")

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("设置 API", lambda: None)  # 由 main.py 连接
        menu.addSeparator()
        menu.addAction("隐藏", self.hide)
        menu.addAction("退出", QApplication.quit)
        menu.exec(event.globalPos())

    # ── 文件拖放（垃圾桶）─────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.set_state("happy")

    def dragLeaveEvent(self, event):
        self.set_state("idle")

    def dropEvent(self, event: QDropEvent):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        self.files_dropped.emit(paths)
        self.set_state("idle")

    # ── 生命周期 ──────────────────────────

    def closeEvent(self, event):
        self.config.pet_x = self.x()
        self.config.pet_y = self.y()
        super().closeEvent(event)
