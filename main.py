import sys
import numpy as np
import sounddevice as sd
from pedalboard import Pedalboard, PitchShift, Chorus, Bitcrush, HighpassFilter
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt

class VoiceChangerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GLaDOS Voice Changer")
        self.setFixedSize(300, 150)

        self.is_running = False
        self.stream = None

        # Setup Pedalboard
        self.board = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=200),
            PitchShift(semitones=2.0),
            Chorus(rate_hz=1.0, depth=0.1, centre_delay_ms=2.0, feedback=0.0, mix=0.5),
            Bitcrush(bit_depth=8)
        ])
        self.sample_rate = 44100

        # Setup UI
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.status_label = QLabel("Status: Stopped", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.toggle_button = QPushButton("Start Voice Changer", self)
        self.toggle_button.clicked.connect(self.toggle_processing)
        layout.addWidget(self.toggle_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def audio_callback(self, indata, outdata, frames, time, status):
        if status:
            print(status)

        # Ensure audio data is appropriate shape (samples, channels)
        # Process audio using pedalboard
        # Pedalboard expects shape (channels, samples), so we transpose
        audio_in = indata.T

        # Apply effects
        audio_out = self.board(audio_in, self.sample_rate, reset=False)

        # If output is stereo but stream is mono, downmix
        if audio_out.shape[0] == 2 and outdata.shape[1] == 1:
            # Simple average downmix
            audio_out = np.mean(audio_out, axis=0, keepdims=True)

        # Ensure we match expected output channels
        if audio_out.shape[0] == 1 and outdata.shape[1] == 2:
            # Upmix to stereo by duplicating mono channel
            audio_out = np.repeat(audio_out, 2, axis=0)

        # Transpose back to (samples, channels)
        outdata[:] = audio_out.T

    def toggle_processing(self):
        if self.is_running:
            self.stop_processing()
        else:
            self.start_processing()

    def start_processing(self):
        try:
            # Start sounddevice Stream
            self.stream = sd.Stream(
                samplerate=self.sample_rate,
                channels=1, # Default to Mono
                callback=self.audio_callback,
                dtype='float32'
            )
            self.stream.start()
            self.is_running = True
            self.status_label.setText("Status: Running")
            self.toggle_button.setText("Stop Voice Changer")
            self.setStyleSheet("QMainWindow { background-color: #2E8B57; }") # Green
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")

    def stop_processing(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.is_running = False
        self.status_label.setText("Status: Stopped")
        self.toggle_button.setText("Start Voice Changer")
        self.setStyleSheet("")

    def closeEvent(self, event):
        self.stop_processing()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VoiceChangerApp()
    window.show()
    sys.exit(app.exec())
