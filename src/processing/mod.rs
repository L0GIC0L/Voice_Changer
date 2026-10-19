use rustfft::num_complex::Complex;
use rustfft::{Fft, FftPlanner};
use std::sync::Arc;

pub struct GLaDOSEffect {
    window_size: usize,
    hop_size: usize,
    fft: Arc<dyn Fft<f32>>,
    ifft: Arc<dyn Fft<f32>>,
    buffer: Vec<f32>,
    ola_buffer: Vec<f32>,
    pitch_shift: f32,
    flatten_pitch: bool,
}

impl GLaDOSEffect {
    pub fn new(window_size: usize, hop_size: usize) -> Self {
        let mut planner = FftPlanner::new();
        let fft = planner.plan_fft_forward(window_size);
        let ifft = planner.plan_fft_inverse(window_size);

        GLaDOSEffect {
            window_size,
            hop_size,
            fft,
            ifft,
            buffer: Vec::with_capacity(window_size),
            ola_buffer: vec![0.0; window_size],
            pitch_shift: 1.0,
            flatten_pitch: true,
        }
    }

    pub fn set_pitch_shift(&mut self, shift: f32) {
        self.pitch_shift = shift;
    }

    pub fn set_flatten_pitch(&mut self, flatten: bool) {
        self.flatten_pitch = flatten;
    }

    pub fn process_sample(&mut self, sample: f32) -> Option<Vec<f32>> {
        self.buffer.push(sample);

        if self.buffer.len() >= self.window_size {
            let processed_chunk = self.process_frame(&self.buffer);

            // Overlap-add
            for (i, item) in processed_chunk.iter().enumerate().take(self.window_size) {
                self.ola_buffer[i] += item;
            }

            let output: Vec<f32> = self.ola_buffer[0..self.hop_size].to_vec();

            // Shift OLA buffer
            self.ola_buffer.rotate_left(self.hop_size);
            for i in (self.window_size - self.hop_size)..self.window_size {
                self.ola_buffer[i] = 0.0;
            }

            // Shift input buffer
            self.buffer.drain(0..self.hop_size);

            return Some(output);
        }

        None
    }

    fn process_frame(&self, frame: &[f32]) -> Vec<f32> {
        let mut complex_frame: Vec<Complex<f32>> = frame
            .iter()
            .enumerate()
            .map(|(i, &val)| {
                // Apply Hann window
                let window = 0.5
                    * (1.0
                        - (2.0 * std::f32::consts::PI * i as f32 / (self.window_size - 1) as f32)
                            .cos());
                Complex::new(val * window, 0.0)
            })
            .collect();

        self.fft.process(&mut complex_frame);

        // Simple phase vocoder / GLaDOS effect approximation
        // 1. Flatten pitch by quantization or simply mapping bin magnitudes
        // 2. Pitch shifting via bin scaling

        let mut processed_complex = vec![Complex::new(0.0, 0.0); self.window_size];

        for (i, item) in complex_frame.iter().enumerate().take(self.window_size / 2) {
            let magnitude = item.norm();
            let phase = item.arg();

            let target_bin = if self.flatten_pitch {
                // Crush the pitch to a set of harmonic bins (autotune/robotic effect)
                let crushed_i = (i as f32 / 10.0).round() * 10.0;
                (crushed_i * self.pitch_shift) as usize
            } else {
                (i as f32 * self.pitch_shift) as usize
            };

            if target_bin < self.window_size / 2 {
                processed_complex[target_bin] += Complex::from_polar(magnitude, phase);
            }
        }

        // Mirror the spectrum for real IFFT
        for i in 1..self.window_size / 2 {
            processed_complex[self.window_size - i] = processed_complex[i].conj();
        }

        self.ifft.process(&mut processed_complex);

        let normalization = 1.0 / self.window_size as f32;
        processed_complex
            .iter()
            .map(|c| c.re * normalization)
            .collect()
    }
}
