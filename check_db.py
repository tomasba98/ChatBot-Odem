# import os, psycopg2
# from dotenv import load_dotenv
# load_dotenv()
# conn = psycopg2.connect(os.getenv('DATABASE_URL'))
# cur = conn.cursor()
# cur.execute("SELECT source, LEFT(content, 80) FROM bot_knowledge ORDER BY source")
# for r in cur.fetchall(): print(r[0], '->', r[1])
# conn.close()

import os, psycopg2
from google import genai
from dotenv import load_dotenv
load_dotenv()

c = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'), http_options={'api_version':'v1beta'})
result = c.models.embed_content(model='gemini-embedding-001', contents='que productos hay disponibles', config={'output_dimensionality': 768})
vec = result.embeddings[0].values

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("SET ivfflat.probes = 10")
cur.execute("""
    SELECT source, LEFT(content, 80), 1 - (embedding <=> %s::vector) AS similarity
    FROM bot_knowledge
    ORDER BY embedding <=> %s::vector
    LIMIT 15
""", (vec, vec))
for r in cur.fetchall(): print(f"{r[2]:.4f}  {r[0]}  ->  {r[1]}")
conn.close()