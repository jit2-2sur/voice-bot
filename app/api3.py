import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions, DeepgramClientOptions
import httpx
import uuid
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from rag import ask_rag

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Deepgram API key
API_KEY = os.getenv("DG_API_KEY")

# Initialize Deepgram client configuration
config = DeepgramClientOptions(options={"keepalive": "true"})
deepgram = DeepgramClient(API_KEY, config)
dg_connection = None


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve the audio file."""
    file_path = os.path.join("D:/voice-bot/", filename)  # Adjust the folder path if needed
    return FileResponse(file_path, media_type='audio/wav')

# In the handle_transcript function, send the audio file URL
async def handle_transcript(websocket: WebSocket, transcript: str):
    """Process the transcribed text, get LLM response, and convert it to speech."""
    print("Speaker: ", transcript)
    await websocket.send_json({"type": "text", "role": "user", "content": transcript})

    llm_response = ask_rag(transcript).response
    print("Bot: ", llm_response)
    await websocket.send_json({"type": "text", "role": "bot", "content": llm_response})

    # Convert to speech and save to a file
    audio_filename = await convert_text_to_speech(llm_response)
    
    # Send the audio file URL to the frontend
    audio_url = f"http://127.0.0.1:8000/audio/{audio_filename}"
    await websocket.send_json({"type": "audio", "content": audio_url})

async def convert_text_to_speech(text: str):
    """Convert LLM response to speech using Deepgram's TTS and save to a file."""
    DEEPGRAM_URL = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"
    headers = {"Authorization": f"Token {API_KEY}", "Content-Type": "application/json"}
    payload = {"text": text}
    
    audio_filename = f"{uuid.uuid4()}.wav"

    async with httpx.AsyncClient() as client:
        response = await client.post(DEEPGRAM_URL, headers=headers, json=payload, timeout=None)

        with open(audio_filename, 'wb') as audio_file:
            async for chunk in response.aiter_bytes(chunk_size=1024):
                if chunk:
                    audio_file.write(chunk)

    print(f"Audio saved to {audio_filename}")

    return audio_filename

def initialize_deepgram_connection(websocket: WebSocket):
    """Initialize Deepgram WebSocket connection and set up event handlers."""
    global dg_connection
    dg_connection = deepgram.listen.websocket.v("1")

    def on_open(self, open, **kwargs):
        print(f"STT Connection opened")

    def on_message(self, result, **kwargs):
        transcript = result.channel.alternatives[0].transcript
        if transcript:
            asyncio.run(handle_transcript(websocket, transcript))

    def on_close(self, close, **kwargs):
        print(f"STT Connection closed")

    def on_error(self, error, **kwargs):
        print(f"STT Connection error: {error}")

    dg_connection.on(LiveTranscriptionEvents.Open, on_open)
    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
    dg_connection.on(LiveTranscriptionEvents.Close, on_close)
    dg_connection.on(LiveTranscriptionEvents.Error, on_error)

    options = LiveOptions(
        model="nova-2", 
        language="en-US",
        encoding="linear16",
        channels=1,
        sample_rate=16000,
        endpointing=500,
        #vad_events=True,
    )
    if not dg_connection.start(options):
        raise RuntimeError("Failed to start Deepgram connection")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections and audio streaming."""
    await websocket.accept()
    try:
        initialize_deepgram_connection(websocket)
        while True:
            data = await websocket.receive_bytes()
            if dg_connection:
                dg_connection.send(data)
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    finally:
        if dg_connection:
            dg_connection.finish()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
