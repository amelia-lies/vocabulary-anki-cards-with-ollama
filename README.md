# Vocab Deck Builder

Genera tarjetas de vocabulario para con un LLM local
(Ollama), con memoria de duplicados, tarjetas cloze con opciones, y una
mini app web para capturar palabras desde texto, URL o PDF.


## Componentes

| Archivo | Qué hace |
|---|---|
| `models.py` | Esquemas Pydantic: tarjeta básica, tarjeta cloze, resultado de generación |
| `memory.py` | Memoria persistente en SQLite. Detecta duplicados por **lema** (conjugaciones/plurales) con `simplemma`, y por **similitud difusa** con `rapidfuzz` para variantes que el lematizador no atrapa |
| `generator.py` | Llama a Ollama en lotes; pasa el vocabulario ya existente como "pool" para que las distracciones del cloze salgan del mismo mazo |
| `extract.py` | Extrae texto de PDF (`pypdf`) o URL (`trafilatura`), y usa el LLM para minar términos candidatos de ese texto |
| `export.py` | Exporta a `.apkg` real de Anki (con `genanki`, tipo de nota Cloze nativo de Anki), además de `.tsv` y `.json` |
| `api.py` | Backend FastAPI que expone todo lo anterior como endpoints HTTP |
| `app_streamlit.py` | Interfaz web ligera (Streamlit) sobre el backend: pegar lista de palabras, pegar texto, pegar URL, subir PDF, ver el mazo y descargar |

## Instalación

```bash
pip install -r requirements.txt

# Instala Ollama (gratis, local): https://ollama.com
ollama pull llama3.1:8b
```

## Uso

Terminal 1 — backend:
```bash
python3 -m uvicorn api:app --reload --port 8000
```

Terminal 2 — interfaz web:
```bash
python3 -m streamlit run app_streamlit.py
```

Abre `http://localhost:8501`. Tienes 4 formas de capturar vocabulario:

1. **Lista de palabras** — pega una palabra o colocación por línea.
2. **Pegar texto** — pega un párrafo/artículo y el LLM extrae el vocabulario avanzado.
3. **Desde URL** — pega el link de un artículo; se descarga y limpia el texto automáticamente (`trafilatura`).
4. **Desde PDF** — sube un PDF (paper, capítulo, etc).

En la pestaña **"My deck"** puedes ver todo lo generado hasta ahora y
descargar el mazo completo como `.apkg` (listo para importar en Anki),
`.tsv` o `.json`.

## Cómo funciona la memoria (punto 1 de tu pedido)

Cada término que se convierte en tarjeta se guarda en `vocab_memory.db`
(SQLite, un solo archivo, no requiere servidor). Antes de generar una
tarjeta nueva:

1. Se compara el término exacto (case-insensitive).
2. Se lematiza palabra por palabra (`simplemma`, sin descargas, 100%
   local) y se compara el "lema" resultante — así "mitigating",
   "mitigated" y "mitigate" se reconocen como el mismo término.
3. Si nada de lo anterior coincide, se hace una comparación difusa
   (`rapidfuzz`) para atrapar variantes que el lematizador no cubre
   (errores tipográficos, variantes de ortografía, etc).

Los duplicados detectados se reportan (con el término contra el que
hicieron match y el motivo) en vez de generarse de nuevo.

## Cloze cards (punto 2)

Cada tarjeta básica viene con 2 ejercicios cloze (`{{c1::palabra}}` en
el `.apkg`, usando el **tipo de nota Cloze nativo de Anki**). Cada
ejercicio incluye 3-4 opciones de respuesta; el modelo prioriza sacar
las opciones incorrectas del mismo mazo de vocabulario que ya
construiste (se le pasa como contexto en el prompt), en vez de inventar
palabras sueltas.

La generación de la tarjeta básica y del cloze son **dos llamadas
separadas** al modelo. Así, si el cloze falla (el modelo local a veces
no devuelve el JSON exacto que se le pide), la tarjeta básica no se
pierde — se guarda igual, solo sin cloze, y el error real se reporta
en la interfaz (nunca se confunde con "duplicado").

## Sentidos múltiples (palabras como "make up")

El prompt por defecto le pide al modelo distinguir entre:
- Palabras con **un solo sentido común** → una sola definición + 5 ejemplos.
- Palabras genuinamente **polisémicas y comunes** (como "make up":
  inventar una historia / maquillarse / constituir un todo /
  reconciliarse) → una tarjeta con varios "sentidos" (`senses`), cada
  uno con su propia etiqueta corta, definición y ejemplos.

El propio prompt le pide al modelo usar criterio: si un posible
significado es raro, arcaico o muy técnico/nicho, **no** debe separarse
en su propio sentido — solo se agregan sentidos cuando de verdad son de
uso común. Puedes editar este criterio libremente en la pestaña
**Prompts** de la interfaz.

## Borrar una palabra (punto nuevo)

En la pestaña **"My deck"** puedes elegir cualquier término ya
generado, ver una vista previa de todo lo que se creó para él
(definición/sentidos, ejemplos, cloze) y borrarlo por completo con un
clic (con checkbox de confirmación). Al borrarlo:
- Se elimina la fila completa de `vocab_memory.db` (definición, sentidos,
  ejemplos y cloze — todo vive junto en un solo registro).
- El término queda libre para volver a generarse desde cero la próxima
  vez que lo pidas, ya que deja de estar en la memoria de duplicados.

## Prompts editables (punto nuevo)

Nueva pestaña **"Prompts"** en la interfaz: puedes editar en caliente
los tres prompts del sistema (tarjeta básica, cloze, extracción de
términos desde texto/URL/PDF), guardarlos, o resetear cada uno a su
valor por defecto. Se guardan en `prompts.json` (se crea solo la
primera vez que corres el backend) — no hace falta tocar código.
Los cambios aplican a la **siguiente** generación; no regeneran
tarjetas ya creadas.

## Notas / próximos pasos posibles

- El extractor de términos (`extract.py`) usa el mismo modelo de
  Ollama que el generador; puedes usar un modelo más chico ahí si
  quieres respuestas más rápidas.
- `FUZZY_THRESHOLD` en `memory.py` (default 88) controla qué tan
  estricta es la detección de duplicados — bájalo si quieres que
  atrape más variantes (a costa de más falsos positivos).
- Para producción real (multiusuario) cambiarías SQLite por Postgres,
  pero para uso personal esto es intencionalmente cero-configuración.
