"""聊天窗主题：配色常量 + 卡片/头像绘制工具

从 chat_window.py 拆出来——配色和绘制跟窗口逻辑混在一个 700 行文件里，
改一个颜色要翻过半个文件。
"""
import html

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (QColor, QPainter, QPainterPath, QPixmap, QLinearGradient,
                           QBrush)

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


def to_html(text: str) -> str:
    """把原始文本转成安全的富文本。

    气泡是 Qt.RichText，模型吐出的 ``<`` 或用户输入的标签会被当成标记解析
    （渲染错乱，也是富文本注入面）——所以一律先转义，再把换行变成 <br>。
    """
    return html.escape(str(text)).replace("\n", "<br>")


def rounded_path(rect: QRectF, tl, tr, br, bl) -> QPainterPath:
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


def circle_pix(src: QPixmap, size: int) -> QPixmap:
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


def face_crop(src: QPixmap, size: int) -> QPixmap:
    """全身精灵图 → 头部聚焦头像：取画面顶部 30% 高度（头+肩）居中裁剪再圆形化。

    全身图几何居中裁剪只会裁到躯干/裙子（角色头顶在 y≈15，画面中心在身体），
    头像必须聚焦头部区域。
    """
    w, h = src.width(), src.height()
    hw = int(w * 0.60)
    hx = (w - hw) // 2
    hy = int(h * 0.02)  # 避开顶部透明边缘
    hh = int(h * 0.30)
    return circle_pix(src.copy(hx, hy, hw, hh), size)


_ai_avatar_cache = None
_user_avatar_cache = None


def ai_avatar():
    """鲸鱼娘圆形头像（用待机帧）"""
    global _ai_avatar_cache
    if _ai_avatar_cache is None:
        from module_1_core.animation import SPRITE_DIR, PetState, make_placeholder_sprite
        idle = SPRITE_DIR / "idle_00.png"
        if idle.exists():
            _ai_avatar_cache = face_crop(QPixmap(str(idle)), MSG_AVATAR)
        else:
            _ai_avatar_cache = circle_pix(make_placeholder_sprite(PetState.IDLE, size=64), MSG_AVATAR)
    return _ai_avatar_cache


def user_avatar():
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


def cached_pet_pix() -> QPixmap:
    """header 大头像（待机图）"""
    from module_1_core.animation import SPRITE_DIR, PetState, make_placeholder_sprite
    idle_path = SPRITE_DIR / "idle_00.png"
    if idle_path.exists():
        return QPixmap(str(idle_path))
    return make_placeholder_sprite(PetState.IDLE, size=64)


# 兼容旧名字（测试与外部引用仍在用下划线前缀）
_rounded_path = rounded_path
_face_crop = face_crop
_circle_pix = circle_pix
_ai_avatar = ai_avatar
_user_avatar = user_avatar
_cached_pet_pix = cached_pet_pix
