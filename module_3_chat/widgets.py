"""聊天窗的三种自定义控件：打字指示器 / 尾巴气泡 / 胶囊输入区"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QTextEdit, QPushButton)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QPolygonF

from module_3_chat.theme import (AI_BUBBLE_A, AI_BUBBLE_B, AI_BORDER, USER_BUBBLE_A,
                                 USER_BUBBLE_B, TEXT_DARK, TEXT_WHITE, ACCENT,
                                 TAIL_W, BUBBLE_R, rounded_path, to_html)


class TypingBubble(QWidget):
    """打字指示器气泡：三个弹跳圆点（等待 AI 回复时显示）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = 0
        self.setFixedSize(64, 34)
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        self._t += 1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor(AI_BUBBLE_A))
        grad.setColorAt(1, QColor(AI_BUBBLE_B))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(AI_BORDER, 1))
        path = rounded_path(QRectF(TAIL_W, 0, self.width() - TAIL_W, self.height()),
                            6, BUBBLE_R, BUBBLE_R, BUBBLE_R)
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


class ChatBubble(QWidget):
    """尾巴气泡：渐变圆角矩形 + 三角尾巴，内部 QLabel 承载富文本

    对外暴露的 text() 始终是原始文本；转义只发生在渲染那一步。
    """

    def __init__(self, text="", is_user=False, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self._raw = ""
        self._label = QLabel(self)
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
        self.setText(text)

    def setText(self, text):
        self._raw = text
        self._label.setText(to_html(text))

    def text(self):
        return self._raw

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if self.is_user:
            rect = QRectF(0, 0, w - TAIL_W, h)
            path = rounded_path(rect, BUBBLE_R, BUBBLE_R, 6, BUBBLE_R)
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0, QColor(USER_BUBBLE_A))
            grad.setColorAt(1, QColor(USER_BUBBLE_B))
            tail = [(w - TAIL_W, 16), (w, 22), (w - TAIL_W, 28)]
        else:
            rect = QRectF(TAIL_W, 0, w - TAIL_W, h)
            path = rounded_path(rect, 6, BUBBLE_R, BUBBLE_R, BUBBLE_R)
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0, QColor(AI_BUBBLE_A))
            grad.setColorAt(1, QColor(AI_BUBBLE_B))
            tail = [(TAIL_W, 16), (0, 22), (TAIL_W, 28)]
        p.setPen(QPen(AI_BORDER if not self.is_user else QColor(255, 255, 255, 130), 1))
        p.setBrush(QBrush(grad))
        p.drawPath(path)
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in tail]))


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
