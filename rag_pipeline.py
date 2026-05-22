"""
rag_pipeline.py
RAG (Retrieval-Augmented Generation) modulu.
ChromaDB + çoxdilli sentence-transformers istifadə edir.
OpenAI API key tələb etmir.
"""

import json
import os

try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# ── Sabitlər ──────────────────────────────────────────────────────────────
RULES_PATH   = os.path.join(os.path.dirname(__file__), 'knowledge', 'triage_rules.jsonl')
CHROMA_DIR   = os.path.join(os.path.dirname(__file__), 'knowledge', 'chroma_store')
COLLECTION   = 'triage_rules'
# 50+ dili dəstəkləyən model — Azərbaycan, ingilis, rus işləyir
EMBED_MODEL  = 'paraphrase-multilingual-MiniLM-L12-v2'

_embedder   = None
_collection = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = client.get_or_create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


def load_rules(path: str = RULES_PATH) -> list:
    """JSONL faylından qaydaları oxu."""
    rules = []
    if not os.path.exists(path):
        return rules
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rules.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rules


def build_index(force_rebuild: bool = False) -> bool:
    """
    Qaydaları vektora çevirib ChromaDB-yə yükləyir.
    force_rebuild=True olarsa mövcud indeksi silir və yenidən qurur.
    """
    if not RAG_AVAILABLE:
        print("[RAG] chromadb və ya sentence-transformers qurulmayıb.")
        return False

    col = _get_collection()

    if not force_rebuild and col.count() > 0:
        print(f"[RAG] İndeks mövcuddur ({col.count()} qayda). Yenidən qurmaq üçün force_rebuild=True.")
        return True

    rules = load_rules()
    if not rules:
        print("[RAG] knowledge/triage_rules.jsonl tapılmadı və ya boşdur.")
        return False

    embedder = _get_embedder()

    # Hər qayda üçün axtarış mətni: simptomlar + urgency + specialty
    texts = []
    for r in rules:
        symptom_str = ' | '.join(r.get('symptoms', []))
        combined    = f"{symptom_str} urgency:{r.get('urgency','')} specialty:{r.get('specialty','')}"
        texts.append(combined)

    embeddings = embedder.encode(texts, show_progress_bar=False).tolist()

    if force_rebuild:
        col.delete(where={"id": {"$ne": "__none__"}})  # hamısını sil

    col.add(
        ids        = [r['id'] for r in rules],
        embeddings = embeddings,
        documents  = texts,
        metadatas  = [
            {
                'urgency':   r.get('urgency', 'GREEN'),
                'specialty': r.get('specialty', 'general'),
                'advice':    r.get('advice', ''),
                'source':    r.get('source', ''),
                'symptoms':  ' | '.join(r.get('symptoms', []))
            }
            for r in rules
        ]
    )

    print(f"[RAG] {len(rules)} qayda ChromaDB-yə yükləndi.")
    return True


def retrieve_rules(query: str, top_k: int = 5) -> list:
    """
    Simptom sorğusuna ən uyğun qaydaları qaytarır.
    Hər element: {'id', 'urgency', 'specialty', 'advice', 'source', 'similarity'}
    """
    if not RAG_AVAILABLE:
        return []

    col = _get_collection()
    if col.count() == 0:
        build_index()
        if col.count() == 0:
            return []

    embedder  = _get_embedder()
    query_vec = embedder.encode([query], show_progress_bar=False).tolist()

    results = col.query(
        query_embeddings = query_vec,
        n_results        = min(top_k, col.count()),
        include          = ['metadatas', 'distances']
    )

    retrieved = []
    for meta, dist in zip(results['metadatas'][0], results['distances'][0]):
        similarity = round(1 - dist, 3)   # cosine similarity
        if similarity < 0.25:             # çox uzaq qaydaları atla
            continue
        retrieved.append({
            'urgency':    meta.get('urgency', 'GREEN'),
            'specialty':  meta.get('specialty', 'general'),
            'advice':     meta.get('advice', ''),
            'source':     meta.get('source', ''),
            'symptoms':   meta.get('symptoms', ''),
            'similarity': similarity
        })

    return retrieved


def format_evidence(rules: list) -> str:
    """Alınan qaydaları prompt üçün oxunaqlı formata çevir."""
    if not rules:
        return "No relevant triage rules retrieved."

    lines = ["=== RETRIEVED MEDICAL EVIDENCE (authoritative — follow strictly) ==="]
    for i, r in enumerate(rules, 1):
        lines.append(
            f"{i}. [{r['urgency']}] Specialty: {r['specialty']} | "
            f"Match: {r['similarity']} | "
            f"Guidance: {r['advice']} | "
            f"Source: {r['source']}"
        )
    lines.append(
        "RULE: If your assessment contradicts the above evidence, "
        "the evidence takes priority unless the patient's symptoms clearly indicate higher urgency."
    )
    return '\n'.join(lines)


def get_max_urgency_from_evidence(rules: list) -> str | None:
    """
    Alınan qaydalar arasında ən yüksək urgency-ni qaytarır.
    Hallucination-a qarşı: AI GREEN desə də evidence RED varsa → RED.
    """
    rank = {'RED': 3, 'YELLOW': 2, 'GREEN': 1}
    best = None
    best_rank = 0
    for r in rules:
        u = r.get('urgency', 'GREEN').upper()
        if rank.get(u, 0) > best_rank:
            best_rank = rank[u]
            best = u
    return best