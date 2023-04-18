import base64
import os
from google.cloud import pubsub_v1
from google.cloud import speech_v1p1beta1 as speech

project_id = "persuasive-byte-384014"
subscription_id = "audio-data-sub"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/limjingda98/persuasive-byte-384014-2a5dd1d3816>

subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(project_id, subscription_id)
publisher = pubsub_v1.PublisherClient()
text_topic_path = publisher.topic_path(project_id, "recognized-text")

def recognize_speech_from_audio_data(audio_data):
    client = speech.SpeechClient()
    audio = speech.RecognitionAudio(content=audio_data)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=44100,
        language_code="en-US",
    )

    response = client.recognize(config=config, audio=audio)
    return response.results[0].alternatives[0].transcript if response.results else "No speech detect>

def callback(message):
    audio_data = base64.b64decode(message.data)
    recognized_text = recognize_speech_from_audio_data(audio_data)
    print(f"Recognized text: {recognized_text}")
    message.ack()

    # Publish the recognized text to the new topic
    future = publisher.publish(text_topic_path, text=recognized_text, data=b"")
    print(f"Text message sent: {recognized_text}")

streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
print(f"Listening for messages on {subscription_path}")

try:
    streaming_pull_future.result()
except KeyboardInterrupt:
    streaming_pull_future.cancel()