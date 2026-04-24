"""
db_preparator.py
Vectoriza las tablas del restaurante y las almacena en la tabla bot_knowledge
con embeddings generados por Gemini text-embedding-004.

Uso: python db_preparator.py
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def embed(text: str) -> list[float]:
    result = _client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config={"output_dimensionality": 768},
    )
    return result.embeddings[0].values


def upsert_knowledge(cur, source: str, content: str) -> None:
    vector = embed(content)
    cur.execute(
        """
        INSERT INTO bot_knowledge (source, content, embedding)
        VALUES (%s, %s, %s::vector)
        ON CONFLICT (source) DO UPDATE
            SET content   = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
        """,
        (source, content, vector),
    )


# ---------------------------------------------------------------------------
# Extractores por tabla
# ---------------------------------------------------------------------------

def load_products(cur_db, cur_kb) -> int:
    cur_db.execute(
        """
        SELECT p."Id", p."Name", p."Description", p."Price", p."IsAvailable",
               c."Name" AS category
        FROM "Products" p
        LEFT JOIN "Categories" c ON c."Id" = p."CategoryId"
        """
    )
    rows = cur_db.fetchall()
    for r in rows:
        content = (
            f'Ítem del menú — Producto: {r[1]}. '
            f'Descripción: {r[2] or "sin descripción"}. '
            f'Precio: ${r[3]}. '
            f'Estado: {"disponible para ordenar" if r[4] else "no disponible"}. '
            f'Categoría del menú: {r[5] or "sin categoría"}.'
        )
        upsert_knowledge(cur_kb, f"product_{r[0]}", content)
    return len(rows)


def load_categories(cur_db, cur_kb) -> int:
    cur_db.execute('SELECT "Id", "Name", "IsActive", "DisplayOrder" FROM "Categories"')
    rows = cur_db.fetchall()
    for r in rows:
        content = (
            f'Categoría: {r[1]}. '
            f'Activa: {"sí" if r[2] else "no"}. '
            f'Orden de display: {r[3]}.'
        )
        upsert_knowledge(cur_kb, f"category_{r[0]}", content)
    return len(rows)


def load_tables(cur_db, cur_kb) -> int:
    cur_db.execute('SELECT "Id", "Number", "IsOccupied", "X", "Y" FROM "Tables"')
    rows = cur_db.fetchall()
    for r in rows:
        content = (
            f'Mesa física número {r[1]} del restaurante. '
            f'Estado de ocupación: {"ocupada" if r[2] else "libre, no ocupada"}. '
            f'Coordenadas en el plano: X={r[3]}, Y={r[4]}.'
        )
        upsert_knowledge(cur_kb, f"table_{r[0]}", content)
    return len(rows)


def load_orders_summary(cur_db, cur_kb) -> int:
    """Carga un resumen agregado de órdenes (hoy y últimos 7 días).
    Status: 0=pending, 1=in_progress, 2=completed, 3=cancelled (enteros).
    """
    cur_db.execute(
        """
        SELECT
            COUNT(*)                                            AS total_today,
            COALESCE(SUM("TotalAmount"), 0)                     AS revenue_today,
            COUNT(*) FILTER (WHERE "Status" = 0)                AS pending,
            COUNT(*) FILTER (WHERE "Status" = 2)                AS completed,
            COUNT(*) FILTER (WHERE "Status" = 3)                AS cancelled
        FROM "Orders"
        WHERE DATE("OperationalDate") = CURRENT_DATE
        """
    )
    r = cur_db.fetchone()
    content = (
        f"Resumen de órdenes del día de hoy: "
        f"total={r[0]}, ingresos=${r[1]:.2f}, "
        f"pendientes={r[2]}, completadas={r[3]}, canceladas={r[4]}."
    )
    upsert_knowledge(cur_kb, "orders_summary_today", content)

    cur_db.execute(
        """
        SELECT DATE("OperationalDate") AS day, COUNT(*), COALESCE(SUM("TotalAmount"),0)
        FROM "Orders"
        WHERE "OperationalDate" >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY day
        ORDER BY day DESC
        """
    )
    rows = cur_db.fetchall()
    lines = [f'{r[0]}: {r[1]} órdenes, ${float(r[2]):.2f}' for r in rows]
    content7 = "Órdenes últimos 7 días:\n" + "\n".join(lines) if lines else "Sin datos."
    upsert_knowledge(cur_kb, "orders_summary_7days", content7)
    return 2


def load_sessions_summary(cur_db, cur_kb) -> int:
    cur_db.execute(
        """
        SELECT
            COUNT(*)                                            AS total_today,
            COUNT(*) FILTER (WHERE "IsActive" = true)           AS active,
            COUNT(*) FILTER (WHERE "IsActive" = false)          AS closed
        FROM "TableSessions"
        WHERE DATE("OperationalDate") = CURRENT_DATE
        """
    )
    r = cur_db.fetchone()
    content = (
        f"Sesiones de mesa del día de hoy: "
        f"total={r[0]}, activas={r[1]}, cerradas={r[2]}."
    )
    upsert_knowledge(cur_kb, "sessions_summary_today", content)
    return 1


def load_payments_summary(cur_db, cur_kb) -> int:
    cur_db.execute(
        """
        SELECT "PaymentMethod", "Status", COUNT(*), COALESCE(SUM("Amount"),0)
        FROM "Payments"
        WHERE DATE("CreatedAt") = CURRENT_DATE
        GROUP BY "PaymentMethod", "Status"
        """
    )
    rows = cur_db.fetchall()
    if rows:
        # PaymentMethod y Status son integers; los mostramos tal cual
        lines = [
            f'método={r[0]}, estado={r[1]}: {r[2]} pagos, ${float(r[3]):.2f}'
            for r in rows
        ]
        content = "Pagos del día de hoy:\n" + "\n".join(lines)
    else:
        content = "No hay pagos registrados hoy."
    upsert_knowledge(cur_kb, "payments_summary_today", content)
    return 1


def load_users_summary(cur_db, cur_kb) -> int:
    cur_db.execute(
        """
        SELECT COUNT(*), COUNT(*) FILTER (WHERE "IsActive" = true)
        FROM "Users"
        """
    )
    r = cur_db.fetchone()
    content = (
        f'Usuarios del sistema: total={r[0]}, activos={r[1]}.'
    )
    upsert_knowledge(cur_kb, "users_summary", content)
    return 1


def load_order_details_summary(cur_db, cur_kb) -> int:
    """Top 10 productos más pedidos hoy."""
    cur_db.execute(
        """
        SELECT p."Name", SUM(od."Quantity") AS qty
        FROM "OrderDetails" od
        JOIN "Products" p ON p."Id" = od."ProductId"
        JOIN "Orders" o ON o."Id" = od."OrderId"
        WHERE DATE(o."OperationalDate") = CURRENT_DATE
        GROUP BY p."Name"
        ORDER BY qty DESC
        LIMIT 10
        """
    )
    rows = cur_db.fetchall()
    if rows:
        lines = [f'{r[0]}: {r[1]} unidades' for r in rows]
        content = "Productos más pedidos hoy:\n" + "\n".join(lines)
    else:
        content = "No hay detalles de órdenes para hoy."
    upsert_knowledge(cur_kb, "order_details_top_today", content)
    return 1


# ---------------------------------------------------------------------------
# Creación de la tabla bot_knowledge (si no existe)
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bot_knowledge (
    id         SERIAL PRIMARY KEY,
    source     TEXT UNIQUE NOT NULL,
    content    TEXT        NOT NULL,
    embedding  vector(768) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS bot_knowledge_embedding_idx
    ON bot_knowledge USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"""


def ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute('DROP TABLE IF EXISTS bot_knowledge CASCADE')
        cur.execute(CREATE_TABLE_SQL)
        cur.execute(CREATE_INDEX_SQL)
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Conectando a la base de datos...")
    conn_db = get_connection()   # conexión para leer las tablas del restaurante
    conn_kb = get_connection()   # conexión para escribir bot_knowledge

    ensure_table(conn_kb)
    print("Tabla bot_knowledge lista.")

    cur_db = conn_db.cursor()
    cur_kb = conn_kb.cursor()

    loaders = [
        ("Productos",                load_products),
        ("Categorías",               load_categories),
        ("Mesas",                    load_tables),
        ("Resumen órdenes",          load_orders_summary),
        ("Detalle órdenes (top)",    load_order_details_summary),
        ("Resumen sesiones",         load_sessions_summary),
        ("Resumen pagos",            load_payments_summary),
        ("Usuarios",                 load_users_summary),
    ]

    total = 0
    for name, fn in loaders:
        try:
            n = fn(cur_db, cur_kb)
            conn_kb.commit()
            print(f"  ✓ {name}: {n} registros vectorizados.")
            total += n
        except Exception as e:
            conn_kb.rollback()
            print(f"  ✗ {name}: error — {e}")

    cur_db.close()
    cur_kb.close()
    conn_db.close()
    conn_kb.close()
    print(f"\nListo. {total} entradas en bot_knowledge.")


if __name__ == "__main__":
    main()
