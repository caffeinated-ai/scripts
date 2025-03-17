import os
import signal
import sys
import threading
import time
from dataclasses import dataclass

import keyboard
import pyaudio
from google.cloud import speech_v1p1beta1 as speech

RATE = 16000
CHUNK = int(RATE / 10)
DEBUG = False
TYPE_INTERVAL = 1.0
TYPE_STABILITY_THRESHOLD = 0.7
SILENCE_THRESHOLD = 3.0

client = speech.SpeechClient()
last_speech_time = time.time()
exit_event = threading.Event()

@dataclass
class Transcript:
    text: str = ""
    stability: float = 0.0
    is_final: bool = False

@dataclass
class SpeechResult:
    timestamp: float
    transcript: Transcript

class MicrophoneStream:
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk
        self._buff = []
        self._closed = True
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            stream_callback=self._fill_buffer,
        )
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if not self._closed:
            self._audio_stream.stop_stream()
            self._audio_stream.close()
            self._closed = True
            self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status):
        if not self._closed:
            self._buff.append(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self._closed and not exit_event.is_set():
            if self._buff:
                yield self._buff.pop(0)
            else:
                time.sleep(0.01)

def debug_print(message):
    if DEBUG:
        print(f"[DEBUG] {message}")

def process_responses(responses):
    for response in responses:
        if exit_event.is_set():
            break

        timestamp = time.time()
        if not response.results or not response.results[0].alternatives:
            yield SpeechResult(timestamp, Transcript())
            continue

        result = response.results[0]
        transcript_text = result.alternatives[0].transcript

        yield SpeechResult(
            timestamp=timestamp,
            transcript=Transcript(
                text=transcript_text,
                is_final=result.is_final,
                stability=result.stability
            ),
        )

@dataclass
class TypeState:
    last_type_time: float = 0
    last_typed_text: str = ""

def handle_results(results):
    state = TypeState(last_type_time=time.time())

    for result in results:
        if exit_event.is_set():
            break

        if result.transcript.text:
            debug_print(f"[Result] {result}")

            should_type = (
                result.transcript.is_final or
                (
                    time.time() - state.last_type_time >= TYPE_INTERVAL and
                    result.transcript.stability > TYPE_STABILITY_THRESHOLD
                )
            )

            if should_type:
                global last_speech_time
                last_speech_time = time.time()

                current_text = result.transcript.text.strip()
                min_len = min(len(current_text), len(state.last_typed_text))
                common_prefix_len = 0

                for i in range(min_len):
                    if current_text[i].lower() == state.last_typed_text[i].lower():
                        common_prefix_len += 1
                    else:
                        break

                text_to_type = current_text[common_prefix_len:].lstrip()

                if text_to_type:
                    if DEBUG:
                        print(f"[DEBUG] Would type: {text_to_type}")
                    else:
                        keyboard.write(text_to_type + " ")

                    state.last_typed_text = current_text
                    state.last_type_time = time.time()

            if result.transcript.is_final:
                state = TypeState(last_type_time=time.time())

def process(responses):
    try:
        results = process_responses(responses)
        handle_results(results)
    except Exception as e:
        debug_print(f"Error during processing: {e}")
        exit_event.set()

def monitor_activity():
    while not exit_event.is_set():
        if time.time() - last_speech_time > SILENCE_THRESHOLD:
            debug_print(f"No activity for {SILENCE_THRESHOLD} seconds. Shutting down...")
            exit_event.set()
            break
        time.sleep(0.3)

def run_speech_service(stream, streaming_config):
    audio_generator = stream.generator()
    requests = (
        speech.StreamingRecognizeRequest(audio_content=content)
        for content in audio_generator
    )
    try:
        responses = client.streaming_recognize(streaming_config, requests)
        process(responses)
    except Exception as e:
        debug_print(f"Streaming error: {e}")
        exit_event.set()

def signal_handler(signum, frame):
    debug_print("Signal received. Shutting down...")
    exit_event.set()

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US",
        enable_automatic_punctuation=False,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True,
    )

    with MicrophoneStream(RATE, CHUNK) as stream:
        monitor_thread = threading.Thread(target=monitor_activity, daemon=True)
        speech_thread = threading.Thread(
            target=run_speech_service,
            args=(stream, streaming_config),
            daemon=True
        )

        monitor_thread.start()
        speech_thread.start()

        monitor_thread.join()
        speech_thread.join()

if __name__ == "__main__":
    main()
