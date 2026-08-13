"""SSH 关机 AutoDL 实例（特权容器，root 可关机）。
注意：用 `shutdown -h now`（SysV），别用 `poweroff`——AutoDL 容器非 systemd，
`poweroff` 是 systemd 符号链接，会报 "System has not been booted with systemd" 且不关机。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

c = conn.connect()
try:
    c.exec_command("shutdown -h now", timeout=15)
    print("关机指令已发送（连接可能立即断开）")
except Exception as e:
    print("发送时连接断开(预期):", e)
c.close()
