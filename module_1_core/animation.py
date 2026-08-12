"""动画状态机 + 帧序列管理"""
from enum import Enum
from pathlib import Path
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QTimer, QObject, Signal, Qt


class PetState(Enum):
    IDLE = "idle"
    WALK = "walk"
    HIDE = "hide"
    PEEK = "peek"
    SLEEP = "sleep"
    HAPPY = "happy"
    LYING = "lying"  # 趴姿 — 聊天窗口左上角


# 精灵图目录
SPRITE_DIR = Path(__file__).parent.parent / "module_5_assets" / "sprites"


class AnimationController(QObject):
    """帧序列动画控制器。加载 PNG 帧序列，按帧率循环播放"""
    frame_changed = Signal(QPixmap)

    def __init__(self, fps=12, parent=None):
        super().__init__(parent)
        self._fps = fps
        self._frames = {}       # state -> list[QPixmap]
        self._current_state = PetState.IDLE
        self._frame_idx = 0
        self._is_playing = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)

    def load_state(self, state: PetState, frames: list[QPixmap]):
        """手动设置某状态的帧序列"""
        self._frames[state] = frames

    def load_from_dir(self, state: PetState):
        """从磁盘加载 {state}_*.png 帧序列"""
        import glob
        pattern = str(SPRITE_DIR / f"{state.value}_*.png")
        files = sorted(glob.glob(pattern))
        if not files:
            return False
        self._frames[state] = [QPixmap(f) for f in files]
        return True

    @property
    def current_state(self):
        return self._current_state

    def switch(self, state: PetState):
        """切换状态。若无该状态帧，退回到 idle"""
        if state not in self._frames:
            state = PetState.IDLE
        if state == self._current_state and self._is_playing:
            return
        self._current_state = state
        self._frame_idx = 0
        if self._frames.get(state):
            self.frame_changed.emit(self._frames[state][0])

    def play(self):
        if self._frames.get(self._current_state):
            self._is_playing = True
            interval = int(1000 / self._fps)
            self._timer.start(interval)

    def stop(self):
        self._is_playing = False
        self._timer.stop()

    def _next_frame(self):
        frames = self._frames.get(self._current_state, [])
        if not frames:
            return
        self._frame_idx = (self._frame_idx + 1) % len(frames)
        self.frame_changed.emit(frames[self._frame_idx])


def make_placeholder_sprite(state: PetState, size=256):
    """Q版鲸鱼娘 — chibi 比例，日式大眼，蓝发女仆"""
    from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                                 QPainterPath, QLinearGradient, QRadialGradient)
    from PySide6.QtCore import Qt, QRectF, QPointF

    s = size
    px = QPixmap(s, s)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)

    CX, CY = s / 2, s * 0.42  # 脸中心

    # ═══ 调色板 ═══
    SKIN = QColor(255, 228, 200)
    SKIN_SHADOW = QColor(240, 205, 175)
    HAIR = QColor(74, 144, 217)
    HAIR_DARK = QColor(46, 106, 176)
    HAIR_LIGHT = QColor(123, 184, 240)
    EYE_BLUE = QColor(30, 80, 144)
    EYE_DARK = QColor(15, 40, 72)
    WHITE = QColor(255, 255, 255)
    BLUSH = QColor(255, 180, 170, 150)
    MOUTH = QColor(210, 110, 90)
    DRESS = QColor(44, 95, 138)
    BOW_GOLD = QColor(240, 192, 96)
    BOW_DARK = QColor(200, 150, 60)
    LACE = QColor(250, 250, 252)

    # ═══ 后发 ═══
    p.setBrush(QBrush(HAIR))
    p.setPen(Qt.NoPen)
    # 两侧长发垂落
    p.drawEllipse(QRectF(CX - s * 0.32, CY - s * 0.08, s * 0.18, s * 0.38))
    p.drawEllipse(QRectF(CX + s * 0.14, CY - s * 0.08, s * 0.18, s * 0.38))
    # 头顶发包
    p.drawEllipse(QRectF(CX - s * 0.28, CY - s * 0.32, s * 0.56, s * 0.42))

    # ═══ 脸 ═══
    face_path = QPainterPath()
    face_r = s * 0.20
    face_path.moveTo(CX - face_r, CY - face_r * 0.7)
    face_path.quadTo(CX - face_r, CY - face_r * 1.0, CX - face_r * 0.7, CY - face_r * 0.95)
    face_path.quadTo(CX, CY - face_r * 1.05, CX + face_r * 0.7, CY - face_r * 0.95)
    face_path.quadTo(CX + face_r, CY - face_r * 1.0, CX + face_r, CY - face_r * 0.7)
    face_path.lineTo(CX + face_r, CY + face_r * 0.6)
    face_path.quadTo(CX + face_r * 0.9, CY + face_r * 1.1, CX + face_r * 0.3, CY + face_r * 1.3)
    face_path.quadTo(CX, CY + face_r * 1.4, CX - face_r * 0.3, CY + face_r * 1.3)
    face_path.quadTo(CX - face_r * 0.9, CY + face_r * 1.1, CX - face_r, CY + face_r * 0.6)
    face_path.closeSubpath()
    p.setBrush(QBrush(SKIN))
    p.setPen(QPen(SKIN_SHADOW, 1))
    p.drawPath(face_path)

    # ═══ 刘海 ═══
    p.setBrush(QBrush(HAIR))
    p.setPen(Qt.NoPen)
    bangs = QPainterPath()
    bangs.moveTo(CX - s * 0.25, CY - s * 0.10)
    bangs.quadTo(CX - s * 0.22, CY - s * 0.28, CX - s * 0.08, CY - s * 0.30)
    bangs.quadTo(CX - s * 0.02, CY - s * 0.32, CX + s * 0.04, CY - s * 0.30)
    bangs.quadTo(CX + s * 0.14, CY - s * 0.28, CX + s * 0.20, CY - s * 0.18)
    bangs.lineTo(CX + s * 0.22, CY - s * 0.06)
    bangs.quadTo(CX + s * 0.10, CY - s * 0.14, CX - s * 0.06, CY - s * 0.16)
    bangs.quadTo(CX - s * 0.14, CY - s * 0.12, CX - s * 0.22, CY - s * 0.06)
    bangs.closeSubpath()
    p.drawPath(bangs)
    # 刘海高光
    p.setBrush(QBrush(HAIR_LIGHT))
    p.drawEllipse(QRectF(CX - s * 0.06, CY - s * 0.27, s * 0.06, s * 0.03))
    p.drawEllipse(QRectF(CX + s * 0.05, CY - s * 0.26, s * 0.04, s * 0.02))

    # ═══ 眼睛 ═══
    eye_y = CY - s * 0.02
    _draw_chibi_eye(p, CX - s * 0.09, eye_y, s * 0.09, s * 0.11, s, flip=False)
    _draw_chibi_eye(p, CX + s * 0.09, eye_y, s * 0.09, s * 0.11, s, flip=False)

    # ═══ 眉毛 ═══
    p.setPen(QPen(HAIR_DARK, max(1.5, s * 0.008)))
    brow_y = CY - s * 0.14
    # 左眉
    path = QPainterPath()
    path.moveTo(CX - s * 0.15, brow_y)
    path.quadTo(CX - s * 0.09, brow_y - s * 0.02, CX - s * 0.03, brow_y)
    p.drawPath(path)
    # 右眉
    path = QPainterPath()
    path.moveTo(CX + s * 0.03, brow_y)
    path.quadTo(CX + s * 0.09, brow_y - s * 0.02, CX + s * 0.15, brow_y)
    p.drawPath(path)

    # ═══ 腮红 ═══
    p.setBrush(QBrush(BLUSH))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(CX - s * 0.17, CY + s * 0.02, s * 0.07, s * 0.04))
    p.drawEllipse(QRectF(CX + s * 0.10, CY + s * 0.02, s * 0.07, s * 0.04))

    # ═══ 嘴 ═══
    mouth_y = CY + s * 0.08
    p.setPen(QPen(MOUTH, max(1.2, s * 0.005)))
    p.setBrush(Qt.NoBrush)
    if state == PetState.HAPPY:
        p.setBrush(QBrush(QColor(250, 150, 140, 180)))
        p.drawEllipse(QRectF(CX - s * 0.04, mouth_y, s * 0.08, s * 0.05))
    elif state == PetState.SLEEP:
        p.drawEllipse(QRectF(CX - s * 0.03, mouth_y + s * 0.01, s * 0.06, s * 0.04))
    else:
        mpath = QPainterPath()
        mpath.moveTo(CX - s * 0.035, mouth_y)
        mpath.quadTo(CX, mouth_y + s * 0.03, CX + s * 0.035, mouth_y)
        p.drawPath(mpath)

    # ═══ 鲸鱼尾巴头饰 ═══
    p.setBrush(QBrush(QColor(90, 170, 245)))
    p.setPen(QPen(QColor(60, 130, 210), max(1, s * 0.005)))
    tpath = QPainterPath()
    tx, ty = CX + s * 0.18, CY - s * 0.28
    tpath.moveTo(tx, ty)
    tpath.quadTo(tx + s * 0.10, ty - s * 0.12, tx + s * 0.07, ty - s * 0.04)
    tpath.quadTo(tx + s * 0.12, ty + s * 0.01, tx, ty + s * 0.02)
    tpath.quadTo(tx + s * 0.12, ty + s * 0.08, tx + s * 0.06, ty + s * 0.04)
    tpath.quadTo(tx + s * 0.10, ty + s * 0.12, tx, ty)
    p.drawPath(tpath)

    # ═══ 女仆头饰 ═══
    p.setBrush(QBrush(LACE))
    p.setPen(QPen(QColor(210, 210, 215), 1))
    for i in range(3):
        fx = CX - s * 0.10 + i * s * 0.10
        fy = CY - s * 0.34
        p.drawEllipse(QRectF(fx, fy, s * 0.12, s * 0.06))
    p.setPen(QPen(BOW_GOLD, max(1, s * 0.004)))
    p.setBrush(QBrush(BOW_GOLD))
    p.drawEllipse(QRectF(CX - s * 0.03, CY - s * 0.38, s * 0.06, s * 0.05))
    # 头饰褶皱暗面
    p.setPen(QPen(QColor(190, 190, 200), 0.5))
    p.setBrush(Qt.NoBrush)
    for i in range(2):
        fx = CX - s * 0.04 + i * s * 0.08
        p.drawLine(int(fx), int(CY - s * 0.34), int(fx), int(CY - s * 0.29))

    # ═══ 身体 ═══
    if state == PetState.LYING:
        # 趴姿：身体横向拉伸，像趴在地上
        body_left = CX - s * 0.22
        body_right = CX + s * 0.22
        body_mid_y = CY + face_r * 1.1
        body_top = body_mid_y - s * 0.08  # 领结参考用
        body_bottom = body_mid_y + s * 0.12
        p.setBrush(QBrush(DRESS))
        p.setPen(QPen(QColor(30, 70, 110), 1.5))
        body_path = QPainterPath()
        body_path.moveTo(body_left, body_mid_y - s * 0.06)
        body_path.quadTo(CX - s * 0.05, body_mid_y - s * 0.12, CX + s * 0.02, body_mid_y - s * 0.08)
        body_path.quadTo(CX + s * 0.08, body_mid_y - s * 0.04, body_right, body_mid_y + s * 0.02)
        body_path.lineTo(body_right - s * 0.02, body_mid_y + s * 0.08)
        body_path.quadTo(CX + s * 0.10, body_mid_y + s * 0.05, CX, body_mid_y + s * 0.12)
        body_path.quadTo(CX - s * 0.10, body_mid_y + s * 0.05, body_left, body_mid_y + s * 0.04)
        body_path.closeSubpath()
        p.drawPath(body_path)
        # 趴姿小围裙
        p.setBrush(QBrush(WHITE))
        p.setPen(QPen(QColor(200, 200, 205), 1))
        apron = QPainterPath()
        apron.moveTo(CX - s * 0.08, body_mid_y - s * 0.04)
        apron.lineTo(CX - s * 0.06, body_mid_y + s * 0.08)
        apron.lineTo(CX + s * 0.06, body_mid_y + s * 0.06)
        apron.lineTo(CX + s * 0.08, body_mid_y - s * 0.02)
        apron.closeSubpath()
        p.drawPath(apron)
    else:
        body_top = CY + face_r * 1.15
        body_bottom = body_top + s * 0.22
        p.setBrush(QBrush(DRESS))
        p.setPen(QPen(QColor(30, 70, 110), 1.5))
        body_path = QPainterPath()
        body_path.moveTo(CX - s * 0.16, body_top)
        body_path.quadTo(CX - s * 0.14, body_bottom - s * 0.02, CX - s * 0.10, body_bottom)
        body_path.lineTo(CX + s * 0.10, body_bottom)
        body_path.quadTo(CX + s * 0.14, body_bottom - s * 0.02, CX + s * 0.16, body_top)
        body_path.closeSubpath()
        p.drawPath(body_path)
        # ═══ 白色围裙 ═══
        p.setBrush(QBrush(WHITE))
        p.setPen(QPen(QColor(200, 200, 205), 1))
        apron = QPainterPath()
        apron_top = body_top + s * 0.02
        apron.moveTo(CX - s * 0.10, apron_top)
        apron.lineTo(CX - s * 0.07, body_bottom)
        apron.lineTo(CX + s * 0.07, body_bottom)
        apron.lineTo(CX + s * 0.10, apron_top)
        apron.closeSubpath()
        p.drawPath(apron)

    # ═══ 领结 ═══
    bow_y = body_top - s * 0.01
    p.setBrush(QBrush(BOW_GOLD))
    p.setPen(QPen(BOW_DARK, 1))
    bow_path = QPainterPath()
    bow_path.moveTo(CX, bow_y)
    bow_path.quadTo(CX - s * 0.07, bow_y - s * 0.03, CX - s * 0.015, bow_y + s * 0.04)
    bow_path.quadTo(CX + s * 0.015, bow_y + s * 0.02, CX, bow_y)
    bow_path.quadTo(CX + s * 0.015, bow_y - s * 0.02, CX + s * 0.07, bow_y + s * 0.03)
    bow_path.quadTo(CX - s * 0.015, bow_y + s * 0.02, CX, bow_y)
    p.drawPath(bow_path)

    # ═══ 状态文字 ═══
    labels = {
        PetState.WALK: "♪",
        PetState.SLEEP: "zzz",
        PetState.HAPPY: "♥",
    }
    txt = labels.get(state)
    if txt:
        p.setPen(QPen(QColor(100, 100, 100)))
        p.setFont(QFont("Segoe UI", int(s * 0.06)))
        p.drawText(QRectF(CX + s * 0.10, CY - s * 0.42, s * 0.30, s * 0.14),
                   Qt.AlignCenter, txt)

    p.end()
    return px


def _draw_chibi_eye(p, ex, ey, ew, eh, s, flip=False):
    """画一只日式chibi大眼 — 多层高光 + 渐变瞳孔"""
    from PySide6.QtGui import QColor, QPen, QBrush, QPainterPath, QRadialGradient
    from PySide6.QtCore import QRectF, QPointF

    # 上睫毛线
    p.setPen(QPen(QColor(40, 40, 50), max(1.5, s * 0.007)))
    p.setBrush(QBrush(QColor(255, 254, 248)))
    lid = QPainterPath()
    lid.moveTo(ex - ew * 0.9, ey)
    lid.quadTo(ex - ew * 0.7, ey - eh * 0.55, ex, ey - eh * 0.55)
    lid.quadTo(ex + ew * 0.7, ey - eh * 0.55, ex + ew * 0.9, ey)
    lid.quadTo(ex + ew * 0.7, ey + eh * 0.45, ex, ey + eh * 0.40)
    lid.quadTo(ex - ew * 0.7, ey + eh * 0.45, ex - ew * 0.9, ey)
    lid.closeSubpath()
    p.drawPath(lid)

    # 瞳孔（蓝色渐变）
    pupil = QRadialGradient(QPointF(ex, ey - eh * 0.05), eh * 0.45)
    pupil.setColorAt(0, QColor(50, 120, 200))
    pupil.setColorAt(0.6, QColor(20, 60, 130))
    pupil.setColorAt(1, QColor(8, 25, 60))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(pupil))
    p.drawEllipse(QRectF(ex - ew * 0.45, ey - eh * 0.25, ew * 0.9, eh * 0.55))

    # 主高光
    p.setBrush(QBrush(QColor(255, 255, 255)))
    p.drawEllipse(QRectF(ex - ew * 0.05, ey - eh * 0.40, ew * 0.38, eh * 0.30))
    # 副高光
    p.setBrush(QBrush(QColor(255, 255, 255, 180)))
    p.drawEllipse(QRectF(ex + ew * 0.15, ey - eh * 0.20, ew * 0.18, eh * 0.14))
    # 底部微高光
    p.setBrush(QBrush(QColor(255, 255, 255, 80)))
    p.drawEllipse(QRectF(ex - ew * 0.20, ey + eh * 0.10, ew * 0.22, eh * 0.12))


def make_placeholder_frames(state: PetState, count=8, size=256):
    """为某状态生成占位帧序列（每帧轻微变形模拟动画）"""
    import math
    from PySide6.QtGui import QPixmap, QPainter
    frames = []
    base = make_placeholder_sprite(state, size).toImage()
    for i in range(count):
        # 用轻微缩放模拟呼吸/动作
        scale = 1.0 + 0.03 * math.sin(i / count * 2 * math.pi)
        new_size = int(size * scale)
        img = base.scaled(new_size, new_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # 居中贴回 256x256
        px = QPixmap(size, size)
        px.fill(Qt.transparent)
        p = QPainter(px)
        offset = (size - new_size) // 2
        p.drawPixmap(offset, offset, QPixmap.fromImage(img))
        p.end()
        frames.append(px)
    return frames
