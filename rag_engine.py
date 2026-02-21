import os
import hashlib
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http import models
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DOCS_DIR = 'docs'
VECTOR_DB_DIR = 'vector_db'
COLLECTION_NAME = 'email_knowledge'

# Initialize Clients
qdrant = QdrantClient(path=VECTOR_DB_DIR)
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    genai_client = None

def get_embedding(text):
    """Generates embedding using Gemini."""
    if not genai_client:
        return None
    try:
        result = genai_client.models.embed_content(
            model='text-embedding-004',
            contents=text
        )
        return result.embeddings[0].values
    except Exception as e:
        print(f"Embedding Error: {e}")
        return None

def init_qdrant():
    """Initializes the Qdrant collection."""
    collections = qdrant.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if not exists:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )
        print(f"Created collection: {COLLECTION_NAME}")

def get_file_hash(filepath):
    """Generates MD5 hash of a file."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def process_pdfs():
    """Reads PDFs from docs/ and indexes them if changed."""
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)
        print(f"Created {DOCS_DIR} directory. Add your PDFs there.")
        return

    init_qdrant()
    
    pdf_files = [f for f in os.listdir(DOCS_DIR) if f.endswith('.pdf')]
    if not pdf_files:
        print("No PDFs found in docs/ folder.")
        return

    for filename in pdf_files:
        filepath = os.path.join(DOCS_DIR, filename)
        file_id = get_file_hash(filepath)
        
        # Check if file is already indexed using a filter (we can use metadata or a separate tracker)
        # For simplicity in this version, we'll store file_id in payload and check
        existing = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="file_id", match=models.MatchValue(value=file_id))]
            ),
            limit=1
        )[0]

        if existing:
            print(f"File {filename} is already indexed. Skipping...")
            continue

        print(f"Indexing {filename}...")
        reader = PdfReader(filepath)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"

        # Simple chunking (by paragraphs or fixed length)
        chunks = [full_text[i:i+1500] for i in range(0, len(full_text), 1200)]
        
        points = []
        for i, chunk in enumerate(chunks):
            vector = get_embedding(chunk)
            if vector:
                points.append(models.PointStruct(
                    id=hashlib.md5(f"{file_id}_{i}".encode()).hexdigest(),
                    vector=vector,
                    payload={
                        "text": chunk,
                        "filename": filename,
                        "file_id": file_id
                    }
                ))
        
        if points:
            qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"Successfully indexed {len(points)} chunks from {filename}")

def query_knowledge_base(query_text, limit=3):
    """Searches the vector DB for relevant context."""
    if not genai_client:
        return ""
        
    query_vector = get_embedding(query_text)
    if not query_vector:
        return ""

    search_result = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=limit
    )
    
    context = "\n---\n".join([hit.payload['text'] for hit in search_result])
    return context

if __name__ == "__main__":
    process_pdfs()
