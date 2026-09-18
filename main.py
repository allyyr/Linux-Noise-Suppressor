import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSystemTrayIcon,
    QMenu,
    QVBoxLayout,
    QWidget,
)

import pipewire_manager as pw


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Noise Suppressor")
        self.setMinimumWidth(380)

        self.settings = pw.load_settings()

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("Microphone to clean up:"))
        self.source_combo = QComboBox()
        layout.addWidget(self.source_combo)

        self.refresh_btn = QPushButton("Refresh device list")
        self.refresh_btn.clicked.connect(self.refresh_sources)
        layout.addWidget(self.refresh_btn)

        layout.addWidget(QLabel("Suppression strength (VAD threshold):"))
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.setValue(int(self.settings.get("vad_threshold", 50)))
        self.threshold_value_label = QLabel(f"{self.threshold_slider.value()}%")
        self.threshold_slider.valueChanged.connect(
            lambda v: self.threshold_value_label.setText(f"{v}%")
        )
        layout.addWidget(self.threshold_slider)
        layout.addWidget(self.threshold_value_label)

        self.toggle_btn = QPushButton()
        self.toggle_btn.clicked.connect(self.toggle_suppression)
        layout.addWidget(self.toggle_btn)

        layout.addStretch()
        self.setCentralWidget(central)

        self.refresh_sources()
        self.update_status()
        self._setup_tray()

    def refresh_sources(self):
        self.source_combo.clear()
        sources = pw.list_audio_sources()
        if not sources:
            self.source_combo.addItem("No microphones found — is PipeWire running?", "")
            return
        for name, description in sources:
            self.source_combo.addItem(description, name)

        saved_source = self.settings.get("source_name", "")
        if saved_source:
            index = self.source_combo.findData(saved_source)
            if index >= 0:
                self.source_combo.setCurrentIndex(index)

    def update_status(self):
        enabled = pw.is_enabled()
        plugin_found = pw.find_ladspa_plugin() is not None

        if not plugin_found:
            self.status_label.setText(
                "⚠ RNNoise LADSPA plugin not found. Install it first — see README."
            )
        elif enabled:
            self.status_label.setText("● Noise suppression is ON")
        else:
            self.status_label.setText("○ Noise suppression is OFF")

        self.toggle_btn.setText("Disable" if enabled else "Enable")

    def toggle_suppression(self):
        if pw.is_enabled():
            ok, message = pw.disable()
        else:
            source_name = self.source_combo.currentData()
            if not source_name:
                QMessageBox.warning(self, "No microphone selected", "Pick a microphone first.")
                return
            threshold = float(self.threshold_slider.value())
            ok, message = pw.enable(source_name, threshold)

            self.settings["source_name"] = source_name
            self.settings["vad_threshold"] = threshold

        self.settings["enabled"] = pw.is_enabled()
        pw.save_settings(self.settings)

        if not ok:
            QMessageBox.critical(self, "Error", message)
        self.update_status()

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.windowIcon() or QIcon.fromTheme("audio-input-microphone"))
        self.tray.setToolTip("Noise Suppressor")

        menu = QMenu()
        show_action = menu.addAction("Open settings")
        show_action.triggered.connect(self.show)
        toggle_action = menu.addAction("Toggle suppression")
        toggle_action.triggered.connect(self._tray_toggle)
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def _tray_toggle(self):
        self.toggle_suppression()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep running via tray icon
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
