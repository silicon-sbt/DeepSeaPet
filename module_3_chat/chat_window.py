"""聊天窗口 — 透明消息区 + 底部圆角输入条 + 左上角趴姿鲸鱼娘"""
import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QTextEdit, QPushButton, QLabel, QGraphicsDropShadowEffect,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QMouseEvent, QPen, QBrush

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

# ── 配色 ──────────────────────────────────
BORDER_BLUE  = "#4A9EFF"
BG_WHITE     = "#FFFFFF"
TEXT_DARK    = "#2C3E50"
TEXT_WHITE   = "#FFFFFF"
BUBBLE_BLUE  = "#5CA0F2"
BUBBLE_GRAY  = "#F0F4F8"
INPUT_BORDER = "#D0D8E4"

WIN_W    = 500
WIN_H    = 380
BAR_H    = 44         # 输入框本身高度
PET_H    = 28         # 输入条上方留给鲸鱼娘的高度
BAR_PAD  = 4          # 输入条左右/下边距
RADIUS   = 22
PET_SIZE = 72
PET_SLOT = 56         # 左侧留给鲸鱼娘的宽度
PET_Y_OFF = 20        # 鲸鱼娘垂直偏移（跟输入条重叠量）
# input bar 内部边距微调
IB_L = BAR_PAD + 12   # 输入条内容左边距
IB_T = PET_H + 6      # 输入条内容上边距
IB_R = BAR_PAD + 8    # 输入条内容右边距
IB_B = BAR_PAD + 2    # 输入条内容下边距


class InputBar(QWidget):
    """底部输入条 — 圆角蓝边白底，左上角留空给鲸鱼娘"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(BAR_H + PET_H + BAR_PAD)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        left = PET_SLOT
        r = QRectF(left, PET_H, self.width() - left - BAR_PAD, BAR_H)
        p.setBrush(QBrush(QColor(BG_WHITE)))
        p.setPen(QPen(QColor(BORDER_BLUE), 3))
        p.drawRoundedRect(r, RADIUS, RADIUS)


from PySide6.QtGui import QPixmap as _QPixmap

_pet_pixmap_cache = None

def _cached_pet_pix():
    global _pet_pixmap_cache
    if _pet_pixmap_cache is None:
        from module_1_core.animation import SPRITE_DIR
        lying_path = SPRITE_DIR / "lying_00.png"
        if lying_path.exists():
            _pet_pixmap_cache = _QPixmap(str(lying_path)).scaled(
                PET_SIZE, PET_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            _pet_pixmap_cache = make_placeholder_sprite(PetState.LYING, size=PET_SIZE).scaled(
                PET_SIZE, PET_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return _pet_pixmap_cache


class ChatBubble(QLabel):
    """消息气泡"""
    def __init__(self, text="", is_user=False, parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)
        self.setMaximumWidth(380)
        if is_user:
            self.setStyleSheet(f"""
                background: {BUBBLE_BLUE}; color: {TEXT_WHITE};
                border-radius: 12px; padding: 6px 12px;
                font-size: 12px; margin: 2px 8px 2px 60px;
            """)
        else:
            self.setStyleSheet(f"""
                background: {BUBBLE_GRAY}; color: {TEXT_DARK};
                border-radius: 12px; padding: 6px 12px;
                font-size: 12px; margin: 2px 60px 2px 8px;
            """)


class ChatWindow(QWidget):
    """聊天浮窗 — 透明消息区 + 底部圆角输入条 + 左上角趴姿"""

    def __init__(self, config: ConfigManager = None, parent=None):
        super().__init__(parent)
        self.config = config or ConfigManager.instance()
        self.client = ApiClient(self.config)
        self.store = ConversationStore()
        self._streaming = False
        self._stream_buffer = ""
        self._drag_start = None

        self._init_ui()
        self._init_pet()
        self._restore_last_conversation()

        self._stream_tick_signal.connect(self._on_stream_tick)
        self._stream_error_signal.connect(self._on_stream_error)
        self._stream_done_signal.connect(self._on_stream_done)

    # ── UI ────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle("深海鲸鱼娘")
        self.setFixedSize(WIN_W, WIN_H)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.8)

        # 根布局
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 消息滚动区（透明背景）──
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: transparent; width: 4px; }
            QScrollBar::handle:vertical { background: rgba(180,200,220,120); border-radius: 2px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.scroll.viewport().setAttribute(Qt.WA_TranslucentBackground)
        self.scroll.viewport().setStyleSheet("background: transparent;")

        self.msg_w = QWidget()
        self.msg_w.setAttribute(Qt.WA_TranslucentBackground)
        self.msg_w.setStyleSheet("background: transparent;")
        self.msg_layout = QVBoxLayout(self.msg_w)
        self.msg_layout.setAlignment(Qt.AlignTop)
        self.msg_layout.setContentsMargins(PET_SLOT, 8, 12, 8)
        self.msg_layout.setSpacing(4)
        self.msg_layout.addStretch()
        self.scroll.setWidget(self.msg_w)
        root.addWidget(self.scroll)

        # ── 底部输入条 ──
        self.input_bar = InputBar()
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 25))
        self.input_bar.setGraphicsEffect(shadow)

        bar_layout = QHBoxLayout(self.input_bar)
        bar_layout.setContentsMargins(IB_L, IB_T, IB_R, IB_B)
        bar_layout.setSpacing(6)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("跟鲸鱼娘说点什么…")
        self.input_edit.setMaximumHeight(32)
        self.input_edit.setMinimumHeight(28)
        self.input_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {BG_WHITE}; color: {TEXT_DARK};
                border: 1px solid {INPUT_BORDER}; border-radius: 14px;
                padding: 4px 12px; font-size: 12px;
            }}
            QTextEdit:focus {{ border-color: {BORDER_BLUE}; }}
        """)
        self.input_edit.installEventFilter(self)
        bar_layout.addWidget(self.input_edit)

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(52, 28)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {BORDER_BLUE}; color: white;
                border-radius: 14px; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #3A8AE8; }}
            QPushButton:disabled {{ background: #B0C8E0; }}
        """)
        self.send_btn.clicked.connect(self._send)
        bar_layout.addWidget(self.send_btn)

        root.addWidget(self.input_bar)

        # ── 右上角关闭按钮（无边框窗口无系统关闭钮）──
        self._close_btn = QPushButton("✕", self)
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.move(WIN_W - 30, 6)
        self._close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 180); color: #8A94A6;
                border: none; border-radius: 12px; font-size: 12px;
            }
            QPushButton:hover { background: #E86A6A; color: white; }
        """)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.clicked.connect(self.hide)

    # ── 左上角趴姿角色（叠在输入条左上方）──

    def _init_pet(self):
        # 叠在输入条左上方
        bar_top = WIN_H - self.input_bar.height()
        self._pet_label = QLabel(self)
        self._pet_label.setPixmap(_cached_pet_pix())
        self._pet_label.setFixedSize(PET_SIZE, PET_SIZE)
        self._pet_label.move(4, bar_top - PET_SIZE + PET_Y_OFF)
        self._pet_label.setToolTip("鲸鱼娘在看着你呢~")
        self._pet_label.mousePressEvent = self._pet_clicked

    def _pet_clicked(self, event=None):
        if not self._streaming:
            self._add_bubble("（被戳了一下，尾巴轻轻摆了摆~）", False)

    # ── 拖拽 ──────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton and self._drag_start:
            delta = event.globalPosition().toPoint() - self._drag_start
            self.move(self.pos() + delta)
            self._drag_start = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_start = None

    # ── 对话 ──────────────────────────────

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
        bubble = ChatBubble(text, is_user)
        bubble.setAlignment(Qt.AlignRight if is_user else Qt.AlignLeft)
        self.msg_layout.takeAt(self.msg_layout.count() - 1)
        self.msg_layout.addWidget(bubble)
        self.msg_layout.addStretch()
        if _scroll:
            QTimer.singleShot(50, self._scroll_bottom)
        return bubble

    def _scroll_bottom(self):
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── 发送 ──────────────────────────────

    def _send(self):
        if self._streaming:
            return
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        if not self.client.is_configured:
            QMessageBox.warning(self, "提示", "请先在托盘菜单中设置 API Key")
            return

        self.input_edit.clear()
        self.input_edit.setEnabled(False)
        self.send_btn.setEnabled(False)

        if not self.store.current_id:
            self.store.create()

        self._add_bubble(text, True)
        self.store.add_message(self.store.current_id, "user", text)
        self._ai_bubble = self._add_bubble("…", False)

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
        if self._ai_bubble:
            # 增量追加，避免每 token 重建全量 HTML
            t = token.replace("\n", "<br>")
            self._ai_bubble.setText(self._ai_bubble.text() + t)
        # ponytail: 滚动节流，用单次延迟代替每次即时滚动
        QTimer.singleShot(80, self._scroll_bottom)

    def _on_stream_error(self, msg: str):
        if self._ai_bubble:
            self._ai_bubble.setText(msg)
        # 不存盘——错误消息不应进入对话历史

    def _on_stream_done(self):
        self._streaming = False
        self.input_edit.setEnabled(True)
        self.send_btn.setEnabled(True)
        if self._stream_buffer:
            self.store.add_message(self.store.current_id, "assistant", self._stream_buffer)
            self._stream_buffer = ""
        self.input_edit.setFocus()

    # ── 快捷键 ────────────────────────────

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj == self.input_edit and event.type() == QEvent.KeyPress:
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
