# Chatbot Ordem — Documentación Técnica

## Descripción general

Asistente virtual para el restaurante **Ordem**, construido sobre **Rasa 3.6.20**. Responde preguntas sobre el menú, mesas, órdenes y configuración del restaurante usando RAG (Retrieval-Augmented Generation) con embeddings vectoriales y Gemini como modelo de lenguaje. También consulta una API externa para el tipo de cambio USD/ARS.

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Framework de diálogo | Rasa 3.6.20 |
| Modelo de embeddings | `gemini-embedding-001` (768 dims, API v1beta) |
| Modelo de generación | `gemini-2.5-flash-lite` (Google Generative AI) |
| SDK de Google | `google-genai` (nuevo SDK, reemplaza `google-generativeai`) |
| Base de datos vectorial | PostgreSQL + pgvector (Neon hosted) |
| Índice vectorial | ivfflat (probes=10, lists=100) |
| API externa | ExchangeRate-API v6 (fallback a v4) |
| Lenguaje | Python 3.10.8 |
| Sistema operativo | Windows, venv en `.venv/` |

---

## Arquitectura RAG

```
Usuario → Rasa NLU → intent: ask_product_rag
                          ↓
                  action_rag_answer
                          ↓
            embed_query(texto) → gemini-embedding-001
                          ↓
            búsqueda coseno en bot_knowledge (pgvector)
            SET ivfflat.probes = 10 → TOP_K = 8 resultados
                          ↓
            build_prompt(contexto, pregunta)
                          ↓
            gemini-2.5-flash-lite → respuesta en español
```

---

## Pipeline NLU (config.yml)

- `WhitespaceTokenizer`
- `RegexFeaturizer`
- `LexicalSyntacticFeaturizer`
- `CountVectorsFeaturizer` (word-level + char n-gram)
- `DIETClassifier` (100 épocas)
- `FallbackClassifier` (umbral: 0.3)

## Políticas de diálogo

- `MemoizationPolicy`
- `RulePolicy`
- `UnexpecTEDIntentPolicy`
- `TEDPolicy`

---

## Intents y comportamiento

| Intent | Descripción | Acción |
|---|---|---|
| `greet` | Saludo del usuario | `utter_greet` |
| `goodbye` | Despedida | `utter_goodbye` |
| `ask_product_rag` | Preguntas sobre el restaurante | `action_rag_answer` (RAG + Gemini) |
| `ask_api_external` | Consulta del dólar | `action_call_external_api` |
| `refresh_knowledge` | Actualizar base de conocimiento RAG | `action_refresh_knowledge` |
| `chitchat` | Conversación fuera de tema | `utter_chitchat` (redirige al bot) |
| `out_of_scope` | Preguntas irrelevantes | `utter_out_of_scope` |
| `nlu_fallback` | Input vacío o incomprensible | `utter_no_input` |

---

## Gestión de sesión

- **Expiración por inactividad**: 5 minutos. Después de 5 minutos sin mensajes, la sesión expira y se reinicia al próximo mensaje.
- **Slots**: No se arrastran entre sesiones (`carry_over_slots_to_new_session: false`).

---

## Tabla bot_knowledge

La tabla vectorial contiene **46 entradas** generadas por `db_preparator.py`:

| Tipo de dato | Cantidad | Prefijo `source` |
|---|---|---|
| Productos del menú | 13 | `product_` |
| Categorías del menú | 5 | `category_` |
| Mesas del restaurante | 22 | `table_` |
| Resumen de órdenes hoy | 1 | `orders_summary_today` |
| Resumen de órdenes 7 días | 1 | `orders_summary_7days` |
| Top detalles de órdenes hoy | 1 | `order_details_top_today` |
| Resumen de sesiones de mesa | 1 | `sessions_summary_today` |
| Resumen de pagos hoy | 1 | `payments_summary_today` |
| Resumen de usuarios | 1 | `users_summary` |

Para actualizar los datos: `python db_preparator.py`

También puede actualizarse en tiempo real desde el chat diciéndole al bot frases como *"actualizá la base de conocimiento"* o *"refrescá el menú"* (intent `refresh_knowledge`). El bot ejecuta `db_preparator.py` en segundo plano sin interrumpir la conversación.

---

## Preguntas que puede responder el bot

### Menú y productos
- ¿Qué productos hay disponibles?
- ¿Cuánto cuesta la pizza?
- ¿Qué bebidas tienen?
- ¿Cuáles son los postres del menú?
- ¿Qué platos principales ofrecen?
- ¿Tienen menú infantil?
- ¿Cuál es el plato más caro?

### Mesas
- ¿Cuántas mesas hay en el restaurante?
- ¿Qué mesas están ocupadas?
- ¿Cuántas mesas están libres?
- ¿Está ocupada la mesa 5?

### Órdenes y actividad
- ¿Cuántas órdenes hubo hoy?
- ¿Cuántas órdenes hubo esta semana?
- ¿Cuánto ingresaron los últimos 7 días?
- ¿Cuántas órdenes están pendientes?

### General del restaurante
- ¿Cómo se llama el restaurante?
- ¿Cuántos usuarios tiene el sistema?
- ¿Cuántas sesiones de mesa hubo hoy?

### Tipo de cambio (API externa)
- ¿A cuánto está el dólar?
- ¿Cuál es el tipo de cambio hoy?
- ¿Cuánto vale el dólar en pesos?

---

## Preguntas fuera del alcance

El bot **no puede** responder sobre:
- Clientes o reservas (no hay esos datos en la BD)
- Órdenes individuales específicas
- Historial de pagos detallado
- Temas no relacionados al restaurante (el bot identifica chitchat y redirige)

---

## Cómo correr el bot

```powershell
# 1. Activar entorno virtual
.venv\Scripts\Activate.ps1

# 2. (Opcional) Actualizar datos vectoriales
python db_preparator.py

# 3. Terminal 1 — servidor de acciones
rasa run actions

# 4. Terminal 2 — shell del bot
rasa shell --endpoints endpoints.yml
```

Para reentrenar después de cambios en datos o dominio:
```powershell
rasa train
```
