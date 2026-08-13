"""桌宠窗口 — 透明无边框置顶、拖拽、贴边隐藏、文件拖放"""
import sys
import time
import math
from collections import deque
from PySide6.QtWidgets import QWidget, QLabel, QMenu, QApplication
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QPointF
from PySide6.QtGui import QPixmap, QPainter, QMouseEvent, QDropEvent, QDragEnterEvent, QCursor

from module_1_core.animation import (AnimationController, PetState,
                                       make_placeholder_frames, SPRITE_DIR)
from module_2_api.config_manager import ConfigManager


class PetWindow(QWidget):
    """主桌宠窗口"""
    clicked = Signal()
    files_dropped = Signal(list)

    # 宠物本体大小
    PET_SIZE = 256
    # 贴边时露出像素
    PEEK_PX = 30
    # 边缘吸附阈值
    EDGE_THRESHOLD = 50
    # 单击判定 — 移动小于此像素算点击
    CLICK_THRESHOLD = 5

    def __init__(self, config: ConfigManager = None):
        super().__init__()
        self.config = config or ConfigManager.instance()
        self._drag_start = None
        self._is_dragging = False
        self._hidden_at_edge = False
        self._snapped_edge = None  # "left" | "right" | "top" | None
        self._bubble = None

        # 拎起来甩 — 物理状态
        self._mode = "idle"            # idle | grabbed | flying
        self._px = 0.0                 # 浮点窗口位置
        self._py = 0.0
        self._vx = 0.0
        self._vy = 0.0
        self._tilt_angle = 0.0         # 倾斜角（度）
        self._tilt_v = 0.0
        self._grab_offset = QPointF()  # 鼠标相对窗口的偏移
        self._mouse = QPointF()        # 鼠标全局坐标
        self._samples = deque(maxlen=6)  # (t, x, y) 甩速采样
        self._cur_frame = None         # 当前动画帧（未倾斜）
        self._tilted = QPixmap(self.PET_SIZE, self.PET_SIZE)  # 倾斜渲染缓冲
        self._screen_geo = None        # 拎起时缓存的屏幕几何
        self._last_tick = time.monotonic()

        self._init_ui()
        self._init_animation()
        self._setup_physics()
        self._setup_edge_timer()

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
        """把当前帧按倾斜角旋转后显示（绕窗口中心，固定尺寸防抖动）"""
        if self._cur_frame is None:
            return
        if abs(self._tilt_angle) < 0.01:
            if self.sprite_label.pixmap() is not self._cur_frame:
                self.sprite_label.setPixmap(self._cur_frame)
            return
        self._tilted.fill(Qt.transparent)
        p = QPainter(self._tilted)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        half = self.PET_SIZE // 2
        p.translate(half, half)
        p.rotate(self._tilt_angle)
        p.drawPixmap(-half, -half, self._cur_frame)
        p.end()
        self.sprite_label.setPixmap(self._tilted)

    def _setup_edge_timer(self):
        """定时检测贴边/鼠标靠近"""
        self._edge_timer = QTimer(self)
        self._edge_timer.timeout.connect(self._check_edge)
        self._edge_timer.start(200)

    def _setup_physics(self):
        """物理循环 ~60fps，与 8fps 动画 timer 解耦"""
        self._phys_timer = QTimer(self)
        self._phys_timer.setInterval(16)
        self._phys_timer.timeout.connect(self._physics_tick)

    # ── 拎起来甩物理 ─────────────────────

    def _start_grab(self):
        """真正拎起来（拖拽超过点击阈值）"""
        if self._hidden_at_edge:
            self.expand_from_edge()
        self._mode = "grabbed"
        self._px = float(self.x())
        self._py = float(self.y())
        self._vx = self._vy = 0.0
        self._tilt_angle = 0.0
        self._tilt_v = 0.0
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        self._screen_geo = screen.availableGeometry()
        self.set_state("held")
        self._last_tick = time.monotonic()
        self._phys_timer.start()

    def _physics_tick(self):
        now = time.monotonic()
        dt = min(0.05, now - self._last_tick)
        self._last_tick = now
        if dt <= 0:
            return

        if self._mode == "grabbed":
            self._step_grabbed(dt)
        elif self._mode == "flying":
            self._step_flying(dt)
        else:
            self._phys_timer.stop()
            return

        self._step_tilt(dt)
        self.move(round(self._px), round(self._py))
        self._render()

    def _step_grabbed(self, dt):
        """弹簧-阻尼跟随鼠标（临界阻尼→平滑惯性，无震荡）"""
        K, C = 70.0, 17.0
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
        target = max(-12.0, min(12.0, -self._vx * 0.006))
        self._tilt_v += ((target - self._tilt_angle) * 60.0 - self._tilt_v * 15.0) * dt
        self._tilt_angle += self._tilt_v * dt

    def _settle(self):
        """站稳，回 idle"""
        self._mode = "idle"
        self._vx = self._vy = 0.0
        self._tilt_angle = 0.0
        self._tilt_v = 0.0
        self._phys_timer.stop()
        self.move(round(self._px), round(self._py))
        self.set_state("idle")
        self._render()
        self.config.pet_x = round(self._px)
        self.config.pet_y = round(self._py)

    # ── 动画状态 ──────────────────────────

    def set_state(self, state_name: str):
        """切换动画状态: "idle"|"walk"|"hide"|"peek"|"sleep"|"happy"|"lying"|"held"|"flying" """
        if self._mode != "idle" and state_name not in ("held", "flying"):
            return  # 物理态（拎起/甩飞）拥有表情，落地回 idle 后再响应
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

    # ── 贴边隐藏 ──────────────────────────

    def _check_edge(self):
        """检测是否应贴边隐藏/展开"""
        if self._mode != "idle":
            return
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

        self.move(x, y)
        self._hidden_at_edge = True
        self._snapped_edge = edge
        self.set_state("peek")

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

        self.move(x, y)
        self._hidden_at_edge = False
        self._snapped_edge = None
        self.set_state("idle")

    # ── 鼠标交互 ──────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            self._is_dragging = False
            self._mouse = event.globalPosition()
            self._grab_offset = self._mouse - QPointF(self.pos())
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
                if mag > 2500.0:
                    self._vx = self._vx / mag * 2500.0
                    self._vy = self._vy / mag * 2500.0
                self._mode = "flying"
                self.set_state("flying")
            else:
                # 纯点击 → 打开聊天
                self.clicked.emit()
                self.config.pet_x = self.x()
                self.config.pet_y = self.y()
            self._drag_start = None
            self._is_dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """双击喂食 — 开心动画"""
        if event.button() == Qt.LeftButton:
            self.set_state("happy")
            self.show_bubble("啊呜~ 好吃!", 2000)
            QTimer.singleShot(2000, lambda: self.set_state("idle"))

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
