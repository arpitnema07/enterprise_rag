import fitz  # PyMuPDF
from typing import List, Dict, Any
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
import uuid
from . import vector_store
from qdrant_client.http import models as rest

# Model Config
EMBEDDING_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3"
OLLAMA_BASE_URL = "http://SRPTH1IDMQFS02.vecvnet.com:11434"

embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)
llm = Ollama(model=CHAT_MODEL, base_url=OLLAMA_BASE_URL)


def process_pdf(file_path: str, group_id: int, metadata: Dict[str, Any] = {}):
    doc = fitz.open(file_path)
    chunks = []

    # Simple chunking for MVP: per page or fixed size text splitting
    # TODO: Implement intelligent chunking per PRD
    for page_num, page in enumerate(doc):
        text = page.get_text()
        # Clean text
        text = " ".join(text.split())

        # Split into approx 512 token chunks (simplified: 200 words)
        words = text.split()
        chunk_size = 200
        overlap = 40

        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i : i + chunk_size]
            chunk_text = " ".join(chunk_words)

            chunk_id = str(uuid.uuid4())

            # Embed
            vector = embeddings.embed_query(chunk_text)

            # Prepare payload
            payload = {
                "text": chunk_text,
                "metadata": {
                    "group_id": group_id,
                    "page_number": page_num + 1,
                    **metadata,
                },
            }

            chunks.append(rest.PointStruct(id=chunk_id, vector=vector, payload=payload))

    # Upload to QDrant
    vector_store.upload_points(chunks)
    return len(chunks)


def generate_answer(query: str, group_ids: List[int]):
    # Embed query
    query_vector = embeddings.embed_query(query)

    # Search QDrant
    search_results = vector_store.search(query_vector, group_ids)

    # Construct Context
    context = ""
    sources = []
    for hit in search_results:
        context += f"Source (Page {hit.payload['metadata']['page_number']}): {hit.payload['text']}\n\n"
        sources.append(hit.payload["metadata"])

    # Generate Answer
    prompt = f"""
    Answer the question based strictly on the provided context. 
    If the answer is not in the context, say "No data found in uploaded documents".
    
    Context:
    {context}
    
    Question: {query}
    """

    response = llm.invoke(prompt)

    return {"answer": response, "sources": sources}
