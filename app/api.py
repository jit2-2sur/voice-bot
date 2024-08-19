from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .rag import ask_rag, load_docs


app = FastAPI()

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.post("/rag")
def get_answer(question):
    load_docs()
    response = ask_rag(question)
    return {"answer": response.response}
