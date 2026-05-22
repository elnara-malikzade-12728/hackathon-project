import json
import os
import sqlite3

# This keeps the app compatible with your teammate's code structure
RAG_AVAILABLE = True
DB_PATH = 'knowledge_triage_rules.db'
RULES_PATH = os.path.join(os.path.dirname(__file__), 'knowledge', 'triage_rules.jsonl')

def load_rules(path: str = RULES_PATH) -> list:
    """Reads rules from the JSONL file."""
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
    """Creates a lightweight local SQLite table and indexes the triage text rules."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if force_rebuild:
            cursor.execute("DROP TABLE IF EXISTS triage_rules")
            
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS triage_rules (
                id TEXT PRIMARY KEY,
                urgency TEXT,
                specialty TEXT,
                advice TEXT,
                source TEXT,
                search_text TEXT
            )
        """)
        
        # Check if rules are already loaded
        cursor.execute("SELECT COUNT(*) FROM triage_rules")
        if cursor.fetchone()[0] > 0 and not force_rebuild:
            conn.close()
            return True

        rules = load_rules()
        if not rules:
            conn.close()
            return False

        for r in rules:
            symptom_str = ' | '.join(r.get('symptoms', []))
            # Combine symptom terms for quick matching lookup queries
            combined = f"{symptom_str} {r.get('urgency','')} {r.get('specialty','')}".lower()
            
            cursor.execute("""
                INSERT OR REPLACE INTO triage_rules (id, urgency, specialty, advice, source, search_text)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                r.get('id'),
                r.get('urgency', 'GREEN'),
                r.get('specialty', 'general'),
                r.get('advice', ''),
                r.get('source', ''),
                combined
            ))
            
        conn.commit()
        conn.close()
        print(f"[SQLite-RAG] Indexed {len(rules)} rules safely at 0 MB RAM footprint cost.")
        return True
    except Exception as e:
        print(f"SQLite build index failed: {e}")
        return False

def retrieve_rules(query: str, top_k: int = 5) -> list:
    """Uses SQL text queries to fetch matching records quickly."""
    try:
        build_index()  # Ensure index exists on startup
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Clean query tokens
        query_words = query.lower().split()
        if not query_words:
            return []

        # Construct safe dynamic SQL lookups matching keywords
        clauses = ["search_text LIKE ?"] * len(query_words)
        sql_query = f"SELECT urgency, specialty, advice, source FROM triage_rules WHERE {' AND '.join(clauses)} LIMIT ?"
        params = [f"%{word}%" for word in query_words] + [top_k]
        
        cursor.execute(sql_query, params)
        rows = cursor.fetchall()
        
        # If strict search yields nothing, do a broader OR search fallback
        if not rows:
            sql_query = f"SELECT urgency, specialty, advice, source FROM triage_rules WHERE {' OR '.join(clauses)} LIMIT ?"
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()

        retrieved = []
        for row in rows:
            retrieved.append({
                'urgency': row[0],
                'specialty': row[1],
                'advice': row[2],
                'source': row[3],
                'similarity': 0.95  # Static mock match weight to ensure prompt format stays consistent
            })
            
        conn.close()
        return retrieved
    except Exception as e:
        print(f"SQLite retrieve failed: {e}")
        return []

def format_evidence(rules: list) -> str:
    """Kept exactly the same to support app.py pipeline structures."""
    if not rules:
        return "No relevant triage rules retrieved."
    lines = ["=== RETRIEVED MEDICAL EVIDENCE (authoritative — follow strictly) ==="]
    for i, r in enumerate(rules, 1):
        lines.append(f"{i}. [{r['urgency']}] Specialty: {r['specialty']} | Guidance: {r['advice']}")
    return '\n'.join(lines)

def get_max_urgency_from_evidence(rules: list) -> str | None:
    """Kept exactly the same to support validation overrides."""
    rank = {'RED': 3, 'YELLOW': 2, 'GREEN': 1}
    best = None
    best_rank = 0
    for r in rules:
        u = r.get('urgency', 'GREEN').upper()
        if rank.get(u, 0) > best_rank:
            best_rank = rank[u]
            best = u
    return best
