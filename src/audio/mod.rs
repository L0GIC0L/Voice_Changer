use cpal::StreamConfig;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use ringbuf::traits::{Consumer, Producer};

pub struct AudioEngine {
    pub sample_rate: u32,
    pub channels: u16,
    pub input_stream: Option<cpal::Stream>,
    pub output_stream: Option<cpal::Stream>,
}

impl AudioEngine {
    pub fn new() -> Result<Self, anyhow::Error> {
        let host = cpal::default_host();
        let input_device = host
            .default_input_device()
            .ok_or(anyhow::anyhow!("No input device"))?;

        let config: cpal::SupportedStreamConfig = input_device.default_input_config()?;
        let conf: StreamConfig = config.into();
        let sample_rate = conf.sample_rate;
        let channels = config.channels();

        Ok(AudioEngine {
            sample_rate,
            channels,
            input_stream: None,
            output_stream: None,
        })
    }

    pub fn start(
        &mut self,
        mut producer: impl Producer<Item = f32> + Send + 'static,
        mut consumer: impl Consumer<Item = f32> + Send + 'static,
    ) -> Result<(), anyhow::Error> {
        let host = cpal::default_host();
        let input_device = host.default_input_device().unwrap();
        let output_device = host.default_output_device().unwrap();

        let input_config: StreamConfig = input_device.default_input_config()?.into();
        let output_config: StreamConfig = output_device.default_output_config()?.into();

        let input_data_fn = move |data: &[f32], _: &cpal::InputCallbackInfo| {
            for &sample in data {
                let _ = producer.try_push(sample);
            }
        };

        let output_data_fn = move |data: &mut [f32], _: &cpal::OutputCallbackInfo| {
            for sample in data.iter_mut() {
                *sample = consumer.try_pop().unwrap_or(0.0);
            }
        };

        let err_fn = |err| eprintln!("an error occurred on stream: {}", err);

        let input_stream =
            input_device.build_input_stream(input_config, input_data_fn, err_fn, None)?;

        let output_stream =
            output_device.build_output_stream(output_config, output_data_fn, err_fn, None)?;

        input_stream.play()?;
        output_stream.play()?;

        self.input_stream = Some(input_stream);
        self.output_stream = Some(output_stream);

        Ok(())
    }
}
