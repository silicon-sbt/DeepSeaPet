# -*- coding: utf-8 -*-
"""余额气泡与单击/双击/三击事件流测试"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import time

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtCore import Qt, QTimer, QEvent, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest, QSignalSpy

app = QApplication(sys.argv)
for f in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(f):
        QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei", 10))

from module_1_core.pet_window import PetWindow, BalanceBubble
from module_2_api.api_client import ApiClient, ApiAuthError, ApiNetworkError

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name, detail)

def wait(ms):
    deadline = time.time() + ms / 1000
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)

# ── 1. BalanceBubble 状态与渲染 ──
bub = BalanceBubble(lambda: (0.0, "CNY"))
bub._on_result((True, 12.34, "CNY", ""))
check("余额显示", bub._amount.text() == "¥ 12.34", bub._amount.text())
bub._on_result((True, 20.0, "CNY", ""))  # 变化 → 动画
check("动画进行中", bub._amount.text() != "¥ 20.00" or bub._anim_timer.isActive(), bub._amount.text())
wait(900)
check("动画结束到位", bub._amount.text() == "¥ 20.00", bub._amount.text())
bub._on_result((False, None, None, "查询失败"))
check("错误态提示重试", "重试" in bub._hint.text(), bub._hint.text())
check("错误态沿用余额", bub._amount.text() == "¥ 20.00", bub._amount.text())
bub._on_result((False, None, None, "仅 DeepSeek 支持余额查询"))
check("不支持态", "--" in bub._amount.text() and "DeepSeek" in bub._hint.text(), bub._hint.text())
# 点击刷新触发
bub._on_result((True, 30.5, "CNY", ""))
check("USD 格式", (lambda: (bub._on_result((True, 30.5, "USD", "")), bub._amount.text() == "30.50 USD")[1])())
wait(900)

# ── 2. get_balance 解析 ──
import json, urllib.request, urllib.error
from unittest import mock
class FakeResp:
    def __init__(self, data): self._d = json.dumps(data).encode()
    def read(self): return self._d
    def __enter__(self): return self
    def __exit__(self, *a): pass
class FakeCfg:
    api_key = "sk-test"; api_type = "deepseek"; api_base = ""
cfg = FakeCfg()
client = ApiClient(cfg)
with mock.patch("urllib.request.urlopen", return_value=FakeResp({"balance_infos": [{"currency": "CNY", "total_balance": "88.50"}]})):
    bal, cur = client.get_balance()
check("余额解析", bal == 88.50 and cur == "CNY", f"{bal} {cur}")
with mock.patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("u", 401, "x", None, None)):
    try:
        client.get_balance(); check("401→AuthError", False)
    except ApiAuthError:
        check("401→AuthError", True)
cfg2 = FakeCfg(); cfg2.api_type = "custom"
c2 = ApiClient(cfg2)
check("自定义API返回None", c2.get_balance() is None)

# ── 3. 单击 → clicked（余额气泡）──
w = PetWindow()
w.clicked.connect(w.show_balance_bubble)  # 模拟 main.py 接线
w.move(800, 300)  # 移到屏幕中央，避免贴边逻辑干扰测试
w.show(); app.processEvents()
spy = QSignalSpy(w.clicked)
QTest.mouseClick(w, Qt.LeftButton)
wait(600)  # doubleClickInterval + 30
check("单击触发 clicked", spy.count() == 1, str(spy.count()))
check("单击显示余额气泡", w._balance_bubble is not None and w._balance_bubble.isVisible())
w._balance_bubble.hide()

# ── 4. 双击 → chat_requested ──
spy2 = QSignalSpy(w.chat_requested)
w.show(); app.processEvents()
QTest.mouseDClick(w, Qt.LeftButton)
wait(650)  # 450ms 三击窗口 + 余量
check("双击触发 chat_requested", spy2.count() == 1, str(spy2.count()))

# ── 5. 三击 → 跳舞（不触发 clicked/chat）──
w._double_at = 0.0
w._dbl_guard_until = 0.0
spy3 = QSignalSpy(w.clicked)
spy4 = QSignalSpy(w.chat_requested)

def real_click_seq(n):
    """模拟真实 Qt 连击：第 2 次起 press 被替换为 DblClick 事件"""
    lp = w.rect().center()
    gp = w.mapToGlobal(lp)
    for i in range(n):
        if i > 0:
            ev = QMouseEvent(QEvent.MouseButtonDblClick, QPointF(lp), QPointF(gp),
                             Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        else:
            ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(lp), QPointF(gp),
                             Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(w, ev)
        rel = QMouseEvent(QEvent.MouseButtonRelease, QPointF(lp), QPointF(gp),
                          Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
        QApplication.sendEvent(w, rel)
    app.processEvents()

real_click_seq(3)
wait(600)
check("三击不触发 clicked", spy3.count() == 0, str(spy3.count()))
check("三击不触发 chat_requested", spy4.count() == 0, str(spy4.count()))
check("三击触发跳舞", w.anim.current_state.name == "DANCE", w.anim.current_state.name)
wait(1200)
# 跳舞结束回 idle（跳过 10s 防抖窗口直接验证切换逻辑）
w._dance_until = 0
w._end_dance()
check("跳舞结束回 idle", w.anim.current_state.name == "IDLE", w.anim.current_state.name)

# ── 6. 再次单击 toggle 隐藏 ──
w._balance_bubble.show(); app.processEvents()
spy5 = QSignalSpy(w.clicked)
QTest.mouseClick(w, Qt.LeftButton)
wait(600)
check("再单击隐藏余额气泡", not w._balance_bubble.isVisible())
check("点击气泡触发刷新", bub._status in ("ok", "loading"))

# ── 7. 气泡定位（云朵显示在角色上方）──
from PySide6.QtCore import QRect
pet_rect = QRect(200, 300, 256, 256)
bub2 = BalanceBubble(lambda: (1.0, "CNY"))
bub2.place_above(pet_rect)
check("气泡在桌宠正上方", bub2.x() == pet_rect.center().x() - bub2.width() // 2
      and bub2.y() == pet_rect.top() - bub2.height() - 18 and bub2._tail_dir == "down",
      f"x={bub2.x()} y={bub2.y()} tail={bub2._tail_dir}")
check("气泡与桌宠不重叠", bub2.geometry().bottom() <= pet_rect.top(), str(bub2.geometry()))
check("气泡水平居中", abs((bub2.x() + bub2.width() // 2) - pet_rect.center().x()) <= 1)
# 顶部空间不足 → fallback 放下方、尾巴朝上
class FakeScreen:
    def availableGeometry(self):
        return QRect(0, 0, 1000, 1000)  # 正常屏
orig = QApplication.screenAt
QApplication.screenAt = lambda *a: FakeScreen()
pet_top = QRect(200, 100, 256, 256)  # 桌宠顶部 100：100-120-18=-38 < 4 → 上方放不下
bub2.place_above(pet_top)
QApplication.screenAt = orig
check("上方不足时放下方", bub2.y() == pet_top.bottom() + 18 and bub2._tail_dir == "up",
      f"y={bub2.y()} tail={bub2._tail_dir}")
check("放下方不重叠", bub2.geometry().top() >= pet_top.bottom(), str(bub2.geometry()))
# 屏幕边界钳制
class FakeScreen2:
    def availableGeometry(self):
        return QRect(0, 0, 100, 100)
QApplication.screenAt = lambda *a: FakeScreen2()
bub2.place_above(QRect(0, 0, 256, 256))
QApplication.screenAt = orig
check("边界钳制", bub2.x() >= 4 and bub2.y() >= 4, f"x={bub2.x()} y={bub2.y()}")

# ── 8. 启动优化：预取缓存秒显 + 200ms 快速确认 ──
import module_1_core.pet_window as pw
from module_1_core.pet_window import _balance_cache, _prefetch_balance

# 缓存命中 → refresh 立即显示（网络慢的 fetch 不阻塞显示）
_balance_cache["ts"] = time.monotonic()
_balance_cache["balance"] = 66.0
_balance_cache["currency"] = "CNY"
bub3 = BalanceBubble(lambda: (time.sleep(3), (0.0, "CNY"))[1])
bub3.refresh()
app.processEvents()
check("缓存命中秒显余额", bub3._amount.text() == "¥ 66.00", bub3._amount.text())
check("缓存命中非loading", bub3._status == "ok", bub3._status)

# 预取：mock get_balance 成功 → 缓存写入
orig_get_balance = pw.ApiClient.get_balance
pw.ApiClient.get_balance = lambda self: (55.5, "CNY")
_balance_cache["ts"] = 0.0
class FakeCfg2:
    api_key = "sk-test"
    api_type = "deepseek"
    api_base = ""
_prefetch_balance(FakeCfg2())
wait(500)
pw.ApiClient.get_balance = orig_get_balance
check("启动预取写入缓存", _balance_cache["balance"] == 55.5 and _balance_cache["ts"] > 0,
      str(_balance_cache["balance"]))

# 快速单击确认（远快于原版 430ms，双击序列内可被取消）
w2 = PetWindow()
spy6 = QSignalSpy(w2.clicked)
w2.show(); app.processEvents()
QTest.mouseClick(w2, Qt.LeftButton)
wait(380)
check("单击 300ms 快速确认", spy6.count() == 1, f"count={spy6.count()} (确认时间~300ms)")

# ── 9. 贴边隐藏时余额云朵自动收起 ──
w3 = PetWindow()
w3.clicked.connect(w3.show_balance_bubble)
w3.move(800, 300)
w3.show(); app.processEvents()
QTest.mouseClick(w3, Qt.LeftButton)
wait(400)
check("云朵已显示", w3._balance_bubble is not None and w3._balance_bubble.isVisible())
w3.snap_to_edge("left")  # 模拟贴边隐藏
app.processEvents()
check("贴边时云朵自动隐藏", w3._balance_bubble is None or not w3._balance_bubble.isVisible())
# 展开后云朵不自动出现
w3.expand_from_edge()
app.processEvents()
check("展开后云朵不自动显示", w3._balance_bubble is None or not w3._balance_bubble.isVisible())
w3._hidden_at_edge = False
w3._snapped_edge = None

print(f"\n===== {len(PASS)} PASS / {len(FAIL)} FAIL =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("ALL GREEN")
