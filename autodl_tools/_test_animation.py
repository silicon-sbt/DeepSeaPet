"""无头测试：AnimationController 加载新 idle 帧并循环"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, r'E:\code\deepseek的桌宠')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QEventLoop

app = QApplication([])

from module_1_core.animation import AnimationController, PetState

ctrl = AnimationController()
ok = ctrl.load_from_dir(PetState.IDLE)
print(f'idle 帧加载: {ok}')

# 取到帧
frames = ctrl._frames.get(PetState.IDLE, [])
print(f'idle 帧数: {len(frames)}')
for i, f in enumerate(frames):
    if not f.isNull():
        print(f'  f{i}: {f.width()}x{f.height()} 非空 ✓')
    else:
        print(f'  f{i}: NULL ✗')

# 模拟循环几帧
ctrl.switch(PetState.IDLE)
ctrl.play()
received = []
def on_frame(px):
    received.append(px)
ctrl.frame_changed.connect(on_frame)

loop = QEventLoop()
QTimer.singleShot(2000, loop.quit)  # 8fps × 2s ≈ 16 tick
loop.exec()
ctrl.stop()
print(f'\n2秒内收到帧更新: {len(received)} 次 (期望 ~14-16)')
print('动画循环正常' if len(received) >= 10 else '⚠ 循环异常')
