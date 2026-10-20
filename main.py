import sys
import sounddevice as sd
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QSlider, QLabel, QComboBox)
from PyQt6.QtCore import Qt, QTimer
from pedalboard import Pedalboard, PitchShift, Chorus, HighpassFilter, LowpassFilter, Reverb, Bitcrush, Gain

class GladosVoiceChanger(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GLaDOS Voice Changer")
        self.setMinimumWidth(400)

        self.is_running = False
        self.stream = None
        self.sample_rate = 44100

        # Audio processing components
        self.pitch_shift = PitchShift(semitones=3)
        self.chorus = Chorus(rate_hz=1.0, depth=0.1, centre_delay_ms=7.0, feedback=0.0, mix=0.3)
        self.bitcrush = Bitcrush(bit_depth=12)
        self.highpass = HighpassFilter(cutoff_frequency_hz=300)
        self.lowpass = LowpassFilter(cutoff_frequency_hz=4000)
        self.reverb = Reverb(room_size=0.1, damping=0.1, wet_level=0.1)
        self.gain = Gain(gain_db=5)

        self.update_pedalboard()

        self.init_ui()

    def update_pedalboard(self):
        self.board = Pedalboard([
            self.pitch_shift,
            self.chorus,
            self.bitcrush,
            self.highpass,
            self.lowpass,
            self.reverb,
            self.gain
        ])

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Device selection
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Input Device:"))
        self.input_combo = QComboBox()
        device_layout.addWidget(self.input_combo)
        layout.addLayout(device_layout)

        device_layout_out = QHBoxLayout()
        device_layout_out.addWidget(QLabel("Output Device:"))
        self.output_combo = QComboBox()
        device_layout_out.addWidget(self.output_combo)
        layout.addLayout(device_layout_out)

        self.populate_devices()

        # Controls
        # Pitch
        self.pitch_slider = self.create_slider("Pitch (Semitones)", 0, 12, 3, layout)
        self.pitch_slider.valueChanged.connect(self.update_pitch)

        # Bitcrush
        self.bitcrush_slider = self.create_slider("Bit Depth", 4, 16, 12, layout)
        self.bitcrush_slider.valueChanged.connect(self.update_bitcrush)

        # Gain
        self.gain_slider = self.create_slider("Gain (dB)", -20, 20, 5, layout)
        self.gain_slider.valueChanged.connect(self.update_gain)

        # Start/Stop button
        self.toggle_btn = QPushButton("Start Processing")
        self.toggle_btn.clicked.connect(self.toggle_processing)
        layout.addWidget(self.toggle_btn)

    def create_slider(self, name, min_val, max_val, default, layout):
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel(name))

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)

        val_label = QLabel(str(default))
        slider.valueChanged.connect(lambda v: val_label.setText(str(v)))

        h_layout.addWidget(slider)
        h_layout.addWidget(val_label)
        layout.addLayout(h_layout)

        return slider

    def update_pitch(self, val):
        self.pitch_shift.semitones = val
        self.update_pedalboard()

    def update_bitcrush(self, val):
        self.bitcrush.bit_depth = val
        self.update_pedalboard()

    def update_gain(self, val):
        self.gain.gain_db = val
        self.update_pedalboard()

    def populate_devices(self):
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    self.input_combo.addItem(f"{i}: {dev['name']}", i)
                if dev['max_output_channels'] > 0:
                    self.output_combo.addItem(f"{i}: {dev['name']}", i)
        except Exception as e:
            print(f"Error enumerating devices: {e}")

    def audio_callback(self, indata, outdata, frames, time, status):
        if status:
            print(status)

        try:
            # Process audio
            audio = indata.T
            # Must use reset=False for real-time streaming to preserve state (reverb tails, etc)
            processed = self.board(audio, self.sample_rate, reset=False)

            # Pedalboard might output stereo (2, frames) due to effects like Reverb.
            # We requested channels=1, so we must downmix to mono or take the first channel.
            mono_processed = processed[0:1, :]
            outdata[:] = mono_processed.T
        except Exception as e:
            print(f"Audio processing error: {e}")
            outdata[:] = 0

    def toggle_processing(self):
        if not self.is_running:
            input_device = self.input_combo.currentData()
            output_device = self.output_combo.currentData()

            if input_device is None or output_device is None:
                return

            try:
                self.stream = sd.Stream(
                    device=(input_device, output_device),
                    channels=1,
                    samplerate=self.sample_rate,
                    callback=self.audio_callback
                )
                self.stream.start()
                self.is_running = True
                self.toggle_btn.setText("Stop Processing")
            except Exception as e:
                print(f"Failed to start stream: {e}")
        else:
            if self.stream:
                self.stream.stop()
                self.stream.close()
            self.is_running = False
            self.toggle_btn.setText("Start Processing")

    def closeEvent(self, event):
        if self.stream and self.stream.active:
            self.stream.stop()
            self.stream.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GladosVoiceChanger()
    window.show()
    sys.exit(app.exec())
