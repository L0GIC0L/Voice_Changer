use gtk::prelude::*;
use gtk::{Application, ApplicationWindow, Box, Label, Orientation, Scale, ToggleButton};
use gtk4 as gtk;
use ringbuf::HeapRb;
use ringbuf::traits::{Consumer, Producer, Split};
use std::sync::{Arc, Mutex};
use std::thread;

use crate::audio::AudioEngine;
use crate::processing::GLaDOSEffect;

pub fn start_gui() {
    let app = Application::builder()
        .application_id("com.glados.voicechanger")
        .build();

    app.connect_activate(build_ui);
    app.run();
}

fn build_ui(app: &Application) {
    let window = ApplicationWindow::builder()
        .application(app)
        .title("GLaDOS Voice Changer")
        .default_width(400)
        .default_height(250)
        .build();

    let vbox = Box::builder()
        .orientation(Orientation::Vertical)
        .spacing(10)
        .margin_top(20)
        .margin_bottom(20)
        .margin_start(20)
        .margin_end(20)
        .build();

    // Pitch Shift Control
    let pitch_label = Label::new(Some("Pitch Shift"));
    let pitch_scale = Scale::with_range(gtk::Orientation::Horizontal, 0.5, 2.0, 0.05);
    pitch_scale.set_value(1.0);

    // Flat Pitch Control
    let flat_toggle = ToggleButton::with_label("Flatten Pitch (Robotic)");
    flat_toggle.set_active(true);

    // Start/Stop Audio
    let start_button = ToggleButton::with_label("Start Voice Changer");

    vbox.append(&pitch_label);
    vbox.append(&pitch_scale);
    vbox.append(&flat_toggle);
    vbox.append(&start_button);

    window.set_child(Some(&vbox));

    // Audio State
    let effect_state = Arc::new(Mutex::new(GLaDOSEffect::new(1024, 256)));

    // Clone for closures
    let effect_clone1 = effect_state.clone();
    pitch_scale.connect_value_changed(move |scale| {
        if let Ok(mut effect) = effect_clone1.lock() {
            effect.set_pitch_shift(scale.value() as f32);
        }
    });

    let effect_clone2 = effect_state.clone();
    flat_toggle.connect_toggled(move |toggle| {
        if let Ok(mut effect) = effect_clone2.lock() {
            effect.set_flatten_pitch(toggle.is_active());
        }
    });

    let effect_clone3 = effect_state.clone();
    let audio_running = Arc::new(std::sync::atomic::AtomicBool::new(false));
    let audio_running_clone = audio_running.clone();

    start_button.connect_toggled(move |button| {
        if button.is_active() {
            button.set_label("Stop");
            audio_running_clone.store(true, std::sync::atomic::Ordering::SeqCst);
            let eff = effect_clone3.clone();
            let running = audio_running_clone.clone();
            thread::spawn(move || {
                run_audio_thread(eff, running);
            });
        } else {
            button.set_label("Start Voice Changer");
            audio_running_clone.store(false, std::sync::atomic::Ordering::SeqCst);
        }
    });

    window.present();
}

fn run_audio_thread(
    effect_mutex: Arc<Mutex<GLaDOSEffect>>,
    running: Arc<std::sync::atomic::AtomicBool>,
) {
    if let Ok(mut engine) = AudioEngine::new() {
        let rb_size = 8192;
        let (in_prod, mut in_cons) = HeapRb::<f32>::new(rb_size).split();
        let (mut out_prod, out_cons) = HeapRb::<f32>::new(rb_size).split();

        if engine.start(in_prod, out_cons).is_ok() {
            while running.load(std::sync::atomic::Ordering::SeqCst) {
                // Read from input ringbuffer
                let mut processed_any = false;
                while let Some(sample) = in_cons.try_pop() {
                    processed_any = true;
                    let processed_chunk = {
                        if let Ok(mut effect) = effect_mutex.try_lock() {
                            effect.process_sample(sample)
                        } else {
                            None
                        }
                    };

                    if let Some(chunk) = processed_chunk {
                        for s in chunk {
                            let _ = out_prod.try_push(s);
                        }
                    }
                }
                if !processed_any {
                    thread::sleep(std::time::Duration::from_millis(1));
                }
            }
        }
    }
}
