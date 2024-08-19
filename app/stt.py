import os

import asyncio
from dotenv import load_dotenv
import logging
from deepgram.utils import verboselogs
from time import sleep

from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    Microphone,
)

load_dotenv()
DEEPGRAM_API_KEY = os.getenv('DG_API_KEY')


is_finals = []


async def listen():
    try:
        config: DeepgramClientOptions = DeepgramClientOptions(
            options={"keepalive": "true"}
        )
        deepgram: DeepgramClient = DeepgramClient(DEEPGRAM_API_KEY, config)

        dg_connection = deepgram.listen.asyncwebsocket.v("1")

        async def on_open(self, open, **kwargs):
            print("Connection Open")

        async def on_message(self, result, **kwargs):
            global is_finals
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return
            if sentence=='Stop.':
                print('Shutdown initiated...')
                await shutdown(dg_connection, microphone)

            if result.is_final:
                is_finals.append(sentence)

                if result.speech_final:
                    utterance = " ".join(is_finals)
                    print(f"Speaker: {utterance}")
                    is_finals = []
                else:
                    print(sentence)
            else:
                print(sentence)

        async def on_metadata(self, metadata, **kwargs):
            print(f"Metadata: {metadata}")

        async def on_speech_started(self, speech_started, **kwargs):
            print("Speech Started")

        async def on_utterance_end(self, utterance_end, **kwargs):
            print("Utterance End")
            global is_finals
            if len(is_finals) > 0:
                utterance = " ".join(is_finals)
                print(f"Utterance End: {utterance}")
                is_finals = []

        async def on_close(self, close, **kwargs):
            print("Connection Closed")

        async def on_error(self, error, **kwargs):
            print(f"Handled Error: {error}")

        async def on_unhandled(self, unhandled, **kwargs):
            print(f"Unhandled Websocket Message: {unhandled}")

        dg_connection.on(LiveTranscriptionEvents.Open, on_open)
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
        dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
        dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
        dg_connection.on(LiveTranscriptionEvents.Close, on_close)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        dg_connection.on(LiveTranscriptionEvents.Unhandled, on_unhandled)

        # connect to websocket
        options: LiveOptions = LiveOptions(
            model="nova-2",
            language="en-IN",
            smart_format=True,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            # To get UtteranceEnd, the following must be set:
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True,
            # Time in milliseconds of silence to wait for before finalizing speech
            endpointing=1000,
        )

        addons = {
            "no_delay": "true"
        }

        print("\n\nStart talking!...\n")
        if await dg_connection.start(options, addons=addons) is False:
            print("Failed to connect to Deepgram")
            return

        # Open a microphone stream on the default input device
        microphone = Microphone(dg_connection.send)

        # start microphone
        microphone.start()

        # wait until cancelled
        try:
            while True:
                await asyncio.sleep(1)
        finally:
            microphone.finish()
            await dg_connection.finish()

        print("Finished")

    except Exception as e:
        print(f"Could not open socket: {e}")
        return


async def shutdown(dg_connection, microphone):
    print("Shutdown ongoing...")
    microphone.finish()
    await dg_connection.finish()
    sleep(30)
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    print(f"Cancelling {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    print("Shutdown complete...")


asyncio.run(listen())