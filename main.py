import kivy
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
import pyaudio
import wave
import numpy as np
import librosa
import os
import base64
import threading
from google.cloud import pubsub_v1
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import ObjectProperty
from kivy.event import EventDispatcher


kivy.require("2.0.0")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "persuasive-byte-384014-2a5dd1d3816f.json"

def pad_or_truncate_feature(feature, fixed_length=128):
    if len(feature) > fixed_length:
        return feature[:fixed_length]
    else:
        return np.pad(feature, (0, fixed_length - len(feature)), mode='constant')


def extract_features_from_audio_data(audio_data, sample_rate, num_mfcc=40):
    audio_data = audio_data.astype(np.float32)
    mfccs = librosa.feature.mfcc(y=audio_data, sr=sample_rate, n_mfcc=num_mfcc)
    scaled_mfccs = np.mean(mfccs.T, axis=0)

    return scaled_mfccs


def save_audio_to_file(filename, sample_width, audio_data, rate=44100):
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(audio_data)

class UpdateEvent(EventDispatcher):
    update_output = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(UpdateEvent, self).__init__(**kwargs)
        self.register_event_type('on_update_output')

    def on_update_output(self, *args):
        pass

class RecordInputApp(App):
    def update_output(self, event, text):
        self.output_label.text += text + '\n'

    def update_status(self, text):
        def update_label(*args):
            self.status_label.text = text

        Clock.schedule_once(update_label, 0)


    def build(self):
        layout = GridLayout(cols=1, padding=10, spacing=10)

        self.start_recording_button = Button(text="Start Recording", size_hint=(1, 0.1))
        self.start_recording_button.bind(on_press=self.start_recording)
        layout.add_widget(self.start_recording_button)

        self.output_label = Label(text="", size_hint=(1, 0.9))
        layout.add_widget(self.output_label)

        self.update_event = UpdateEvent()
        self.update_event.bind(update_output=self.update_output)

        self.status_label = Label(text="", size_hint=(1, 0.2))
        layout.add_widget(self.status_label)

        return layout


    def start_recording(self, instance):
        print("Recording started")
        self.update_event.dispatch('on_update_output', "Recording started")
        sample_width, audio_data, rate = record_audio()
        audio_data_np = np.frombuffer(audio_data, dtype=np.int16)

        audio_file_path = "test_recording.wav"
        save_audio_to_file("test_recording.wav", sample_width, audio_data, rate)
        send_audio_file(audio_file_path)


def record_audio(duration=3, rate=44100, chunk=1024):
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = rate
    CHUNK = chunk
    RECORD_SECONDS = duration

    audio = pyaudio.PyAudio()

    stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, input=True,
                        frames_per_buffer=CHUNK)

    print("Recording...")
    app = App.get_running_app()
    app.update_status("Recording...")
    frames = []

    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)

    print("Finished recording.")
    app.update_status("Finished recording.")

    stream.stop_stream()
    stream.close()
    audio.terminate()

    return audio.get_sample_size(FORMAT), b''.join(frames), rate


project_id = "persuasive-byte-384014"
topic_id = "audio-data"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, topic_id)

def send_audio_file(file_path):
    with open(file_path, 'rb') as audio_file:
        audio_data = audio_file.read()
        print(f"Read {len(audio_data)} bytes from the audio file")
        # Encode the binary data as base64 before sending
        encoded_audio_data = base64.b64encode(audio_data)
        future = publisher.publish(topic_path, data=encoded_audio_data)
        print(f"Audio file sent: {file_path}")

        app = App.get_running_app()
        app.update_status(f"Read {len(audio_data)} bytes from the audio file")
        app.update_status(f"Audio file sent: {file_path}")


def receive_text_messages():
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, "recognized-text-sub")

    def text_callback(message):
        recognized_text = message.attributes['text']
        print(f"Received text: {recognized_text}")
        message.ack()

        app = App.get_running_app()
        app.update_output(None, f"Received text: {recognized_text}")
        app.update_status("Text message received")

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=text_callback)
    print(f"Listening for text messages on {subscription_path}")

    try:
        streaming_pull_future.result()
    except KeyboardInterrupt:
        streaming_pull_future.cancel()


if __name__ == "__main__":
    threading.Thread(target=receive_text_messages, daemon=True).start()
    RecordInputApp().run()
