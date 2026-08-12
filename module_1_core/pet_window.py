"""桌宠窗口 — 透明无边框置顶、拖拽、贴边隐藏、文件拖放"""
import sys
from PySide6.QtWidgets import QWidget, QLabel, QMenu, QApplication
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
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

        self._init_ui()
        self._init_animation()
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
        scaled = pixmap.scaled(self.PET_SIZE, self.PET_SIZE,
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.sprite_label.setPixmap(scaled)

    def _setup_edge_timer(self):
        """定时检测贴边/鼠标靠近"""
        self._edge_timer = QTimer(self)
        self._edge_timer.timeout.connect(self._check_edge)
        self._edge_timer.start(200)

    # ── 动画状态 ──────────────────────────

    def set_state(self, state_name: str):
        """切换动画状态: "idle"|"walk"|"hide"|"peek"|"sleep"|"happy" """
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

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton and self._drag_start:
            delta = event.globalPosition().toPoint() - self._drag_start
            if delta.manhattanLength() > self.CLICK_THRESHOLD:
                self._is_dragging = True
            if self._is_dragging:
                self.move(self.pos() + delta)
                self._drag_start = event.globalPosition().toPoint()
                # 拖拽时先展开
                if self._hidden_at_edge:
                    self.expand_from_edge()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and not self._is_dragging:
            self.clicked.emit()
        # 保存位置
        self.config.pet_x = self.x()
        self.config.pet_y = self.y()

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
