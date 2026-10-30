import sys
import numpy as np
import sounddevice as sd
import aubio
from pedalboard import Pedalboard, HighpassFilter, PitchShift, Chorus, Bitcrush
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt

class VoiceChangerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.stream = None
        self.board = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=300),
            PitchShift(semitones=2),
            Chorus(rate_hz=1.0, depth=0.25, centre_delay_ms=7.0, feedback=0.0, mix=0.5),
            Bitcrush(bit_depth=8)
        ])

        self.samplerate = 44100
        self.blocksize = 1024
        self.pitch_detector = aubio.pitch("default", 2048, self.blocksize, self.samplerate)
        self.output_buffer = np.zeros((1, 0), dtype=np.float32)

        self.initUI()

    def initUI(self):
        self.setWindowTitle('GLaDOS Voice Changer')
        self.setFixedSize(300, 150)

        layout = QVBoxLayout()

        self.status_label = QLabel("Status: Stopped", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.start_btn = QPushButton('Start Voice Changer', self)
        self.start_btn.clicked.connect(self.start_processing)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton('Stop Voice Changer', self)
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

        self.setLayout(layout)

    def audio_callback(self, indata, outdata, frames, time, status):
        if status:
            print(status, file=sys.stderr)

        # Process the input data
        # pedalboard expects shape (channels, samples), sounddevice gives (samples, channels)
        input_audio = indata.T

        # Detect pitch for autotune
        samples = np.zeros(self.blocksize, dtype=np.float32)
        in_len = min(self.blocksize, indata.shape[0])
        samples[:in_len] = indata[:in_len, 0]

        pitch_freq = self.pitch_detector(samples)[0]
        if pitch_freq > 0:
            midi = 69 + 12 * np.log2(pitch_freq / 440.0)
            nearest_midi = round(midi)
            shift_to_snap = nearest_midi - midi
            self.board[1].semitones = shift_to_snap + 2.0

        # apply the effect
        processed_audio = self.board(input_audio, self.stream.samplerate, reset=False)

        # If pedalboard output is stereo but our output expects mono, downmix
        if processed_audio.shape[0] > outdata.shape[1]:
            # Simple average downmix
            processed_audio = np.mean(processed_audio, axis=0, keepdims=True)

        # Append to buffer
        self.output_buffer = np.concatenate((self.output_buffer, processed_audio), axis=1)

        # Write to outdata (samples, channels)
        # Take exactly frames amount of audio from buffer
        available_frames = self.output_buffer.shape[1]

        if available_frames >= frames:
            outdata[:] = self.output_buffer[:, :frames].T
            self.output_buffer = self.output_buffer[:, frames:]
        else:
            # Underflow - pad with zeros
            outdata[:available_frames] = self.output_buffer.T
            outdata[available_frames:] = 0
            self.output_buffer = np.zeros((1, 0), dtype=np.float32)

    def start_processing(self):
        self.status_label.setText("Status: Running")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.output_buffer = np.zeros((1, 0), dtype=np.float32)

        try:
            self.stream = sd.Stream(callback=self.audio_callback, channels=1, samplerate=self.samplerate, blocksize=self.blocksize)
            self.stream.start()
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def stop_processing(self):
        self.status_label.setText("Status: Stopped")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = VoiceChangerApp()
    ex.show()
    sys.exit(app.exec())
