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

        self.samplerate = 44100
        self.blocksize = 1024

        # Initialize pitch detector
        # aubio.pitch(method, buf_size, hop_size, samplerate)
        self.pitch_o = aubio.pitch("default", 2048, self.blocksize, self.samplerate)
        self.pitch_o.set_unit("Hz")
        self.pitch_o.set_tolerance(0.8)

        # Buffer to accumulate processed output frames
        self.out_buffer = np.zeros((0, 1), dtype=np.float32)

        self.board = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=300),
            PitchShift(semitones=2),
            Chorus(rate_hz=1.0, depth=0.25, centre_delay_ms=7.0, feedback=0.0, mix=0.5),
            Bitcrush(bit_depth=8)
        ])
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

        # Pitch detection
        samples = indata[:, 0].astype(np.float32)
        pitch = self.pitch_o(samples)[0]

        if pitch > 0:
            midi_note = 12 * np.log2(pitch / 440.0) + 69
            target_midi = np.round(midi_note)
            shift = target_midi - midi_note
            # Update pitch shift (+2 semitones is the base shift for GLaDOS)
            self.board[1].semitones = shift + 2.0

        # Process the input data
        # pedalboard expects shape (channels, samples), sounddevice gives (samples, channels)
        input_audio = indata.T

        # apply the effect
        processed_audio = self.board(input_audio, self.stream.samplerate, reset=False)

        # If pedalboard output is stereo but our output expects mono, downmix
        if processed_audio.shape[0] > outdata.shape[1]:
            # Simple average downmix
            processed_audio = np.mean(processed_audio, axis=0, keepdims=True)

        processed_audio = processed_audio.T

        # Append to buffer
        self.out_buffer = np.vstack((self.out_buffer, processed_audio))

        # Write to outdata (samples, channels)
        if len(self.out_buffer) >= frames:
            outdata[:] = self.out_buffer[:frames]
            self.out_buffer = self.out_buffer[frames:]
        else:
            # Underflow, output whatever we have padded with zeros
            size = len(self.out_buffer)
            outdata[:size] = self.out_buffer
            outdata[size:] = 0
            self.out_buffer = np.zeros((0, 1), dtype=np.float32)

    def start_processing(self):
        self.status_label.setText("Status: Running")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        try:
            self.stream = sd.Stream(
                callback=self.audio_callback,
                channels=1,
                samplerate=self.samplerate,
                blocksize=self.blocksize
            )
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
