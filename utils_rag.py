
import os

import psycopg2

# Uso a futuro
def retrieve_live_data(intent_keywords: str) -> str:
    """Consulta tablas operativas en tiempo real según la pregunta."""
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    results = []
    try:
        with conn.cursor() as cur:
            # Mesas disponibles
            cur.execute("""
                SELECT COUNT(*) FROM "Tables" WHERE "Status" = 'available'
            """)
            available = cur.fetchone()[0]
            results.append(f"Mesas disponibles ahora: {available}")
            
            # Órdenes del día
            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM("TotalAmount"), 0)
                FROM "Orders"
                WHERE DATE("CreatedAt") = CURRENT_DATE
            """)
            count, total = cur.fetchone()
            results.append(f"Órdenes de hoy: {count}, Recaudación: ${total:.2f}")
            
            # Productos sin stock
            cur.execute("""
                SELECT "Name" FROM "Products" WHERE "IsAvailable" = false
            """)
            unavailable = [r[0] for r in cur.fetchall()]
            if unavailable:
                results.append(f"Productos sin stock: {', '.join(unavailable)}")
    finally:
        conn.close()
    return "\n".join(results)