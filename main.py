import sys
import numpy as np
import sounddevice as sd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout,
                             QWidget, QLabel, QSlider)
from PyQt6.QtCore import Qt
from pedalboard import Pedalboard, PitchShift, Chorus, Reverb, Compressor

class GLaDOSVoiceChanger(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GLaDOS Voice Changer")

        self.is_running = False
        self.stream = None

        self.setup_ui()
        self.setup_audio_effects()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.status_label = QLabel("Status: Stopped")
        layout.addWidget(self.status_label)

        self.toggle_btn = QPushButton("Start Voice Changer")
        self.toggle_btn.clicked.connect(self.toggle_audio)
        layout.addWidget(self.toggle_btn)

        # Pitch Control
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setMinimum(0)
        self.pitch_slider.setMaximum(100)
        self.pitch_slider.setValue(25) # 2.5 semitones
        self.pitch_slider.valueChanged.connect(self.update_pitch)
        layout.addWidget(QLabel("Pitch Shift"))
        layout.addWidget(self.pitch_slider)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def setup_audio_effects(self):
        # GLaDOS effect: Pitch shift up, slight chorus, and compression for roboty feel
        self.board = Pedalboard([
            PitchShift(semitones=2.5),
            Chorus(rate_hz=1.0, depth=0.1, centre_delay_ms=2.0, feedback=0.0, mix=0.3),
            Compressor(threshold_db=-20, ratio=4)
        ])

    def update_pitch(self, value):
        semitones = value / 10.0
        self.board[0].semitones = semitones

    def toggle_audio(self):
        if self.is_running:
            self.stop_audio()
        else:
            self.start_audio()

    def start_audio(self):
        try:
            self.stream = sd.Stream(callback=self.audio_callback, channels=1, samplerate=44100)
            self.stream.start()
            self.is_running = True
            self.toggle_btn.setText("Stop Voice Changer")
            self.status_label.setText("Status: Running (GLaDOS active)")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def stop_audio(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.is_running = False
        self.toggle_btn.setText("Start Voice Changer")
        self.status_label.setText("Status: Stopped")

    def audio_callback(self, indata, outdata, frames, time, status):
        if status:
            print(status, file=sys.stderr)

        # apply pedalboard
        # pedalboard expects (channels, samples) shape
        audio_in = indata.T
        audio_out = self.board(audio_in, 44100, reset=False)
        outdata[:] = audio_out.T

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GLaDOSVoiceChanger()
    window.show()
    sys.exit(app.exec())
