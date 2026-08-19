"""聊天窗口 — 深海主题卡片式 UI：磨砂渐变卡片 + header(头像/状态/关闭) + 尾巴气泡 + 胶囊输入区"""
import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QTextEdit, QPushButton, QLabel, QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QTimer, QRectF, QPointF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QColor, QPainter, QMouseEvent, QPen, QBrush, QLinearGradient,
    QPainterPath, QPixmap, QPolygonF,
)

from module_2_api.config_manager import ConfigManager
from module_2_api.api_client import ApiClient, ApiConfigError, ApiAuthError, ApiQuotaError, ApiRateLimitError, ApiNetworkError
from module_3_chat.conversation_store import ConversationStore
from module_3_chat.greeting import get_random_greeting
from module_1_core.animation import PetState, make_placeholder_sprite

SYSTEM_PROMPT = """你是一只深海鲸鱼娘桌宠，形象是蓝色长发+鲸鱼尾巴+女仆装的可爱女孩。
性格：傲娇、嘴硬心软、偶尔撒娇。你是 DeepSeek 的娘化形象，被网友叫做"大肥鱼"但你很讨厌这个称呼。
你的尾巴会随着情绪摆动：开心时摇尾巴，害羞时卷成螺旋，生气时拍打地面。
说话风格：
- 可爱、活泼，带一点傲娇
- 偶尔嘴硬说"才不是…呢！""哼！"
- 用简短的分句，不要太长
- 可以适当用颜文字 (~, >_<, QwQ)
- 被夸的时候会害羞，被说"大肥鱼"会生气
- 认真回答问题的时候会收起傲娇，专业回答
- 禁止说自己是AI助手/语言模型，你就是深海鲸鱼娘！"""

# ── 主题（深海蓝）──────────────────
CARD_TOP      = "#F9FBFF"   # 卡片渐变顶
CARD_BOTTOM   = "#EDF3FC"   # 卡片渐变底
CARD_BORDER   = QColor(74, 158, 255, 70)
AI_BUBBLE_A   = "#FFFFFF"   # AI 气泡渐变
AI_BUBBLE_B   = "#EAF3FF"
AI_BORDER     = QColor(74, 158, 255, 40)
USER_BUBBLE_A = "#5FB4FF"   # 用户气泡渐变
USER_BUBBLE_B = "#3D8BF0"
TEXT_DARK     = "#2C3E50"
TEXT_WHITE    = "#FFFFFF"
TEXT_SUB      = "#8A94A6"
ACCENT        = "#4A9EFF"
ONLINE_GREEN  = "#34D399"

WIN_W   = 520
WIN_H   = 450
MIN_W   = 400
MIN_H   = 360
EDGE    = 8           # 边缘 resize 检测宽度
RADIUS  = 18          # 卡片圆角
HEADER_H = 52
AVATAR_S = 34         # header 头像
MSG_AVATAR = 32       # 气泡行头像
TAIL_W  = 9           # 气泡尾巴长度
BUBBLE_R = 14         # 气泡圆角

# ── 工具 ───────────────────────────

def _rounded_path(rect: QRectF, tl, tr, br, bl) -> QPainterPath:
    """四角独立圆角路径"""
    p = QPainterPath()
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    d = 2 * 0.5522847498  # 圆角逼近系数
    p.moveTo(x + tl, y)
    p.lineTo(x + w - tr, y)
    p.cubicTo(x + w - tr + tr * d, y, x + w, y + tr - tr * d, x + w, y + tr)
    p.lineTo(x + w, y + h - br)
    p.cubicTo(x + w, y + h - br + br * d, x + w - br + br * d, y + h, x + w - br, y + h)
    p.lineTo(x + bl, y + h)
    p.cubicTo(x + bl - bl * d, y + h, x, y + h - bl + bl * d, x, y + h - bl)
    p.lineTo(x, y + tl)
    p.cubicTo(x, y + tl - tl * d, x + tl - tl * d, y, x + tl, y)
    p.closeSubpath()
    return p


def _circle_pix(src: QPixmap, size: int) -> QPixmap:
    """任意图 → 圆形裁剪头像（覆盖缩放居中）"""
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    p.setClipPath(path)
    scaled = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    p.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    p.end()
    return out


def _face_crop(src: QPixmap, size: int) -> QPixmap:
    """全身精灵图 → 头部聚焦头像：取画面顶部 30% 高度（头+肩）居中裁剪再圆形化。

    全身图几何居中裁剪只会裁到躯干/裙子（角色头顶在 y≈15，画面中心在身体），
    头像必须聚焦头部区域。
    """
    w, h = src.width(), src.height()
    hw = int(w * 0.60)
    hx = (w - hw) // 2
    hy = int(h * 0.02)  # 避开顶部透明边缘
    hh = int(h * 0.30)
    return _circle_pix(src.copy(hx, hy, hw, hh), size)


_ai_avatar_cache = None
_user_avatar_cache = None


def _ai_avatar():
    """鲸鱼娘圆形头像（用趴姿帧）"""
    global _ai_avatar_cache
    if _ai_avatar_cache is None:
        from module_1_core.animation import SPRITE_DIR
        idle = SPRITE_DIR / "idle_00.png"
        if idle.exists():
            _ai_avatar_cache = _face_crop(QPixmap(str(idle)), MSG_AVATAR)
        else:
            _ai_avatar_cache = _circle_pix(make_placeholder_sprite(PetState.IDLE, size=64), MSG_AVATAR)
    return _ai_avatar_cache


def _user_avatar():
    """用户头像：蓝渐变圆 + 白字"""
    global _user_avatar_cache
    if _user_avatar_cache is None:
        s = MSG_AVATAR
        out = QPixmap(s, s)
        out.fill(Qt.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, 0, s)
        grad.setColorAt(0, QColor(USER_BUBBLE_A))
        grad.setColorAt(1, QColor(USER_BUBBLE_B))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, s, s)
        p.setPen(QColor(TEXT_WHITE))
        f = p.font()
        f.setPointSizeF(9.5)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, 0, s, s), Qt.AlignCenter, "我")
        p.end()
        _user_avatar_cache = out
    return _user_avatar_cache


def _cached_pet_pix():
    """header 大头像（待机图）"""
    from module_1_core.animation import SPRITE_DIR
    idle_path = SPRITE_DIR / "idle_00.png"
    if idle_path.exists():
        return QPixmap(str(idle_path))
    return make_placeholder_sprite(PetState.IDLE, size=64)


# ── 气泡 ───────────────────────────

class TypingBubble(QWidget):
    """打字指示器气泡：三个弹跳圆点（等待 AI 回复时显示）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = 0
        self.setFixedSize(64, 34)
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(lambda: (setattr(self, "_t", self._t + 1), self.update()))
        self._timer.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor(AI_BUBBLE_A))
        grad.setColorAt(1, QColor(AI_BUBBLE_B))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(AI_BORDER, 1))
        path = _rounded_path(QRectF(TAIL_W, 0, self.width() - TAIL_W, self.height()), 6, BUBBLE_R, BUBBLE_R, BUBBLE_R)
        p.drawPath(path)
        p.drawPolygon(QPolygonF([QPointF(TAIL_W, 11), QPointF(0, 17), QPointF(TAIL_W, 23)]))
        # 三个弹跳圆点：相位差 0.6s
        for i in range(3):
            ph = (self._t + i * 6) % 18
            r = 3.5 + (1.5 if ph < 6 else 0)
            y = 17 + (4 - ph * 0.45 if ph < 9 else ph * 0.45 - 4) * 0.5
            p.setBrush(QBrush(QColor(ACCENT)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(14 + i * 13, y), r, r)

    def setText(self, text):
        pass  # 占位兼容：流式到达时由 ChatWindow 替换为普通气泡


class ChatBubble(QWidget):
    """尾巴气泡：渐变圆角矩形 + 三角尾巴，内部 QLabel 承载富文本"""

    def __init__(self, text="", is_user=False, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self._label = QLabel(text, self)
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.RichText)
        self._label.setStyleSheet(
            f"background: transparent; color: {TEXT_WHITE if is_user else TEXT_DARK}; font-size: 13px;")
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay = QVBoxLayout(self)
        if is_user:
            lay.setContentsMargins(14, 9, TAIL_W + 12, 9)
        else:
            lay.setContentsMargins(TAIL_W + 12, 9, 14, 9)
        lay.addWidget(self._label)
        self.setMaximumWidth(350)

    def setText(self, text):
        self._label.setText(text)

    def text(self):
        return self._label.text()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if self.is_user:
            rect = QRectF(0, 0, w - TAIL_W, h)
            path = _rounded_path(rect, BUBBLE_R, BUBBLE_R, 6, BUBBLE_R)
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0, QColor(USER_BUBBLE_A))
            grad.setColorAt(1, QColor(USER_BUBBLE_B))
            tail = [(w - TAIL_W, 16), (w, 22), (w - TAIL_W, 28)]
        else:
            rect = QRectF(TAIL_W, 0, w - TAIL_W, h)
            path = _rounded_path(rect, 6, BUBBLE_R, BUBBLE_R, BUBBLE_R)
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0, QColor(AI_BUBBLE_A))
            grad.setColorAt(1, QColor(AI_BUBBLE_B))
            tail = [(TAIL_W, 16), (0, 22), (TAIL_W, 28)]
        p.setPen(QPen(AI_BORDER if not self.is_user else QColor(255, 255, 255, 130), 1))
        p.setBrush(QBrush(grad))
        p.drawPath(path)
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in tail]))


# ── 输入条 ─────────────────────────

class InputBar(QWidget):
    """胶囊输入区：圆角白底输入框 + 圆形渐变发送钮"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        self._init_ui()

    def _init_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(10)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("跟鲸鱼娘说点什么…")
        self.input_edit.setMaximumHeight(40)
        self.input_edit.setMinimumHeight(36)
        self.input_edit.setStyleSheet(f"""
            QTextEdit {{
                background: #F4F8FE; color: {TEXT_DARK};
                border: 1.5px solid #C9D8EA; border-radius: 19px;
                padding: 6px 16px; font-size: 13px;
                placeholder-text-color: #AEB9C9;
            }}
            QTextEdit:hover {{ border-color: #B4CBE6; }}
            QTextEdit:focus {{ border-color: {ACCENT}; background: #FFFFFF; }}
        """)
        lay.addWidget(self.input_edit)

        self.send_btn = QPushButton("↑")
        self.send_btn.setFixedSize(40, 40)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {USER_BUBBLE_A}, stop:1 {USER_BUBBLE_B});
                color: white; border: none; border-radius: 20px;
                font-size: 18px; font-weight: bold;
            }}
            QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #6FC0FF, stop:1 {ACCENT}); }}
            QPushButton:pressed {{ background: #3D8BF0; }}
            QPushButton:disabled {{ background: #B9CDE8; }}
        """)
        lay.addWidget(self.send_btn)

    def set_send_handler(self, handler):
        self.send_btn.clicked.connect(handler)


# ── 主窗口 ─────────────────────────

class ChatWindow(QWidget):
    """聊天浮窗 — 深海主题卡片：header + 尾巴气泡消息区 + 胶囊输入区"""

    def __init__(self, config: ConfigManager = None, parent=None):
        super().__init__(parent)
        self.config = config or ConfigManager.instance()
        self.client = ApiClient(self.config)
        self.store = ConversationStore()
        self._streaming = False
        self._stream_buffer = ""
        self._drag_start = None
        self._ai_bubble = None

        self._init_ui()
        self._restore_last_conversation()

        self._stream_tick_signal.connect(self._on_stream_tick)
        self._stream_error_signal.connect(self._on_stream_error)
        self._stream_done_signal.connect(self._on_stream_done)

    # ── UI ────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle("深海鲸鱼娘")
        self.resize(WIN_W, WIN_H)
        self.setMinimumSize(MIN_W, MIN_H)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.92)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header ──
        self.header = QWidget()
        self.header.setFixedHeight(HEADER_H)
        self.header.setAttribute(Qt.WA_TranslucentBackground)
        h_lay = QHBoxLayout(self.header)
        h_lay.setContentsMargins(18, 0, 12, 0)
        h_lay.setSpacing(9)

        self._pet_label = QLabel()
        self._pet_label.setPixmap(_face_crop(_cached_pet_pix(), AVATAR_S))
        self._pet_label.setFixedSize(AVATAR_S, AVATAR_S)
        self._pet_label.setCursor(Qt.PointingHandCursor)
        self._pet_label.setToolTip("戳我一下嘛~")
        self._pet_label.mousePressEvent = self._pet_clicked
        h_lay.addWidget(self._pet_label)

        name_box = QVBoxLayout()
        name_box.setSpacing(0)
        name_lay = QHBoxLayout()
        name_lay.setSpacing(6)
        name = QLabel("深海鲸鱼娘")
        name.setStyleSheet(f"color: {TEXT_DARK}; font-size: 13px; font-weight: 700; background: transparent;")
        name_lay.addWidget(name)
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {ONLINE_GREEN}; border-radius: 4px;")
        name_lay.addWidget(dot)
        name_lay.addStretch(1)
        name_box.addLayout(name_lay)
        sub = QLabel("在线 · 尾巴摇啊摇")
        sub.setStyleSheet(f"color: #6B7A8F; font-size: 10px; background: transparent;")
        name_box.addWidget(sub)
        h_lay.addLayout(name_box)
        h_lay.addStretch(1)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(32, 32)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 235); color: #5A6B85;
                border: 1px solid rgba(74,158,255,60); border-radius: 16px; font-size: 13px;
            }
            QPushButton:hover { background: #FF6B6B; color: white; border-color: #FF6B6B; }
            QPushButton:pressed { background: #E85A5A; color: white; }
        """)
        self._close_btn.clicked.connect(self.hide)
        h_lay.addWidget(self._close_btn)

        # header 与消息区之间的淡分隔线
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: rgba(74,158,255,45);")
        root.addWidget(divider)

        # header 拖拽由 app 级 eventFilter 接管（filter 已覆盖 header 区域）
        root.addWidget(self.header)

        # ── 消息滚动区（透明）──
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: transparent; width: 5px; }
            QScrollBar::handle:vertical { background: rgba(120,160,210,110); border-radius: 2px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: rgba(74,158,255,160); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.scroll.viewport().setAttribute(Qt.WA_TranslucentBackground)
        self.scroll.viewport().setStyleSheet("background: transparent;")

        self.msg_w = QWidget()
        self.msg_w.setAttribute(Qt.WA_TranslucentBackground)
        self.msg_w.setStyleSheet("background: transparent;")
        self.msg_layout = QVBoxLayout(self.msg_w)
        self.msg_layout.setAlignment(Qt.AlignTop)
        self.msg_layout.setContentsMargins(16, 6, 16, 10)
        self.msg_layout.setSpacing(5)
        self.msg_layout.addStretch()
        self.scroll.setWidget(self.msg_w)
        root.addWidget(self.scroll, 1)

        # ── 输入区 ──
        self.input_bar = InputBar()
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(30, 60, 120, 40))
        self.input_bar.setGraphicsEffect(shadow)
        self.input_bar.input_edit.installEventFilter(self)
        self.input_bar.set_send_handler(self._send)
        root.addWidget(self.input_bar)

        # 全区域鼠标跟踪：让边缘 resize 光标覆盖整个窗口（含滚动区/输入区）
        self.setMouseTracking(True)
        for wgt in (self.scroll, self.msg_w, self.header, self.input_bar):
            wgt.setMouseTracking(True)
        self.scroll.viewport().setMouseTracking(True)
        # 窗口级事件过滤器：统一接管所有子区域的光标反馈
        from PySide6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

    # ── 卡片背景（含柔和阴影）──

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # 外阴影：多层递减透明度
        for i in range(7):
            m = 12 + i * 1.5
            p.setBrush(QColor(30, 70, 140, int(22 - i * 2.8)))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(m, m + 3, w - 2 * m, h - 2 * m), RADIUS + 3, RADIUS + 3)
        # 卡片主体：垂直渐变
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor(CARD_TOP))
        grad.setColorAt(1, QColor(CARD_BOTTOM))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(CARD_BORDER, 1))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), RADIUS, RADIUS)

    # ── 交互（拖拽 + 边缘自由调整大小）──

    def _edges_at(self, pos) -> Qt.Edges:
        """返回位置命中的可调整边缘（0 = 内部，可拖拽移动）"""
        edges = Qt.Edges()
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        if x <= EDGE:
            edges |= Qt.Edge.LeftEdge
        if x >= w - EDGE:
            edges |= Qt.Edge.RightEdge
        if y <= EDGE:
            edges |= Qt.Edge.TopEdge
        if y >= h - EDGE:
            edges |= Qt.Edge.BottomEdge
        return edges

    def mousePressEvent(self, event: QMouseEvent):
        # 拖拽/边缘调整已由 app 级 eventFilter 统一接管（见 eventFilter）
        pass

    def mouseMoveEvent(self, event: QMouseEvent):
        pass

    def mouseReleaseEvent(self, event: QMouseEvent):
        pass

    def _update_cursor(self, global_pos):
        """按鼠标位置更新窗口光标（边缘 → resize 箭头；内部 → 默认）"""
        edges = self._edges_at(self.mapFromGlobal(global_pos))
        if edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
            shape = Qt.SizeHorCursor
        elif edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
            shape = Qt.SizeVerCursor
        elif edges in (Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge):
            shape = Qt.SizeFDiagCursor
        elif edges in (Qt.Edge.RightEdge | Qt.Edge.TopEdge, Qt.Edge.LeftEdge | Qt.Edge.BottomEdge):
            shape = Qt.SizeBDiagCursor
        else:
            shape = Qt.ArrowCursor
        if self.cursor().shape() != shape:
            self.setCursor(shape)

    def _pet_clicked(self, event=None):
        if not self._streaming:
            self._add_bubble("（被戳了一下，尾巴轻轻摆了摆~）", False)

    # ── 消息区 ────────────────────────────

    def _restore_last_conversation(self):
        if self.store.current_id and self.store.get(self.store.current_id):
            self._load_messages(self.store.current_id)
        elif self.store.has_conversations():
            conv = self.store.list_all()[0]
            self.store.current_id = conv.id
            self._load_messages(conv.id)
        else:
            self._add_bubble("嘿～我是深海鲸鱼娘！<br>想聊什么呀？", False)

    def _load_messages(self, conv_id: str):
        conv = self.store.get(conv_id)
        self._clear_messages()
        if conv:
            for msg in conv.messages:
                self._add_bubble(msg["content"], msg["role"] == "user", _scroll=False)
        self._scroll_bottom()

    def _clear_messages(self):
        while self.msg_layout.count():
            item = self.msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.msg_layout.addStretch()

    def _add_bubble(self, text: str, is_user: bool, _scroll=True):
        # 行容器：头像 + 气泡（用户镜像）
        row = QWidget()
        row.setAttribute(Qt.WA_TranslucentBackground)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 3, 0, 3)
        lay.setSpacing(8)
        bubble = ChatBubble(text, is_user)
        if is_user:
            lay.addStretch(1)
            lay.addWidget(bubble)
            av = QLabel()
            av.setPixmap(_user_avatar())
            av.setFixedSize(MSG_AVATAR, MSG_AVATAR)
            lay.addWidget(av)
        else:
            av = QLabel()
            av.setPixmap(_ai_avatar())
            av.setFixedSize(MSG_AVATAR, MSG_AVATAR)
            lay.addWidget(av)
            lay.addWidget(bubble)
            lay.addStretch(1)

        # 淡入动画
        eff = QGraphicsOpacityEffect(row)
        row.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", row)
        anim.setDuration(160)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        row._fade = anim

        self.msg_layout.takeAt(self.msg_layout.count() - 1)
        self.msg_layout.addWidget(row)
        self.msg_layout.addStretch()
        if _scroll:
            QTimer.singleShot(50, self._scroll_bottom)
        return bubble

    def _scroll_bottom(self):
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _add_typing(self):
        """添加打字指示器行，返回 indicator（首 token 到达时替换为真实气泡）"""
        row = QWidget()
        row.setAttribute(Qt.WA_TranslucentBackground)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 3, 0, 3)
        lay.setSpacing(8)
        av = QLabel()
        av.setPixmap(_ai_avatar())
        av.setFixedSize(MSG_AVATAR, MSG_AVATAR)
        lay.addWidget(av)
        typing = TypingBubble()
        lay.addWidget(typing)
        lay.addStretch(1)
        self.msg_layout.takeAt(self.msg_layout.count() - 1)
        self.msg_layout.addWidget(row)
        self.msg_layout.addStretch()
        self._typing_row = row
        self._typing_lay = lay
        QTimer.singleShot(50, self._scroll_bottom)
        return typing

    def _replace_typing(self, text=""):
        """把打字指示器行替换成普通 AI 气泡（流式开始或出错时）"""
        if not getattr(self, "_typing_row", None) or self._typing_row.layout() is None:
            return
        bubble = ChatBubble(text, False)
        idx = self._typing_lay.indexOf(self._ai_bubble)
        if idx >= 0:
            self._typing_lay.takeAt(idx)
        self._ai_bubble.deleteLater()
        self._typing_lay.insertWidget(idx if idx >= 0 else 1, bubble)
        self._ai_bubble = bubble
        self._typing_row = None

    # ── 发送 ──────────────────────────────

    def _send(self):
        if self._streaming:
            return
        text = self.input_bar.input_edit.toPlainText().strip()
        if not text:
            return
        if not self.client.is_configured:
            QMessageBox.warning(self, "提示", "请先在托盘菜单中设置 API Key")
            return

        self.input_bar.input_edit.clear()
        self.input_bar.input_edit.setEnabled(False)
        self.input_bar.send_btn.setEnabled(False)

        if not self.store.current_id:
            self.store.create()

        self._add_bubble(text, True)
        self.store.add_message(self.store.current_id, "user", text)
        self._ai_bubble = self._add_typing()

        self._streaming = True
        self._stream_buffer = ""
        threading.Thread(target=self._stream_api, daemon=True).start()

    def _stream_api(self):
        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            messages += self.store.get_history(self.store.current_id)
            for token in self.client.chat_stream(messages):
                self._stream_buffer += token
                self._stream_tick_signal.emit(token)
        except ApiAuthError as e:
            self._stream_error_signal.emit(f"🔑 {e}")
        except ApiQuotaError as e:
            self._stream_error_signal.emit(f"💰 {e}")
        except ApiRateLimitError as e:
            self._stream_error_signal.emit(f"⏳ {e}")
        except ApiNetworkError as e:
            self._stream_error_signal.emit(f"🌐 {e}")
        except ApiConfigError as e:
            self._stream_error_signal.emit(f"⚙ {e}")
        except Exception as e:
            self._stream_error_signal.emit(f"出错了: {e}")
        finally:
            self._stream_done_signal.emit()

    _stream_tick_signal = Signal(str)
    _stream_error_signal = Signal(str)
    _stream_done_signal = Signal()

    def _on_stream_tick(self, token: str):
        if isinstance(self._ai_bubble, TypingBubble):
            self._replace_typing()
        if self._ai_bubble:
            t = token.replace("\n", "<br>")
            self._ai_bubble.setText(self._ai_bubble.text() + t)
        QTimer.singleShot(80, self._scroll_bottom)

    def _on_stream_error(self, msg: str):
        if isinstance(self._ai_bubble, TypingBubble):
            self._replace_typing(msg)
        elif self._ai_bubble:
            self._ai_bubble.setText(msg)

    def _on_stream_done(self):
        self._streaming = False
        self.input_bar.input_edit.setEnabled(True)
        self.input_bar.send_btn.setEnabled(True)
        if self._stream_buffer:
            self.store.add_message(self.store.current_id, "assistant", self._stream_buffer)
            self._stream_buffer = ""
        self.input_bar.input_edit.setFocus()

    # ── 事件过滤（app 级）：全区域拖拽 / 边缘 resize / 光标反馈 / 快捷键 ──

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QWidget
        if isinstance(obj, QWidget) and (obj is self or self.isAncestorOf(obj)):
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                gp = event.globalPosition().toPoint()
                edges = self._edges_at(self.mapFromGlobal(gp))
                if edges and self.windowHandle():
                    # 边缘按下 → 系统原生 resize（覆盖滚动区/输入区边缘）
                    self.windowHandle().startSystemResize(edges)
                    event.accept()
                    return True
                if obj in (self.scroll.viewport(), self.msg_w, self.header):
                    # 空白区按下 → 拖拽移动（输入框/气泡/按钮不拦截，防误拖）
                    self._drag_start = gp
                    self.setCursor(Qt.SizeAllCursor)
                    event.accept()
                    return True
            elif event.type() == QEvent.MouseMove:
                if event.buttons() & Qt.LeftButton and self._drag_start:
                    delta = event.globalPosition().toPoint() - self._drag_start
                    self.move(self.pos() + delta)
                    self._drag_start = event.globalPosition().toPoint()
                    event.accept()
                    return True
                if not event.buttons():
                    self._update_cursor(event.globalPosition().toPoint())
            elif event.type() == QEvent.MouseButtonRelease and not event.buttons():
                self._drag_start = None
                self._update_cursor(event.globalPosition().toPoint())
        if obj == self.input_bar.input_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and event.modifiers() & Qt.ControlModifier:
                self._send()
                return True
        return super().eventFilter(obj, event)

    # ── 打招呼 ────────────────────────────

    def show_greeting(self):
        if not self.client.is_configured:
            return
        msg = get_random_greeting(self.config.api_type)
        self._add_bubble(msg, False)
        if self.store.current_id:
            self.store.add_message(self.store.current_id, "assistant", msg)
