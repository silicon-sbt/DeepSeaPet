"""余额云朵气泡 — 独立透明悬浮窗，显示桌宠正上方

从 pet_window.py 拆出来：这个类自带信号、定时器、绘制和网络线程，
跟 PetWindow 的交互物理没有任何耦合，放在一起只会让那个文件越来越难读。
理念致敬 MeteorNOX/DeepSeek-Balance-Whale-Widget。
"""
import sys
import threading
import time

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PySide6.QtCore import Qt, Signal, QTimer, QPointF
from PySide6.QtGui import (QPainter, QColor, QBrush, QLinearGradient,
                           QPolygonF, QPainterPath, QMouseEvent)

from module_2_api.api_client import (ApiClient, ApiConfigError, ApiAuthError,
                                     ApiNetworkError)


# 余额预取缓存：启动时后台查一次，单击气泡时秒显（无需等网络）
_balance_cache = {"ts": 0.0, "balance": None, "currency": None}


def _prefetch_balance(config):
    """后台预取 DeepSeek 余额到模块缓存（不阻塞启动）。

    失败只往 stderr 记一行：预取是可选优化，不该弹窗打扰用户，
    但也不能像以前那样 `except Exception: pass` 把故障吃得一干二净——
    余额一直不显示的时候，那就是唯一能查的线索。
    """
    def work():
        try:
            result = ApiClient(config).get_balance()
        except (ApiConfigError, ApiAuthError, ApiNetworkError) as e:
            print(f"[balance] 预取失败: {e}", file=sys.stderr)
            return
        except Exception as e:
            print(f"[balance] 预取异常: {e!r}", file=sys.stderr)
            return
        if result is not None:
            _balance_cache["balance"], _balance_cache["currency"] = result
            _balance_cache["ts"] = time.monotonic()
    threading.Thread(target=work, daemon=True).start()


class BalanceBubble(QWidget):
    """余额气泡 — 云朵形悬浮气泡，显示在桌宠正上方（尾巴指向角色）。

    蓬松云朵轮廓（多圆并集渐变填充）+ 底部小尾巴；点击刷新、60s 自动刷新、
    金额滚动动画。
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
        except Exception as e:
            print(f"[balance] 查询异常: {e!r}", file=sys.stderr)
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
