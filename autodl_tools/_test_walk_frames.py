"""无头验证 walk 多帧交替：_walk_frames 加载 2 帧，_step_walk 按相位切帧不崩"""
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\code\deepseek的桌宠")

from PySide6.QtWidgets import QApplication
from module_1_core.pet_window import PetWindow

app = QApplication([])
w = PetWindow()
print("walk_frames 数量:", len(w._walk_frames))
assert len(w._walk_frames) == 2, "walk 应加载 2 帧（walk_00/walk_01）"

# 手动触发散步
w._walk_dir = 1
w._walk_target_x = w.x() + 60
w.set_state("walk")

# 跑 2 秒物理，观察帧切换
w._walk_idx = -1
seen = set()
t0 = time.time()
while time.time() - t0 < 2.0:
    w._physics_tick()
    seen.add(w._walk_idx)
    time.sleep(0.001)
print("期间切换到的帧索引:", sorted(seen))
assert seen == {0, 1}, "2 秒内应交替切到 0 和 1"

# 散步结束回 idle 应重置
w._finish_walk()
print("finish 后 _walk_idx:", w._walk_idx)
assert w._walk_idx == -1
print("WALK MULTI-FRAME OK")
