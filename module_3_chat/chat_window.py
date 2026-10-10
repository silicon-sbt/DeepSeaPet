"""聊天窗口 — 深海主题卡片式 UI：header + 尾巴气泡消息区 + 胶囊输入区

主题常量与绘制工具在 theme.py，三种自定义控件在 widgets.py；
这里只留窗口本身（布局、拖拽/resize、流式收发、会话切换）。
"""
import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QPushButton, QLabel, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QTimer, QEvent, QPropertyAnimation, QEasingCurve, QRectF
from PySide6.QtGui import QColor, QPainter, QMouseEvent, QLinearGradient, QBrush, QPen

from module_2_api.config_manager import ConfigManager
from module_2_api.api_client import (
    ApiClient, ApiConfigError, ApiAuthError, ApiQuotaError, ApiRateLimitError, ApiNetworkError,
)
from module_3_chat.conversation_store import ConversationStore
from module_3_chat.greeting import get_random_greeting
# 主题与控件显式再导出：外部（含测试）仍可从本模块 import 这些名字
from module_3_chat.theme import (  # noqa: F401
    WIN_W, WIN_H, MIN_W, MIN_H, EDGE, RADIUS, HEADER_H, AVATAR_S, MSG_AVATAR, TAIL_W, BUBBLE_R,
    CARD_TOP, CARD_BOTTOM, CARD_BORDER, AI_BUBBLE_A, AI_BUBBLE_B, AI_BORDER,
    USER_BUBBLE_A, USER_BUBBLE_B, TEXT_DARK, TEXT_WHITE, TEXT_SUB, ACCENT, ONLINE_GREEN,
    _face_crop, _cached_pet_pix, _ai_avatar, _user_avatar,
)
from module_3_chat.widgets import ChatBubble, TypingBubble, InputBar  # noqa: F401

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
        # 恢复上次调整过的窗口尺寸（钳到最小尺寸以上）
        self.resize(max(MIN_W, int(self.config.chat_w)),
                    max(MIN_H, int(self.config.chat_h)))
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

        self._new_btn = QPushButton("＋")
        self._new_btn.setToolTip("开一段新对话")
        self._new_btn.setFixedSize(32, 32)
        self._new_btn.setCursor(Qt.PointingHandCursor)
        self._new_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 235); color: #4A9EFF;
                border: 1px solid rgba(74,158,255,60); border-radius: 16px; font-size: 16px;
            }
            QPushButton:hover { background: #EAF3FF; border-color: #4A9EFF; }
            QPushButton:pressed { background: #D6E9FF; }
        """)
        self._new_btn.clicked.connect(self._new_conversation)
        h_lay.addWidget(self._new_btn)

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
            self._add_bubble("嘿～我是深海鲸鱼娘！\n想聊什么呀？", False)

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
        old = self._ai_bubble
        idx = self._typing_lay.indexOf(old) if old is not None else -1
        if idx >= 0:
            self._typing_lay.takeAt(idx)     # 先摘出布局，再删，避免留下悬空项
        bubble = ChatBubble(text, False)
        self._typing_lay.insertWidget(idx if idx >= 0 else 1, bubble)
        if old is not None:
            old.deleteLater()
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
            # worker 线程已把 token 累进 _stream_buffer，直接用它重设文本：
            # ChatBubble 内部负责转义，从 QLabel 读回再拼等于每 token 重建一次富文本
            self._ai_bubble.setText(self._stream_buffer)
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

    # ── 会话切换 / 尺寸持久化 ──────────────

    def _new_conversation(self):
        """开新对话：新建会话 + 清空消息区 + 重新打个招呼"""
        if self._streaming:
            return
        self.store.create()
        self._clear_messages()
        self._add_bubble(get_random_greeting(self.config.api_type or "deepseek"), False)

    def hideEvent(self, event):
        # 只在隐藏时落盘一次：写在 resizeEvent 里会变成每像素一次 JSON 写
        self.config.chat_w = self.width()
        self.config.chat_h = self.height()
        super().hideEvent(event)

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
