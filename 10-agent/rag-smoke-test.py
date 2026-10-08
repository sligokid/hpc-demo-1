import os
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from tools import search_knowledge_base, get_video_metadata, get_full_transcript

qdrant = QdrantClient(host="localhost", port=6333)
model  = SentenceTransformer("intfloat/multilingual-e5-large")

# ask the user for the question
question = input("Enter your topic: ")

results = search_knowledge_base(
    question,
    lang="en",
    top_k=5,
    qdrant_client=qdrant,
    embed_model=model,
)

for result in results:
    print(result)