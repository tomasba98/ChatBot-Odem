"""
utils_rag.py
Utilidades para la búsqueda vectorial (RAG) sobre bot_knowledge.
"""

import os
import psycopg2
from google import genai
from dotenv import load_dotenv

load_dotenv()

_client = genai.Client(
    api_key=os.getenv("GOOGLE_API_KEY"),
    http_options={"api_version": "v1beta"},
)

TOP_K = 8  # número de fragmentos a recuperar


def embed_query(text: str) -> list[float]:
    """Genera el embedding de una consulta del usuario."""
    result = _client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config={"output_dimensionality": 768},
    )
    return result.embeddings[0].values


def retrieve_context(user_query: str, top_k: int = TOP_K) -> str:
    """
    Busca los fragmentos más relevantes en bot_knowledge usando
    similitud coseno y devuelve el texto concatenado como contexto.
    Retorna cadena vacía si no hay resultados.
    """
    query_embedding = embed_query(user_query)

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    try:
        with conn.cursor() as cur:
            cur.execute("SET ivfflat.probes = 10")
            cur.execute(
                """
                SELECT content
                FROM bot_knowledge
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, top_k),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return "\n".join(r[0] for r in rows)


def build_prompt(context: str, user_query: str) -> str:
    """Construye el prompt final para Gemini."""
    return (
        "Eres el asistente virtual del restaurante Ordem. "
        "Respondes de forma amable, concisa y siempre en español. "
        "Usa únicamente la información del CONTEXTO para responder. "
        "Si la información no está en el contexto, dilo con claridad.\n\n"
        f"CONTEXTO:\n{context}\n\n"
        f"PREGUNTA DEL USUARIO:\n{user_query}"
    )
