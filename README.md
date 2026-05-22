# Symptom Triage (Hackathon Project)

AI-assisted symptom triage prototype that classifies urgency (RED / YELLOW / GREEN), recommends a likely medical specialty, and suggests nearby hospitals and pharmacies using live OpenStreetMap data. The UI supports **Azerbaijani, English, and Russian** and is designed for fast, safety-first guidance during a hackathon demo.

> **Disclaimer:** This is a hackathon prototype and not medical advice. If symptoms are severe or life-threatening, contact emergency services immediately.
## Key Features
- **Urgency triage** with deterministic safety rules (life-threatening red flags, pediatric/escalation logic).
- **Specialty routing** based on multilingual symptom keywords and patient context.
- **Optional AI assessment** via OpenAI (structured JSON output + safety merge).
- **RAG evidence grounding** using local triage rules in `knowledge/triage_rules.jsonl` with ChromaDB.
- **Nearby care discovery** from OpenStreetMap (Overpass + Nominatim) and fallback local facility list.
- **Pharmacy suggestions** with caching and distance ranking.
- **Multi-language UI** with consistent outputs across AZ/EN/RU.

## Tech Stack
- **Backend:** Flask (`app.py`)
- **RAG:** ChromaDB + `sentence-transformers` (`rag_pipeline.py`)
- **AI (optional):** OpenAI API (gpt-4o-mini)
- **Maps:** Leaflet + OpenStreetMap tiles (frontend)
- **Geolocation:** Browser geolocation + Overpass/Nominatim
- **Storage:** Local SQLite audit log (`ai_auto_map_audit.db`)

## Repository Structure
- `app.py` — main Flask server, triage logic, OSM integration, caching
- `rag_pipeline.py` — RAG index/build/retrieve helpers
- `knowledge/triage_rules.jsonl` — curated triage rules for retrieval
- `knowledge/chroma_store/` — persistent Chroma vector store
- `templates/index.html` — web UI
- `static/script.js` / `static/style.css` — UI logic and styling

## Getting Started
### Prerequisites
- **Python 3.10+** (required for modern type syntax)

### Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration (Optional)
Create a `.env` file in the project root (loaded automatically):
```bash
OPENAI_API_KEY=your_key_here
USE_AI_SYMPTOMS=true
```
- If `OPENAI_API_KEY` is missing or `USE_AI_SYMPTOMS` is false, the app uses the deterministic triage engine only.
- RAG retrieval is used to **ground AI responses** when AI is enabled.

### Run Locally
```bash
python app.py
```
Open: **http://localhost:5005**

### Production (example)
```bash
gunicorn --bind 0.0.0.0:5005 app:app
```

## API Endpoints
### `POST /api/triage`
Analyzes symptoms and returns urgency, specialty, and nearby care suggestions.

**Request body (JSON):**
```json
{
  "symptoms": "Qəfil sinə ağrısı və nəfəs darlığı",
  "latitude": 40.3700,
  "longitude": 49.8372,
  "age": 35,
  "gender": "Female",
  "chronic_conditions": "diabet",
  "use_specialty": true
}
```

**Response (JSON, simplified):**
```json
{
  "status": "success",
  "data": {
    "city": "Baku",
    "urgency": "RED",
    "detected_specialty": "cardiologist",
    "specialist": {"en": "Cardiologist", "az": "Kardioloq", "ru": "Кардиолог"},
    "reason": {"en": "...", "az": "...", "ru": "..."},
    "critical_flags": ["possible_acute_cardiac_event"],
    "hospitals": ["..."],
    "pharmacies": ["..."]
  }
}
```

### `GET /api/hospitals`
Fetches hospitals/clinics near coordinates.

**Query params:** `lat`, `lng`, `radius`, `specialty`, `urgency`, `city`

Example:
```
/api/hospitals?lat=40.3700&lng=49.8372&radius=10&specialty=cardiologist&urgency=RED
```

## RAG Knowledge Base
- Rules live in `knowledge/triage_rules.jsonl` (one JSON object per line).
- The Chroma index is stored in `knowledge/chroma_store/` and built at startup.
- To refresh rules, update the JSONL file and rebuild the index (e.g., delete the folder or run `build_index(force_rebuild=True)` from a Python shell).

## Notes & Safety
- The app **logs triage requests locally** to `ai_auto_map_audit.db` for analytics.
- Emergency advice in the UI is tailored for Azerbaijan (e.g., emergency number 103). Update the language dictionary in `static/script.js` if deploying to other regions.

---
If you want a fuller roadmap for RAG improvements, see `RAG_ROADMAP.md`.
