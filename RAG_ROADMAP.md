# RAG İnteqrasiyası üçün Dərin Analiz və Yol Xəritəsi

Bu sənəd hazırkı branch-də olan `app.py` arxitekturasına əsaslanaraq, simptom triage modelinin "fantaziya" (hallucination) riskini azaltmaq üçün **RAG (Retrieval-Augmented Generation)** inteqrasiyasını mərhələli şəkildə izah edir.

## 1) Hazırkı sistemin real vəziyyəti (repo analizi)

Hazırkı backend artıq hibrit yanaşma istifadə edir:
- **Rule-based təhlükəsizlik qatları** (`detect_urgency_from_symptoms`, `detect_life_threatening_flags`) var.
- **LLM qatında JSON-only məcburiyyəti** və allowed labels var (`get_ai_symptom_assessment`).
- **Post-validation/safety merge** var (`choose_safe_specialty`, `max_urgency_level`).

Bu, yaxşı bazadır. Amma LLM hələ də əsasən prompt daxilindəki ümumi qaydalarla işləyir; mənbə sənədlərdən retrieval yoxdur. Yəni “insultu dermatoloqa yönləndirmə” kimi semantik drift halları tam sıfırlanmır.

## 2) RAG üçün minimal-invaziv dizayn (bu kod bazasına uyğun)

### Hədəf
LLM qərarını əvvəlcədən seçilmiş, etibarlı tibbi qaydalarla torpaqlamaq (grounding).

### Yeni axın (high-level)
1. İstifadəçi simptomu daxil edir (`/api/triage`).
2. Sistem simptomu normallaşdırır.
3. **Retriever** symptom sorğusuna ən yaxın triage qaydalarını qaytarır.
4. Bu qaydalar `get_ai_symptom_assessment` promptuna “evidence” kimi daxil edilir.
5. Model yalnız həmin evidence + mövcud safety qaydaları ilə JSON qaytarır.
6. Mövcud deterministic safety merge yenə qalır (critical).

Bu yanaşma mövcud funksiyalara ən az toxunuşla tətbiq edilə bilər.

## 3) Sənədləşdirilmiş tibbi source formatı

### Fayl strukturu (təklif)
- `knowledge/triage_rules.jsonl`

### JSONL nümunə sətirləri
Hər sətrdə 1 qayda:
```json
{"id":"rule_stroke_001","symptoms":["nitq pozulması","üz əyilməsi","qolda gücsüzlük"],"urgency":"RED","specialty":"neurologist","advice":"Stroke ehtimalı: dərhal təcili yardım.","source":"WHO stroke signs"}
{"id":"rule_derm_001","symptoms":["lokal səpgi","qaşınma","qızartı"],"urgency":"GREEN","specialty":"dermatologist","advice":"Kəskin sistemik əlamət yoxdursa planlı dermatoloji baxış.","source":"Primary care triage"}
```

### Məcburi sahələr
- `id`
- `symptoms` (array)
- `urgency` (`RED|YELLOW|GREEN`)
- `specialty` (mövcud allowed specialty list-dən)
- `source` (məs: WHO/ESI)

## 4) Vector DB seçimi (sənin mərhələ üçün praktik seçim)

Sənin “hələlik başlamaq” məqsədinə görə prioritet:
1. **Chroma (local persistent)** – sürətli start, infra minimum.
2. Pinecone – prod scale üçün yaxşıdır, amma ilkin mərhələdə əlavə DevOps yükü.
3. FAISS – local sürətli, amma metadata+ops baxımından Chroma rahatdır.

## 5) Kod səviyyəsində konkret inteqrasiya planı

## 5.1 Yeni modul: `rag_pipeline.py`
Funksiyalar:
- `load_rules(path) -> list[dict]`
- `index_rules(rules)`
- `retrieve_rules(query, top_k=5) -> list[dict]`
- `format_evidence(rules) -> str`

## 5.2 `app.py` daxilində inteqrasiya nöqtələri

### A) App start zamanı indeks hazırla
- `setup_database_automatically()` yaxınlığında bir dəfə knowledge index init.

### B) `analyze_symptoms_and_generate_map_ai(...)` daxilində retrieval çağır
- `full_case_text` və ya simptom mətni ilə `retrieve_rules(...)` çağır.
- Qayıdan top-k qaydaları `get_ai_symptom_assessment(...)`-ə yeni parametr kimi ötür.

### C) `get_ai_symptom_assessment(...)` promptunu genişləndir
- Prompta “Retrieved medical evidence (authoritative): ...” bloku əlavə et.
- Qayda: “evidence ilə ziddiyyət varsa, evidence üstünlük təşkil etsin.”

### D) Safety guard saxla
- Mövcud `choose_safe_specialty` + `max_urgency_level` mütləq qalmalıdır.
- RAG risk azaldır, amma deterministic guardrail-lər mütləq lazımdır.

## 6) Qəbul kriteriyaları (Definition of Done)

RAG inteqrasiyası tamam sayılmaq üçün:
- Stroke test cümlələri (`nitq pozulması`, `üz əyilməsi`, `weakness`) həmişə `RED + neurologist` qaytarsın.
- Lokal dəri simptomları `GREEN/YELLOW + dermatologist` xəttində qalsın.
- “Qeyri-müəyyən” inputlarda urgency aşağı düşməsin (under-triage yox).
- API response-a debug üçün `retrieved_rule_ids` əlavə olunsun.

## 7) Test planı (praktik)

### Unit testlər
- Retriever semantik uyğun qaydanı top-k daxilində tapsın.
- Evidence formatter boş/az nəticə hallarında stabil olsun.

### Integration testlər (`/api/triage`)
- 20-30 klinik scenario cədvəli ilə regression set.
- Hər scenario üçün gözlənilən `urgency` + `detected_specialty` assert.

### Safety metric
- `critical_mismatch_rate` (məs: stroke semptomu + qeyri-nevroloq yönləndirmə) = 0 hədəf.

## 8) Sənin bu branch üçün dərhal etməli olduğun işlər (prioritetlə)

1. `knowledge/triage_rules.jsonl` hazırlamaq (ən az 80-120 keyfiyyətli qayda).
2. `rag_pipeline.py` yazmaq (Chroma + embedding).
3. `get_ai_symptom_assessment`-ə evidence injection əlavə etmək.
4. `retrieved_rule_ids` response field əlavə etmək.
5. 20+ kritik ssenari üçün test faylı yazmaq.

## 9) Risklər və necə idarə etməli

- **Pis source keyfiyyəti** → yanlış retrieval.
  - Həll: yalnız kurasiya olunmuş WHO/ESI qaydaları.
- **Dil qarışıqlığı (AZ/EN/RU)**.
  - Həll: hər qaydaya sinonimlər və çoxdilli symptom variantları.
- **Top-k çox az/çox olması**.
  - Həll: 3,5,8 müqayisə ilə A/B test.

## 10) Tövsiyə edilən icra sırası (1 həftəlik sprint)

- Gün 1: Source schema + ilkin 100 qayda.
- Gün 2: Chroma index + retrieval API.
- Gün 3: Prompt grounding + response debug fields.
- Gün 4: Regression test set.
- Gün 5: Tuning (top-k, prompt constraint, threshold).

---

Əgər istəsən növbəti addımda bu planı birbaşa kodlayıb `rag_pipeline.py` + `knowledge/triage_rules.jsonl` skeleton-u da branch-ə əlavə edə bilərəm.
