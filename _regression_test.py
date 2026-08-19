# -*- coding: utf-8 -*-
"""回归测试：关闭按钮 / resize / 拖拽 / 流式替换 / 消息管理"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import time

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase, QMouseEvent
from PySide6.QtCore import Qt, QPoint, QEvent, QPointF, QTimer
from PySide6.QtTest import QTest

app = QApplication(sys.argv)
for f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei", 10))

from module_3_chat.chat_window import ChatWindow, ChatBubble, TypingBubble, MIN_W, MIN_H, WIN_W, WIN_H, EDGE

PASS = []
FAIL = []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name, detail)


class FakeStore:
    def __init__(self):
        self.current_id = None
        self.messages = []
    def create(self):
        self.current_id = "t1"
    def add_message(self, cid, role, content):
        self.messages.append((role, content))
    def get_history(self, cid):
        return [{"role": r, "content": c} for r, c in self.messages]
    def get(self, cid):
        return None
    def has_conversations(self):
        return False
    def list_all(self):
        return []


# ── 1. 创建与基本尺寸 ──
w = ChatWindow()
w.store = FakeStore()
w._clear_messages()
w.show()
app.processEvents()
check("初始尺寸", w.width() == WIN_W and w.height() == WIN_H, f"{w.width()}x{w.height()}")
check("最小尺寸设置", w.minimumWidth() == MIN_W and w.minimumHeight() == MIN_H)

# ── 2. 关闭按钮 ──
QTest.mouseClick(w._close_btn, Qt.LeftButton)
app.processEvents()
check("关闭按钮点击→隐藏", not w.isVisible())
w.show()
app.processEvents()

# ── 3. 消息管理 ──
b1 = w._add_bubble("你好呀", False)
b2 = w._add_bubble("在吗", True)
check("气泡添加", isinstance(b1, ChatBubble) and isinstance(b2, ChatBubble))
check("气泡文本", b1.text() == "你好呀" and b2.text() == "在吗")
w._clear_messages()
check("清空消息", w.msg_layout.count() == 1)  # 只剩 stretch

# ── 4. 流式流程（TypingBubble 替换）──
import types
w.client = types.SimpleNamespace(is_configured=True, chat_stream=lambda messages: iter(["你", "好", "呀"]))
w.input_bar.input_edit.setPlainText("测试消息")
w._send()
deadline = time.time() + 5
while w._streaming and time.time() < deadline:
    app.processEvents()
    time.sleep(0.02)
app.processEvents()
check("流式完成后替换为普通气泡", isinstance(w._ai_bubble, ChatBubble), type(w._ai_bubble).__name__)
check("流式内容拼接", w._ai_bubble.text() == "你好呀", w._ai_bubble.text())
check("流式存盘", ("assistant", "你好呀") in w.store.messages, str(w.store.messages))
check("输入框恢复", w.input_bar.input_edit.isEnabled() and w.input_bar.send_btn.isEnabled())

# ── 5. 流式错误路径（TypingBubble → 错误文本）──
w._clear_messages()
w.client = types.SimpleNamespace(is_configured=True,
    chat_stream=lambda messages: (_ for _ in ()).throw(RuntimeError("boom")))
w.input_bar.input_edit.setPlainText("再测")
w._send()
deadline = time.time() + 5
while w._streaming and time.time() < deadline:
    app.processEvents()
    time.sleep(0.02)
app.processEvents()
check("错误路径替换气泡", isinstance(w._ai_bubble, ChatBubble))
check("错误文本显示", "出错了" in w._ai_bubble.text(), w._ai_bubble.text())
check("错误不存盘", not any(role == "assistant" and "boom" in content for role, content in w.store.messages), str(w.store.messages))

# ── 6. resize ──
w.resize(720, 620)
app.processEvents()
check("放大窗口", w.width() == 720 and w.height() == 620)
check("放大后布局正常", w.msg_layout.count() >= 1)
w.resize(300, 260)
app.processEvents()
check("小于最小尺寸被钳制", w.width() >= MIN_W and w.height() >= MIN_H, f"{w.width()}x{w.height()}")
w.resize(WIN_W, WIN_H)
app.processEvents()

# ── 7. 边缘检测 ──
W, H = w.width(), w.height()
check("左边缘", w._edges_at(QPoint(0, H // 2)) == Qt.Edge.LeftEdge)
check("右边缘", w._edges_at(QPoint(W - 1, H // 2)) == Qt.Edge.RightEdge)
check("上边缘", w._edges_at(QPoint(W // 2, 0)) == Qt.Edge.TopEdge)
check("下边缘", w._edges_at(QPoint(W // 2, H - 1)) == Qt.Edge.BottomEdge)
check("左上角", w._edges_at(QPoint(0, 0)) == (Qt.Edge.LeftEdge | Qt.Edge.TopEdge))
check("内部=0", w._edges_at(QPoint(W // 2, H // 2)) == Qt.Edges())
check("边缘外非边缘", w._edges_at(QPoint(EDGE + 5, H // 2)) == Qt.Edges())

# ── 8. 拖拽（统一走 app 级事件过滤器）──

def send_press(lx, ly, target=None):
    gp = w.mapToGlobal(QPoint(lx, ly))
    ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(lx, ly), QPointF(gp),
                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(target if target is not None else w.scroll.viewport(), ev)
    app.processEvents()

def send_release(lx, ly, target=None):
    gp = w.mapToGlobal(QPoint(lx, ly))
    ev = QMouseEvent(QEvent.MouseButtonRelease, QPointF(lx, ly), QPointF(gp),
                     Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
    QApplication.sendEvent(target if target is not None else w.scroll.viewport(), ev)
    app.processEvents()

def send_drag_move(lx, ly, target=None):
    gp = w.mapToGlobal(QPoint(lx, ly))
    ev = QMouseEvent(QEvent.MouseMove, QPointF(lx, ly), QPointF(gp),
                     Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(target if target is not None else w.scroll.viewport(), ev)
    app.processEvents()

w.move(100, 100)
app.processEvents()
before = w.pos()
send_press(W // 2, H // 2)  # 滚动区空白按下
send_drag_move(W // 2 + 40, H // 2 + 25)
send_release(W // 2 + 40, H // 2 + 25)
check("滚动区拖拽移动窗口", w.pos().x() == before.x() + 40 and w.pos().y() == before.y() + 25,
      f"{before} -> {w.pos()}")
# header 拖拽（filter 拦截 header 空白按下）
w.move(100, 100)
app.processEvents()
before = w.pos()
send_press(200, 20, w.header)
send_drag_move(240, 20, w.header)
send_release(240, 20, w.header)
check("header 拖拽", w.pos().x() == 140 and w.pos().y() == 100, f"pos={w.pos()}")

# ── 9. Ctrl+Enter ──
w.client = types.SimpleNamespace(is_configured=True, chat_stream=lambda messages: iter(["ok"]))
w.store = FakeStore()
w._clear_messages()
w.input_bar.input_edit.setPlainText("回车测试")
from PySide6.QtGui import QKeyEvent
key = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.ControlModifier)
check("eventFilter 拦截 Ctrl+Enter", w.eventFilter(w.input_bar.input_edit, key) is True)
w._send()
deadline = time.time() + 5
while w._streaming and time.time() < deadline:
    app.processEvents()
    time.sleep(0.02)
app.processEvents()
check("Ctrl+Enter 发送", ("user", "回车测试") in w.store.messages, str(w.store.messages))

# ── 10. 光标反馈 + app 级事件过滤路径 ──
w.move(100, 100)
w.resize(WIN_W, WIN_H)
app.processEvents()
W, H = w.width(), w.height()

def send_move(lx, ly, target=None):
    gp = w.mapToGlobal(QPoint(lx, ly))
    ev = QMouseEvent(QEvent.MouseMove, QPointF(lx, ly), QPointF(gp),
                     Qt.NoButton, Qt.NoButton, Qt.NoModifier)
    QApplication.sendEvent(target if target is not None else w.scroll.viewport(), ev)
    app.processEvents()

# 悬停右边缘 → 水平 resize 光标（经滚动区 viewport 传递）
send_move(W - 2, H // 2)
check("右边缘光标 SizeHor", w.cursor().shape() == Qt.SizeHorCursor, str(w.cursor().shape()))
# 悬停下边缘 → 垂直 resize 光标（经输入区传递）
send_move(W // 2, H - 2, w.input_bar)
check("下边缘光标 SizeVer", w.cursor().shape() == Qt.SizeVerCursor, str(w.cursor().shape()))
# 悬停左上角 → 对角光标
send_move(2, 2)
check("左上角光标 SizeFDiag", w.cursor().shape() == Qt.SizeFDiagCursor, str(w.cursor().shape()))
# 悬停内部 → 箭头
send_move(W // 2, H // 2)
check("内部光标 Arrow", w.cursor().shape() == Qt.ArrowCursor, str(w.cursor().shape()))
# 空白按下 → SizeAll + 拖拽移动（app filter 路径）
w.move(150, 150); app.processEvents()
before = w.pos()
send_press(W // 2, H // 2)  # 内部按下 → 拖拽
check("按下光标 SizeAll", w.cursor().shape() == Qt.SizeAllCursor)
gp = w.mapToGlobal(QPoint(W // 2 + 30, H // 2 + 20))
mv = QMouseEvent(QEvent.MouseMove, QPointF(W // 2 + 30, H // 2 + 20), QPointF(gp),
                 Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(w.scroll.viewport(), mv)
app.processEvents()
check("filter路径拖拽移动", w.pos().x() == before.x() + 30 and w.pos().y() == before.y() + 20, f"{before}->{w.pos()}")
send_release(W // 2 + 30, H // 2 + 20)
# 输入框内按下 → 不拦截（不进入拖拽，输入框保留焦点）
w.input_bar.input_edit.setFocus()
focus_before = w.input_bar.input_edit.hasFocus()
send_press(100, H - 30, w.input_bar.input_edit)  # 输入框内（非边缘）
check("输入框按下不拖拽", w._drag_start is None, str(w._drag_start))
# 边缘按下（windowHandle 不可用时降级不崩溃）
orig_wh = w.windowHandle
w.windowHandle = lambda: None
send_press(W - 2, H // 2)  # 右边缘 press
check("边缘按下无handle不崩溃", True)
w.windowHandle = orig_wh

# ── 汇总 ──
print(f"\n===== {len(PASS)} PASS / {len(FAIL)} FAIL =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("ALL GREEN")
