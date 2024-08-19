import os
from dotenv import load_dotenv

import chromadb
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext

from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.core import Settings

from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')


llm = Gemini(model="models/gemini-1.5-flash", api_key=GOOGLE_API_KEY)
Settings.llm = llm

embed_model_name = "models/embedding-001"
embed_model = GeminiEmbedding(model_name=embed_model_name, api_key=GOOGLE_API_KEY)
Settings.embed_model = embed_model

def load_docs():
    documents = SimpleDirectoryReader("./data").load_data()

    db = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = db.get_or_create_collection("hr_policy")

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_documents(
        documents, storage_context=storage_context
    )


def ask_rag(question):
    db = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = db.get_or_create_collection("hr_policy")

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    index = VectorStoreIndex.from_vector_store(
        vector_store, storage_context=storage_context
    )

    query_engine = index.as_query_engine()

    qna_tool = QueryEngineTool(
        query_engine=query_engine,
        metadata=ToolMetadata(
            name="personal_bot",
            description="you are an assistant bot. Always give professional, short, accurate answer without any special characters and emojis.",
        ),
    )
    agent = ReActAgent.from_tools([qna_tool], llm=llm, verbose=False)

    response = agent.chat(question)

    return response