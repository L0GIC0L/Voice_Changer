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

        # GLaDOS-like effect chain:
        # 1. Highpass to remove low end
        # 2. PitchShift (for autotune + pitch up)
        # 3. Chorus (robotic/metallic feel)
        # 4. Bitcrush (lo-fi/computerized artifacting)
        self.board = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=300),
            PitchShift(semitones=2.0),
            Chorus(rate_hz=1.0, depth=0.25, centre_delay_ms=7.0, feedback=0.0, mix=0.5),
            Bitcrush(bit_depth=8)
        ])
        self.output_buffer = np.zeros((0, 1), dtype=np.float32)

        # Setup aubio pitch detection
        # Using a standard block size of 2048 and hop size of 512
        self.pitch_o = aubio.pitch("default", 2048, 512, self.samplerate)
        self.pitch_o.set_unit("Hz")
        self.pitch_o.set_tolerance(0.8)

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

        # Autotune logic: analyze pitch of incoming chunk
        # Extract flat float32 array for aubio
        samples = indata[:, 0].astype(np.float32)

        # We only need one pitch estimate for the chunk. Aubio needs 512 samples.
        # If the chunk is smaller, we'll pad it, but usually frames is 1024 or 2048.
        if len(samples) >= 512:
            pitch_hz = self.pitch_o(samples[:512])[0]

            if pitch_hz > 0:
                # Convert Hz to MIDI note
                midi = 69 + 12 * np.log2(pitch_hz / 440.0)
                # Find closest semitone
                closest_note = round(midi)
                # Calculate difference needed to snap to closest note
                diff_semitones = closest_note - midi

                # Update pitch shift effect: GLaDOS pitch up (e.g. +3 semitones) + correction
                glados_pitch_up = 3.0
                # board[1] is the PitchShift effect
                self.board[1].semitones = float(diff_semitones + glados_pitch_up)

        # Process the input data
        # pedalboard expects shape (channels, samples), sounddevice gives (samples, channels)
        input_audio = indata.T

        # apply the effect
        processed_audio = self.board(input_audio, self.samplerate, reset=False)

        # If pedalboard output is stereo but our output expects mono, downmix
        if processed_audio.shape[0] > outdata.shape[1]:
            # Simple average downmix
            processed_audio = np.mean(processed_audio, axis=0, keepdims=True)

        # Append to buffer
        self.output_buffer = np.vstack((self.output_buffer, processed_audio.T))

        # Write to outdata (samples, channels)
        if len(self.output_buffer) >= frames:
            outdata[:] = self.output_buffer[:frames]
            self.output_buffer = self.output_buffer[frames:]
        else:
            available = len(self.output_buffer)
            outdata[:available] = self.output_buffer
            outdata[available:] = 0.0
            self.output_buffer = np.zeros((0, outdata.shape[1]), dtype=np.float32)

    def start_processing(self):
        self.status_label.setText("Status: Running")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        try:
            self.stream = sd.Stream(callback=self.audio_callback, channels=1, samplerate=44100)
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
