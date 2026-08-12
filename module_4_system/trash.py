"""垃圾桶处理 — 拖放文件移到回收站"""
import send2trash
from PySide6.QtWidgets import QMessageBox


class TrashHandler:
    """将拖放到桌宠的文件移至回收站"""

    @staticmethod
    def handle(config, paths: list[str]) -> dict:
        """
        处理文件拖放。
        - 若 config.confirm_delete，先弹确认框
        - 逐个调 send2trash
        返回: {"success": [...], "failed": [...]}
        """
        if not paths:
            return {"success": [], "failed": []}

        # 确认对话框（可勾选"不再提示"）
        if config.confirm_delete:
            msg = QMessageBox()
            msg.setWindowTitle("确认删除")
            msg.setIcon(QMessageBox.Warning)
            file_list = "\n".join(p[:60] + "…" if len(p) > 60 else p for p in paths[:10])
            more = f"\n…还有 {len(paths) - 10} 个文件" if len(paths) > 10 else ""
            msg.setText(f"确定要将以下 {len(paths)} 个文件移到回收站吗？\n\n{file_list}{more}")

            from PySide6.QtWidgets import QCheckBox
            cb = QCheckBox("不再提示")
            msg.setCheckBox(cb)

            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.No)

            if msg.exec() != QMessageBox.Yes:
                return {"success": [], "failed": paths}

            if cb.isChecked():
                config.confirm_delete = False

        # 执行删除
        success, failed = [], []
        for path in paths:
            try:
                send2trash.send2trash(path)
                success.append(path)
            except Exception:
                failed.append(path)

        return {"success": success, "failed": failed}
