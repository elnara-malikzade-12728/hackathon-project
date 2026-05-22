import math
import os
import json
import re
import sys
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from geopy.distance import geodesic
from openai import OpenAI


def configure_output_encoding():
    """Force UTF-8 output where supported to avoid Windows console encoding crashes."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8')
            except Exception:
                pass


def load_local_env(path='.env'):
    """Lightweight .env loader to keep local secrets out of source code."""
    if not os.path.exists(path):
        return

    try:
        with open(path, 'r', encoding='utf-8') as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


configure_output_encoding()
load_local_env()
app = Flask(__name__)
DB_FILE = 'ai_auto_map_audit.db'
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
USE_AI_SYMPTOMS = os.environ.get('USE_AI_SYMPTOMS', 'false').lower() in ('1', 'true', 'yes')
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
SPECIALTY_SIGNAL_MAP = {
    'dentist': {
        'high': [
            'diş', 'diş əti', 'ağıl dişi', 'tooth', 'teeth', 'gum', 'wisdom tooth',
            'stomatolog', 'стоматолог', 'зуб', 'десна'
        ],
        'medium': [
            'toothache', 'dental', 'karies', 'karyes', 'cavity', 'root canal',
            'çənə', 'jaw', 'cold water pain', 'sensitivity'
        ]
    },
    'dermatologist': {
        'high': [
            'dəri', 'xal', 'sivilcə', 'səpgi', 'qaşınma', 'qaşıntı', 'qabıqlanma',
            'skin', 'acne', 'rash', 'itch', 'eczema', 'psoriasis', 'mole',
            'кожа', 'сыпь', 'зуд', 'прыщ'
        ],
        'medium': [
            'pustular', 'pustule', 'blackhead', 'scalp', 'baş dərisi', 'seborrhea',
            'pigment', 'asymmetrical', 'asimmetrik', 'color change', 'rəngini dəyişib'
        ]
    },
    'cardiologist': {
        'high': [
            'sinə', 'döş', 'ürək', 'aritmiya', 'nizamsız döyüntü', 'chest', 'heart',
            'arrhythmia', 'palpitation', 'palpitations', 'angina', 'cardiac',
            'грудь', 'сердце', 'аритмия'
        ],
        'medium': [
            'chest tightness', 'tightness', 'shortness of breath', 'nəfəs darlığı',
            'qan təzyiqi', 'blood pressure'
        ]
    },
    'ophthalmologist': {
        'high': [
            'göz', 'görmə', 'bulanıq', 'göz qapağı', 'itdirsəyi', 'arpacıq',
            'eye', 'vision', 'blurred vision', 'eyelid', 'stye',
            'глаз', 'зрение', 'веко'
        ],
        'medium': [
            'quruluq', 'batma', 'göz ağrısı', 'göz iltihabı', 'red eye',
            'itchy eyes', 'light sensitivity', 'контактные линзы'
        ]
    },
    'orthopedic': {
        'high': [
            'bel', 'diz', 'oynaq', 'bilək', 'burxdum', 'sınıq', 'əzələ', 'sümük',
            'back', 'knee', 'joint', 'wrist', 'sprain', 'fracture', 'bone',
            'сустав', 'перелом', 'колено', 'запястье'
        ],
        'medium': [
            'stiffness', 'morning stiffness', 'xırtıltı', 'şişkinlik', 'swelling',
            'hip', 'arm', 'leg', 'mobility'
        ]
    },
    'neurologist': {
        'high': [
            'baş ağrısı', 'miqren', 'başgicəllənmə', 'nevroloq', 'headache', 
            'migraine', 'dizziness', 'головная боль', 'мигрень', 'головокружение', 'невролог'
        ],
        'medium': [
            'uyuşma', 'numbness', 'zəiflik', 'weakness', 'titrəmə', 'tremor', 'онемение', 'слабость'
        ]
    },
    'gastroenterologist': {
        'high': [
            'mədə', 'bağırsaq', 'qusma', 'ishal', 'qastroenteroloq', 'stomach', 
            'intestine', 'vomiting', 'diarrhea', 'желудок', 'кишечник', 'рвота', 'диарея', 'гастроэнтеролог'
        ],
        'medium': [
            'ürəkbulanma', 'nausea', 'qəbzlik', 'constipation', 'həzmsizlik', 'indigestion', 'тошнота', 'запор'
        ]
    },
    'otolaryngologist': {
        'high': [
            'qulaq', 'boğaz', 'burun', 'badamcıq', 'lor', 'ear', 'nose', 'throat', 
            'ухо', 'горло', 'нос', 'лор', 'отоларинголог'
        ],
        'medium': [
            'burun axması', 'runny nose', 'udqunma', 'swallowing', 'səs batması', 'насморк', 'глотание'
        ]
    },
    'pediatrician': {
        'high': [
            'uşaq', 'körpə', 'pediatr', 'child', 'baby', 'infant', 'pediatrician', 
            'ребенок', 'малыш', 'педиатр'
        ],
        'medium': [
            'ağlamaq', 'süd', 'crying', 'breastfeeding', 'плач', 'кормление'
        ]
    },
    'gynecologist': {
        'high': [
            'hamilə', 'aybaşı', 'menstruasiya', 'ginekoloq', 'pregnant', 'pregnancy', 
            'period', 'menstruation', 'gynecologist', 'беременность', 'менструация', 'гинеколог'
        ],
        'medium': [
            'axıntı', 'discharge', 'qasıq', 'pelvic', 'выделения'
        ]
    },
    'urologist': {
        'high': [
            'böyrək', 'sidik', 'uroloq', 'kidney', 'urine', 'urination', 'urologist', 
            'почка', 'моча', 'уролог'
        ],
        'medium': [
            'yanma', 'tez-tez sidiyə getmə', 'burning', 'frequent urination', 'жжение при мочеиспускании'
        ]
    }
}

SPECIALTY_KEYWORD_MAP = {
    specialty: signals['high'] + signals['medium']
    for specialty, signals in SPECIALTY_SIGNAL_MAP.items()
}

SPECIALTY_PRIORITY = [
    'cardiologist', 'pediatrician', 'gynecologist', 'neurologist', 
    'ophthalmologist', 'otolaryngologist', 'gastroenterologist', 
    'urologist', 'orthopedic', 'dentist', 'dermatologist'
]
ALLOWED_SPECIALTIES = set(SPECIALTY_SIGNAL_MAP.keys()) | {'general'}

RED_URGENCY_PHRASES = [
    'heart attack', 'cardiac arrest', 'cannot breathe', 'cant breathe',
    'difficulty breathing', 'severe bleeding', 'cannot stop bleeding',
    'uncontrollable bleeding', 'lost consciousness', 'unconscious', 'seizure',
    'stroke', 'paralysis', 'face droop', 'facial droop', 'anaphylaxis',
    'chemical', 'chemical burn', 'kimyəvi', 'yanıq', 'korluq', 'görmənin itməsi',
    'şüur itkisi', 'nəfəs ala bilmir', 'nəfəs ala bilmirəm', 'dayanmayan qanaxma',
    'kəskin iflic', 'инсульт', 'потеря сознания', 'остановка сердца', 'химический ожог'
]
YELLOW_URGENCY_PHRASES = [
    'chest tightness', 'sinə sıxıntısı', 'döş qəfəsində sıxıntı', 'arrhythmia',
    'aritmiya', 'palpitations', 'irregular heartbeat', 'sprain', 'burxdum',
    'fracture', 'sınıq', 'severe eye pain', 'göz iltihabı',
    'vision loss', 'sudden blurred vision', 'high fever', 'qızdırma', 'deep cut',
    'severe abdominal pain', 'morning stiffness', 'şiddətli tutulma', 'xırtıltı',
    'ağıl dişi', 'wisdom tooth', 'qulağa vuran ağrı', 'radiates to my ear'
]
MILD_QUALIFIERS = [
    'mild', 'slight', 'light', 'yüngül', 'az', 'stabil', 'minor'
]
URGENCY_RANK = {'GREEN': 0, 'YELLOW': 1, 'RED': 2}

PEDIATRIC_ALERT_PHRASES = [
    'qızdırma', 'fever', '38', '38.5', '39', 'qus', 'vomit', 'vomiting',
    'ishal', 'diarrhea', 'ağlayır', 'persistent crying', 'qulaq', 'ear',
    'halsız', 'lethargy'
]

CARDIAC_ALERT_PHRASES = [
    'sinə', 'döş', 'chest', 'ürək', 'heart', 'aritmiya', 'arrhythmia',
    'nəfəs darlığı', 'shortness of breath', 'palpitations', 'nizamsız döyüntü'
]

INFECTION_ALERT_PHRASES = [
    'qızdırma', 'fever', 'infeksiya', 'infection', 'vomit', 'qus',
    'diarrhea', 'ishal', 'titreme', 'chills'
]

CHRONIC_RISK_TERMS = {
    'cardio': [
        'hipertoniya', 'yüksək təzyiq', 'təzyiq', 'xolesterin', 'ürək',
        'hypertension', 'high blood pressure', 'cholesterol', 'heart disease',
        'гипертония', 'давление', 'холестерин', 'сердце'
    ],
    'diabetes': ['diabet', 'diabetes', 'сахарный диабет', 'диабет'],
    'respiratory': ['astma', 'asma', 'copd', 'koah', 'asthma', 'астма'],
    'renal': ['böyrək', 'kidney', 'renal', 'почка'],
    'immunosuppressed': [
        'onkoloji', 'xərçəng', 'kemoterapi', 'immun çatışmazlığı',
        'cancer', 'chemotherapy', 'immunosuppressed', 'онкология', 'рак'
    ],
    'pregnancy': ['hamilə', 'pregnant', 'pregnancy', 'беремен']
}
SPECIALTY_SEARCH_CLAUSES = {
    'dentist': [
        'node["healthcare"="dentist"]',
        'way["healthcare"="dentist"]',
        'relation["healthcare"="dentist"]',
        'node["healthcare:specialty"="dentist"]',
        'way["healthcare:specialty"="dentist"]',
        'relation["healthcare:specialty"="dentist"]'
    ],
    'dermatologist': [
        'node["healthcare"="dermatologist"]',
        'way["healthcare"="dermatologist"]',
        'relation["healthcare"="dermatologist"]',
        'node["healthcare:specialty"="dermatologist"]',
        'way["healthcare:specialty"="dermatologist"]',
        'relation["healthcare:specialty"="dermatologist"]'
    ],
    'cardiologist': [
        'node["healthcare"="cardiologist"]',
        'way["healthcare"="cardiologist"]',
        'relation["healthcare"="cardiologist"]',
        'node["healthcare:specialty"="cardiologist"]',
        'way["healthcare:specialty"="cardiologist"]',
        'relation["healthcare:specialty"="cardiologist"]'
    ],
    'ophthalmologist': [
        'node["healthcare"="ophthalmologist"]',
        'way["healthcare"="ophthalmologist"]',
        'relation["healthcare"="ophthalmologist"]',
        'node["healthcare:specialty"="ophthalmologist"]',
        'way["healthcare:specialty"="ophthalmologist"]',
        'relation["healthcare:specialty"="ophthalmologist"]'
    ],
    'orthopedic': [
        'node["healthcare"="orthopedic"]',
        'way["healthcare"="orthopedic"]',
        'relation["healthcare"="orthopedic"]',
        'node["healthcare:specialty"="orthopedic"]',
        'way["healthcare:specialty"="orthopedic"]',
        'relation["healthcare:specialty"="orthopedic"]'
    ],
    'neurologist': [
        'node["healthcare"="neurologist"]',
        'way["healthcare"="neurologist"]',
        'relation["healthcare"="neurologist"]',
        'node["healthcare:specialty"="neurology"]',
        'way["healthcare:specialty"="neurology"]'
    ],
    'gastroenterologist': [
        'node["healthcare"="gastroenterologist"]',
        'way["healthcare"="gastroenterologist"]',
        'relation["healthcare"="gastroenterologist"]',
        'node["healthcare:specialty"="gastroenterology"]',
        'way["healthcare:specialty"="gastroenterology"]'
    ],
    'otolaryngologist': [
        'node["healthcare"="otolaryngologist"]',
        'way["healthcare"="otolaryngologist"]',
        'relation["healthcare"="otolaryngologist"]',
        'node["healthcare:specialty"="otolaryngology"]',
        'way["healthcare:specialty"="otolaryngology"]'
    ],
    'pediatrician': [
        'node["healthcare"="pediatrician"]',
        'way["healthcare"="pediatrician"]',
        'node["healthcare:specialty"="paediatrics"]',
        'way["healthcare:specialty"="paediatrics"]',
        'node["healthcare:specialty"="pediatrics"]'
    ],
    'gynecologist': [
        'node["healthcare"="gynecologist"]',
        'way["healthcare"="gynecologist"]',
        'node["healthcare:specialty"="gynaecology"]',
        'way["healthcare:specialty"="gynaecology"]',
        'node["healthcare:specialty"="gynecology"]'
    ],
    'urologist': [
        'node["healthcare"="urologist"]',
        'way["healthcare"="urologist"]',
        'node["healthcare:specialty"="urology"]',
        'way["healthcare:specialty"="urology"]'
    ]
}
NEARBY_HOSPITAL_DATABASE = [
    {'name': 'Baku Central Clinical Hospital', 'address': 'Parliament Ave 76', 'latitude': 40.3669, 'longitude': 49.8254, 'has_emergency': True},
    {'name': 'Republican Clinical Hospital', 'address': 'A.M.Sharifzade Ave', 'latitude': 40.4048, 'longitude': 49.8075, 'has_emergency': True},
    {'name': 'Neftchilar Medical Center', 'address': 'Baku Blvd', 'latitude': 40.3690, 'longitude': 49.7080, 'has_emergency': False},
    {'name': 'Baku City Hospital', 'address': 'Yusif Vazir St', 'latitude': 40.3850, 'longitude': 49.7120, 'has_emergency': False},
    {'name': 'City Emergency Clinic', 'address': 'Yusif Vazir St', 'latitude': 40.3920, 'longitude': 49.6750, 'has_emergency': True},
    {'name': 'Ganja City Hospital No.1', 'address': 'Attar St', 'latitude': 40.6820, 'longitude': 46.3640, 'has_emergency': True},
    {'name': 'International Health Center Ganja', 'address': 'Heydar Aliyev Ave', 'latitude': 40.6850, 'longitude': 46.3710, 'has_emergency': False},
    {'name': 'Ganja Clinic & Diagnostics', 'address': 'Mingachevir Hwy', 'latitude': 40.6750, 'longitude': 46.3580, 'has_emergency': False},
    {'name': 'Sumqayit City Hospital', 'address': 'Central Ave', 'latitude': 40.5880, 'longitude': 49.6730, 'has_emergency': True},
    {'name': 'Sumqayit Clinic Center', 'address': 'Komsomol St', 'latitude': 40.5920, 'longitude': 49.6820, 'has_emergency': False}
]

def normalize_symptom_text(text):
    """Normalize symptom text for multilingual keyword matching."""
    text = (text or '').lower()
    text = re.sub(r'[\s\r\n\t]+', ' ', text)
    return f" {text} "


def parse_age(value):
    """Safely parse age from request payload."""
    try:
        if value in (None, '', 'Göstərilməyib', 'Not specified'):
            return None
        age = int(float(value))
        if 0 <= age <= 120:
            return age
    except (TypeError, ValueError):
        return None
    return None


def build_patient_context(age=None, gender=None, chronic_conditions=''):
    """Create patient-level risk context used in triage scoring and specialty routing."""
    age_value = parse_age(age)
    gender_text = (gender or '').strip().lower()
    chronic_text = normalize_symptom_text(chronic_conditions or '')

    risk_flags = {}
    for flag, terms in CHRONIC_RISK_TERMS.items():
        risk_flags[flag] = any(term in chronic_text for term in terms)

    return {
        'age': age_value,
        'gender': gender_text,
        'chronic_text': chronic_text.strip(),
        'risk_flags': risk_flags,
        'is_infant': age_value is not None and age_value <= 2,
        'is_child': age_value is not None and age_value <= 14,
        'is_elderly': age_value is not None and age_value >= 60
    }


def detect_specialty_from_symptoms(text, patient_context=None):
    """Score symptoms and return the most likely specialist domain."""
    text_lower = normalize_symptom_text(text)
    scores = {}

    for specialty, signals in SPECIALTY_SIGNAL_MAP.items():
        score = 0
        score += sum(3 for keyword in signals['high'] if keyword in text_lower)
        score += sum(1 for keyword in signals['medium'] if keyword in text_lower)
        scores[specialty] = score

    if patient_context:
        # Young children should be routed to pediatrics for mixed acute complaints.
        if patient_context.get('is_child') and any(term in text_lower for term in PEDIATRIC_ALERT_PHRASES):
            scores['pediatrician'] = scores.get('pediatrician', 0) + 4

        # Elderly + chest/cardiac symptoms should strongly favor cardiology.
        if patient_context.get('is_elderly') and any(term in text_lower for term in CARDIAC_ALERT_PHRASES):
            scores['cardiologist'] = scores.get('cardiologist', 0) + 3

        # Pregnancy context should prioritize gynecology for abdominal/pelvic symptom wording.
        if (
            patient_context.get('risk_flags', {}).get('pregnancy') and
            any(term in text_lower for term in ['abdominal pain', 'qarın ağrısı', 'pelvic', 'qasıq', 'bleeding', 'qanaxma'])
        ):
            scores['gynecologist'] = scores.get('gynecologist', 0) + 4

        # Known kidney disease + urinary phrases should favor urology.
        if (
            patient_context.get('risk_flags', {}).get('renal') and
            any(term in text_lower for term in ['sidik', 'urine', 'urination', 'böyrək', 'kidney', 'burning'])
        ):
            scores['urologist'] = scores.get('urologist', 0) + 3

    max_score = max(scores.values()) if scores else 0
    if max_score <= 0:
        if patient_context and patient_context.get('is_child'):
            return 'pediatrician'
        return None

    top_specialties = [spec for spec, score in scores.items() if score == max_score]
    for spec in SPECIALTY_PRIORITY:
        if spec in top_specialties:
            return spec
    return top_specialties[0]


def detect_urgency_from_symptoms(text, patient_context=None, detected_specialty=None):
    """Classify urgency with context-aware escalation using age and chronic risk."""
    text_lower = normalize_symptom_text(text)

    if any(phrase in text_lower for phrase in RED_URGENCY_PHRASES):
        return "RED"

    urgency_score = 0
    if any(phrase in text_lower for phrase in YELLOW_URGENCY_PHRASES):
        urgency_score += 2

    if any(phrase in text_lower for phrase in MILD_QUALIFIERS):
        urgency_score -= 1

    if patient_context:
        risk_flags = patient_context.get('risk_flags', {})

        if patient_context.get('is_infant') and any(term in text_lower for term in PEDIATRIC_ALERT_PHRASES):
            urgency_score += 2
        elif patient_context.get('is_child') and any(term in text_lower for term in PEDIATRIC_ALERT_PHRASES):
            urgency_score += 1

        if patient_context.get('is_elderly') and any(term in text_lower for term in CARDIAC_ALERT_PHRASES):
            urgency_score += 2

        if (risk_flags.get('cardio') or risk_flags.get('diabetes')) and any(term in text_lower for term in CARDIAC_ALERT_PHRASES):
            urgency_score += 2

        if (risk_flags.get('immunosuppressed') or risk_flags.get('diabetes')) and any(term in text_lower for term in INFECTION_ALERT_PHRASES):
            urgency_score += 1

        if risk_flags.get('pregnancy') and any(term in text_lower for term in ['qanaxma', 'bleeding', 'qarın ağrısı', 'abdominal pain']):
            urgency_score += 2

    if detected_specialty in ('cardiologist', 'urologist', 'otolaryngologist') and urgency_score > 0:
        urgency_score += 1

    return "YELLOW" if urgency_score >= 2 else "GREEN"


def max_urgency_level(primary, secondary):
    """Return higher urgency from two labels."""
    p = str(primary or 'GREEN').upper()
    s = str(secondary or 'GREEN').upper()
    return p if URGENCY_RANK.get(p, 0) >= URGENCY_RANK.get(s, 0) else s


def get_ai_symptom_assessment(text, city, detected_specialty=None, patient_context=None):
    """Use an OpenAI model to interpret symptoms and return structured triage output."""
    if not USE_AI_SYMPTOMS or not OPENAI_API_KEY or not client:
        return None

    try:
        client.api_key = OPENAI_API_KEY
        age_context = patient_context.get('age') if patient_context else None
        gender_context = patient_context.get('gender') if patient_context else ''
        chronic_context = patient_context.get('chronic_text') if patient_context else ''

        prompt = (
            "You are a highly sensitive and strict multilingual medical triage assistant.\n"
            "Input can be Azerbaijani, English, Russian, or mixed.\n"
            "Always analyze the context of the sentence, not just isolated words. Detect BOTH urgency and the most relevant specialist.\n\n"
            "Allowed urgency labels: RED, YELLOW, GREEN.\n"
            "Allowed detected_specialty labels: dentist, dermatologist, cardiologist, ophthalmologist, orthopedic, neurologist, gastroenterologist, otolaryngologist, pediatrician, gynecologist, urologist, general.\n\n"            "Decision protocol:\n"
            "1) Detect the dominant clinical domain first, then map to detected_specialty.\n"
            "2) If symptoms clearly point to one organ system, do NOT return general.\n"
            "3) RED is for IMMEDIATE LIFE-THREATENING OR ORGAN-THREATENING emergencies. This includes: severe breathing distress, uncontrolled bleeding, stroke signs, loss of consciousness, seizure, anaphylaxis, suspected heart attack, CHEMICAL BURNS, chemical splash in eyes, sudden complete vision loss, or severe traumatic deformity.\n"
            "4) YELLOW for urgent conditions requiring prompt care but no immediate risk of death/organ loss: arrhythmia, chest tightness with exertion, simple fractures/sprains with swelling, acute infections, severe dental swelling/abscess, or non-chemical sudden eye inflammation.\n"
            "5) GREEN for stable outpatient conditions: acne, rash, itching, chronic joint/back pain, gum bleeding, non-acute dental sensitivity.\n"
            "6) Context Matters: Even if the user types 'yüngül' (mild), if they describe a chemical splashing into their eye, the situation is RED. Read the action described.\n\n"
            "Specialist mapping anchors:\n"
            "- Dermatologist: acne/rash/itching/flaking/mole changes. (Chemical skin burns go to RED / Emergency).\n"
            "- Ophthalmologist: dry eye, blurred vision, stye. (Chemical splash in eye goes to Ophthalmologist AND RED urgency).\n"
            "- Cardiologist: chest tightness, palpitations, arrhythmia.\n"
            "- Orthopedic: sprain, fracture, joint pain/stiffness.\n"
            "- Dentist: tooth/gum pain, wisdom tooth eruption, facial swelling from tooth.\n\n"
            "- Neurologist: headache, migraine, dizziness, numbness, tremors.\n"
            "- Gastroenterologist: stomach pain, vomiting, diarrhea, nausea.\n"
            "- Otolaryngologist: ear/nose/throat pain, runny nose, difficulty swallowing.\n"
            "- Pediatrician: symptoms specifically mentioning a child, baby, or infant.\n"
            "- Gynecologist: pregnancy, menstruation issues, pelvic pain in females.\n"
            "- Urologist: kidney pain, painful or frequent urination, blood in urine.\n"
            "Context-aware risk rules:\n"
            "- Age <= 14: if fever + pain + persistent crying or vomiting/diarrhea, prioritize pediatrician and at least YELLOW when symptoms are ongoing.\n"
            "- Age >= 60 with cardiac symptoms or cardio chronic diseases (hypertension/cholesterol/heart disease): avoid GREEN unless clearly mild.\n"
            "- Diabetes/immunosuppression with infection-like symptoms should increase urgency by one level when clinically plausible.\n"
            "- Never ignore chronic conditions and age when assigning urgency.\n"
            f"Patient age: {age_context if age_context is not None else 'unknown'}\n"
            f"Patient gender: {gender_context or 'unknown'}\n"
            f"Chronic conditions: {chronic_context or 'none'}\n"
            f"Server-side heuristic specialty hint: {detected_specialty or 'general'}\n"
            f"Symptoms: {text}\n"
            "Return ONLY valid JSON with keys:\n"
            '{"urgency": "RED/YELLOW/GREEN", "specialist": {"en": "...", "az": "...", "ru": "..."}, "reason": {"en": "...", "az": "...", "ru": "..."}, "detected_specialty": "..."}'
        )

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            response_format={ "type": "json_object" },
            messages=[
                {'role': 'system', 'content': 'You are a safely constrained assistant for symptom triage. Always output strictly in JSON.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.2,
            max_tokens=400
        )

        raw = response.choices[0].message.content.strip()
        import re
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        parsed = json.loads(raw)

        if isinstance(parsed, dict):
            parsed_specialty = str(parsed.get('detected_specialty', 'general')).strip().lower()
            if parsed_specialty not in ALLOWED_SPECIALTIES:
                parsed_specialty = detected_specialty or 'general'
            if parsed_specialty == 'general' and detected_specialty in ALLOWED_SPECIALTIES:
                parsed_specialty = detected_specialty

            return {
                'city': city,
                'urgency': parsed.get('urgency', 'GREEN'),
                'specialist': parsed.get('specialist', {'en': 'Primary Care Practitioner', 'az': 'Ailə Həkimi / Terapevt', 'ru': 'Участковый Терапевт'}),
                'reason': parsed.get('reason', {'en': 'Mild symptoms. Monitor locally.', 'az': 'Yüngül simptomlar. Nəzarət edin.', 'ru': 'Легкие симптомы. Наблюдайте за состоянием.'}),
                'detected_specialty': parsed_specialty,
                'map_vector_data': {
                    'center_city': city,
                    'hospitals': [],
                    'roads': []
                }
            }
    except Exception as exc:
        print(f"OpenAI symptom analysis failed: {exc}")
    return None


def setup_database_automatically():
    """Initializes local storage solely for analytical logs and tracking metrics."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS triage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symptoms_text TEXT,
                urgency_level TEXT,
                detected_city TEXT,
                latitude REAL,
                longitude REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
        print("📁 Analytical local database engine initialized.")
    except Exception as e:
        print(f"⚠️ Database setup error: {e}")

def get_city_from_coordinates(lat, lng):
    """
    Determines the closest known city based on the user's coordinates.
    Defaults to Unknown instead of forcing Baku when the location is outside the known area.
    """
    known_cities = {
        "Baku": (40.3953, 49.8822),
        "Ganja": (40.6840, 46.3606),
        "Sumqayit": (40.5898, 49.6502)
    }

    distances = []
    for city, center in known_cities.items():
        try:
            distances.append((geodesic((lat, lng), center).km, city))
        except Exception:
            continue

    distances.sort(key=lambda x: x[0])
    if distances and distances[0][0] <= 50:
        return distances[0][1]
    return "Unknown"

def get_hospitals_from_openstreetmap(lat, lng, radius_km=5, specialty=None):
    """
    Fetches real hospital and clinic data from OpenStreetMap using the Overpass API.
    Returns hospitals and clinics within the specified radius of given coordinates.
    """
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
        radius_m = int(radius_km * 1000)
        hospitals = []
        search_clauses = []

        if specialty and specialty in SPECIALTY_SEARCH_CLAUSES:
            search_clauses.extend(SPECIALTY_SEARCH_CLAUSES[specialty])

        search_clauses.extend([
            'node["amenity"="hospital"]',
            'node["amenity"="clinic"]',
            'way["amenity"="hospital"]',
            'way["amenity"="clinic"]',
            'relation["amenity"="hospital"]',
            'relation["amenity"="clinic"]',
            'node["amenity"="doctors"]',
            'way["amenity"="doctors"]',
            'relation["amenity"="doctors"]',
            'node["healthcare"="clinic"]',
            'way["healthcare"="clinic"]',
            'relation["healthcare"="clinic"]'
        ])

        overpass_query = '[out:json][timeout:30];(' + '\n'.join([f'  {clause}(around:{radius_m},{lat},{lng});' for clause in search_clauses]) + '\n);\nout center tags;'
        response = requests.get(
            overpass_url,
            params={'data': overpass_query},
            headers={'User-Agent': 'AI-SymptomTriage/1.0', 'Accept': 'application/json'},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            for element in data.get('elements', []):
                if 'center' in element:
                    h_lat = element['center']['lat']
                    h_lng = element['center']['lon']
                elif 'lat' in element:
                    h_lat = element['lat']
                    h_lng = element['lon']
                else:
                    continue
                
                tags = element.get('tags', {})
                name = tags.get('name', tags.get('operator', 'Hospital/Clinic'))
                address_parts = []
                if tags.get('addr:street'):
                    address_parts.append(tags.get('addr:street'))
                if tags.get('addr:housenumber'):
                    address_parts.append(tags.get('addr:housenumber'))
                address = ', '.join(address_parts).strip() or 'Address unavailable'

                try:
                    distance = geodesic((lat, lng), (h_lat, h_lng)).km
                except:
                    distance = 0.0

                has_emergency = tags.get('emergency') == 'yes' or tags.get('amenity') == 'hospital'                
                hospitals.append({
                    'name': name,
                    'address': address,
                    'latitude': h_lat,
                    'longitude': h_lng,
                    'distance': round(distance, 2),
                    'has_emergency': has_emergency
                })
            
            hospitals.sort(key=lambda x: x['distance'])
            hospitals = hospitals[:5]
        else:
            print(f"Overpass API error: {response.status_code}")
    except Exception as e:
        print(f"Error fetching hospitals from OSM: {e}")
        return []

    if not hospitals and specialty:
        return get_hospitals_from_openstreetmap(lat, lng, radius_km=radius_km, specialty=None)
    return hospitals

def get_nearest_health_suggestions(lat, lng, city=None):
    """Return nearest hospital/clinic suggestions based on actual user coordinates."""
    suggestions = []
    for hospital in NEARBY_HOSPITAL_DATABASE:
        try:
            distance = geodesic((lat, lng), (hospital['latitude'], hospital['longitude'])).km
        except Exception:
            distance = 0.0
        suggestions.append({
            'name': hospital['name'],
            'address': hospital['address'],
            'latitude': hospital['latitude'],
            'longitude': hospital['longitude'],
            'has_emergency': hospital['has_emergency'],
            'distance': round(distance, 2)
        })

    suggestions.sort(key=lambda x: x['distance'])
    return suggestions[:5]

def analyze_symptoms_and_generate_map_ai(text, city, specialty=None, patient_context=None):
    """Consolidated logic analyzing symptom context and building map arrays."""
    detected_specialty = specialty or detect_specialty_from_symptoms(text, patient_context=patient_context)

    ai_result = get_ai_symptom_assessment(
        text,
        city,
        detected_specialty=detected_specialty,
        patient_context=patient_context
    )
    if ai_result is not None:
        deterministic_urgency = detect_urgency_from_symptoms(
            text,
            patient_context=patient_context,
            detected_specialty=ai_result.get('detected_specialty') or detected_specialty
        )
        ai_result['urgency'] = max_urgency_level(ai_result.get('urgency'), deterministic_urgency)
        return ai_result
    
    if city == "Baku":
        ai_hospitals = [
            {"name_en": "Baku Central Clinical Hospital", "name_az": "Mərkəzi Klinik Xəstəxana", "name_ru": "Центральная Клиническая Больница", "address_en": "76 Parliament Ave", "address_az": "Parlament Prospekti 76", "address_ru": "Парламентский проспект 76", "offset_x": -60, "offset_y": -45, "er": 1},
            {"name_en": "Republican Clinical Hospital", "name_az": "Respublika Klinik Xəstəxanasi", "name_ru": "Республиканская Клиническая Больница", "address_en": "Tbilisi Ave", "address_az": "Tbilisi Prospekti", "address_ru": "Тбилисский проспект", "offset_x": -85, "offset_y": 70, "er": 1},
            {"name_en": "Baku City Hospital", "name_az": "Bakı Şəhər Xəstəxanası", "name_ru": "Городская Больница Баку", "address_en": "Yusif Vazir St", "address_az": "Yusif Vəzir Küçəsi", "address_ru": "ул. Юсифа Везира", "offset_x": 95, "offset_y": 30, "er": 0}
        ]
        roads = [{"name_en": "Tbilisi Ave", "name_az": "Tbilisi Pr.", "from_x": -120, "from_y": 70, "to_x": 120, "to_y": 70}]
    elif city == "Ganja":
        ai_hospitals = [
            {"name_en": "Ganja City Hospital No.1", "name_az": "Gəncə Şəhər Xəstəxanası №1", "name_ru": "Городская Больница Гянджи №1", "address_en": "Attar St", "address_az": "Əttarlar Küçəsi", "address_ru": "ул. Атарлар", "offset_x": -40, "offset_y": -50, "er": 1},
            {"name_en": "International Hospital Ganja", "name_az": "Beynəlxalq Xəstəxana Gəncə", "name_ru": "Международная Больница Гянджи", "address_en": "Heydar Aliyev Ave", "address_az": "Heydər Əliyev Pr.", "address_ru": "пр. Гейдара Алиева", "offset_x": 70, "offset_y": 60, "er": 1}
        ]
        roads = [{"name_en": "Heydar Aliyev Ave", "name_az": "Heydər Əliyev Pr.", "from_x": -120, "from_y": 60, "to_x": 120, "to_y": 60}]
    else:
        ai_hospitals = [
            {"name_en": "District General Hospital", "name_az": "Bölgə Mərkəzi Xəstəxanası", "name_ru": "Районная Больница", "address_en": "Main Hub St", "address_az": "Mərkəzi Küçə", "address_ru": "Главная Улица", "offset_x": -50, "offset_y": -50, "er": 1}
        ]
        roads = []

    urgency = detect_urgency_from_symptoms(text, patient_context=patient_context, detected_specialty=detected_specialty)
    if urgency == "RED":
        spec_en, spec_az, spec_ru = "Emergency Physician", "Təcili Tibbi Yardım Həkimi", "Врач Скорой Помощи"
        reas_en = "Potential life-threatening symptoms detected. Seek emergency services immediately."
        reas_az = "Həyat üçün təhlükəli simptomlar müşahidə olunur. Dərhal təcili yardım xidmətinə müraciət edin."
        reas_ru = "Обнаружены потенциально опасные для жизни симптомы. Немедленно обратитесь в экстренную службу."
    elif urgency == "YELLOW":
        spec_en, spec_az, spec_ru = "Urgent Care Specialist", "Təcili Baxım Mütəxəssisi", "Специалист Неотложной Помощи"
        reas_en = "Acute symptoms require prompt in-person clinical evaluation."
        reas_az = "Kəskin simptomlar qısa zamanda həkim müayinəsi tələb edir."
        reas_ru = "Острые симптомы требуют оперативного очного осмотра."
    else:
        spec_en, spec_az, spec_ru = "Primary Care Practitioner", "Ailə Həkimi / Terapevt", "Участковый Терапевт"
        reas_en = "Current symptom pattern appears stable and outpatient-manageable."
        reas_az = "Hazırkı simptom profili stabil görünür və ambulator izlənə bilər."
        reas_ru = "Текущая симптоматика выглядит стабильной и подходит для амбулаторного наблюдения."

    if detected_specialty == 'dentist':
        spec_en = "Dental Care Specialist"
        spec_az = "Diş Həkimi / Stomatoloq"
        spec_ru = "Стоматолог"
        reas_en = "Symptom pattern suggests dental pain or oral health care."
        reas_az = "Simptomlar diş ağrısı və ya ağız sağlamığına işarə edir."
        reas_ru = "Симптомы указывают на зубную боль или стоматологическую помощь."
    elif detected_specialty == 'dermatologist':
        spec_en = "Dermatologist"
        spec_az = "Dermatoloq"
        spec_ru = "Дерматолог"
        reas_en = "Skin-related symptoms suggest consultation with a dermatologist."
        reas_az = "Dəri ilə bağlı simptomlar dermatoloq məsləhətinə ehtiyac olduğunu göstərir."
        reas_ru = "Симптомы кожи указывают на консультацию у дерматолога."
    elif detected_specialty == 'cardiologist':
        spec_en = "Cardiologist"
        spec_az = "Kardioloq"
        spec_ru = "Кардиолог"
        reas_en = "Complaints are consistent with heart or cardiovascular care."
        reas_az = "Şikayətlər ürək və ya ürək-damar baxımına uyğundur."
        reas_ru = "Жалобы соответствуют сердечно-сосудистому уходу."
    elif detected_specialty == 'ophthalmologist':
        spec_en = "Ophthalmologist"
        spec_az = "Oftalmoloq"
        spec_ru = "Офтальмолог"
        reas_en = "Eye symptoms indicate specialist eye care is recommended."
        reas_az = "Göz simptomları ixtisaslı göz baxımını tövsiyə edir."
        reas_ru = "Симптомы глаз указывают на необходимость специализированной офтальмологической помощи."
    elif detected_specialty == 'orthopedic':
        spec_en = "Orthopedic Specialist"
        spec_az = "Ortopedik Mütəxəssis"
        spec_ru = "Ортопед"
        reas_en = "Musculoskeletal complaints suggest orthopedic evaluation."
        reas_az = "Əzələ-sümük şikayətləri ortopedik müayinə tələb edir."
        reas_ru = "Мышечно-скелетные жалобы требуют ортопедической оценки."
    elif detected_specialty == 'neurologist':
        spec_en = "Neurologist"
        spec_az = "Nevroloq"
        spec_ru = "Невролог"
        reas_en = "Symptoms suggest a neurological evaluation is needed."
        reas_az = "Simptomlar nevroloji müayinəyə ehtiyac olduğunu göstərir."
        reas_ru = "Симптомы указывают на необходимость неврологического обследования."
    elif detected_specialty == 'gastroenterologist':
        spec_en = "Gastroenterologist"
        spec_az = "Qastroenteroloq"
        spec_ru = "Гастроэнтеролог"
        reas_en = "Digestive system symptoms require gastroenterology care."
        reas_az = "Həzm sistemi şikayətləri qastroenteroloq müayinəsi tələb edir."
        reas_ru = "Симптомы пищеварительной системы требуют консультации гастроэнтеролога."
    elif detected_specialty == 'otolaryngologist':
        spec_en = "ENT Specialist (Otolaryngologist)"
        spec_az = "LOR Mütəxəssisi (Otolarinqoloq)"
        spec_ru = "ЛОР-врач (Отоларинголог)"
        reas_en = "Ear, nose, or throat symptoms detected."
        reas_az = "Qulaq, burun və ya boğazla bağlı simptomlar aşkarlandı."
        reas_ru = "Обнаружены симптомы, связанные с ухом, горлом или носом."
    elif detected_specialty == 'pediatrician':
        spec_en = "Pediatrician"
        spec_az = "Pediatr"
        spec_ru = "Педиатр"
        reas_en = "Symptoms indicate a need for pediatric care for a child or infant."
        reas_az = "Simptomlar uşaq və ya körpə üçün pediatr müayinəsini tələb edir."
        reas_ru = "Симптомы указывают на необходимость педиатрической помощи для ребенка."
    elif detected_specialty == 'gynecologist':
        spec_en = "Gynecologist"
        spec_az = "Ginekoloq"
        spec_ru = "Гинеколог"
        reas_en = "Symptoms are related to female reproductive health or pregnancy."
        reas_az = "Simptomlar qadın reproduktiv sağlamlığı və ya hamiləliklə bağlıdır."
        reas_ru = "Симптомы связаны с женским репродуктивным здоровьем или беременностью."
    elif detected_specialty == 'urologist':
        spec_en = "Urologist"
        spec_az = "Uroloq"
        spec_ru = "Уролог"
        reas_en = "Urinary tract or kidney symptoms suggest a urological consultation."
        reas_az = "Sidik yolları və ya böyrək şikayətləri uroloq məsləhətini göstərir."
        reas_ru = "Симптомы мочевыводящих путей или почек требуют консультации уролога."

    return {
        "city": city,
        "urgency": urgency,
        "detected_specialty": detected_specialty or "general",
        "specialist": {"en": spec_en, "az": spec_az, "ru": spec_ru},
        "reason": {"en": reas_en, "az": reas_az, "ru": reas_ru},
        "map_vector_data": {
            "center_city": city,
            "hospitals": ai_hospitals,
            "roads": roads
        }
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/triage', methods=['POST'])
def process_triage():
    try:
        data = request.get_json()
        symptoms = data.get('symptoms', '')
        lat = float(data.get('latitude', 40.3700))
        lng = float(data.get('longitude', 49.8372))
        age = data.get('age')
        gender = data.get('gender')
        chronic = data.get('chronic_conditions', '')
        patient_context = build_patient_context(age=age, gender=gender, chronic_conditions=chronic)

        full_case_text = (
            f"Age: {patient_context.get('age') if patient_context.get('age') is not None else 'unknown'}, "
            f"Gender: {patient_context.get('gender') or 'unknown'}, "
            f"Chronic conditions: {chronic or 'none'}. "
            f"Symptoms: {symptoms}"
        )
        
        # 1. Automatically track user location city based on incoming telemetry coordinates
        detected_city = get_city_from_coordinates(lat, lng)
        
        # 2. Always detect likely specialist; allow request flag to force specialty-focused map query.
        detected_specialty = detect_specialty_from_symptoms(symptoms, patient_context=patient_context)
        use_specialty = bool(data.get('use_specialty', False))
        specialty_for_search = detected_specialty if (use_specialty or detected_specialty) else None

        ai_payload = analyze_symptoms_and_generate_map_ai(
            symptoms,
            detected_city,
            specialty=detected_specialty,
            patient_context=patient_context
        )
        hospitals = get_hospitals_from_openstreetmap(lat, lng, radius_km=10, specialty=specialty_for_search)
        if not hospitals:
            hospitals = get_nearest_health_suggestions(lat, lng, detected_city)

        ai_payload['specialty_search'] = detected_specialty or 'general'
        # YELLOW və ya RED statusda təcili yardım xidməti olan yerləri önə çək
        if ai_payload.get('urgency') in ('RED', 'YELLOW'):
            hospitals.sort(key=lambda h: (0 if h.get('has_emergency') else 1, h.get('distance', 0)))

        ai_payload['hospitals'] = hospitals
        
        # 4. Log results inside relational database ledger tables
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO triage_logs (symptoms_text, urgency_level, detected_city, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
                       (full_case_text, ai_payload['urgency'], detected_city, lat, lng))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "data": ai_payload})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    """Endpoint to fetch hospitals/clinics near given coordinates using OpenStreetMap."""
    try:
        lat = float(request.args.get('lat', 40.3700))
        lng = float(request.args.get('lng', 49.8372))
        radius = float(request.args.get('radius', 10))
        specialty = request.args.get('specialty')
        hospitals = get_hospitals_from_openstreetmap(lat, lng, radius_km=radius, specialty=specialty)
        if not hospitals:
            hospitals = get_nearest_health_suggestions(lat, lng, request.args.get('city', ''))
        return jsonify({"status": "success", "hospitals": hospitals})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    setup_database_automatically()
    app.run(debug=True, port=5005)
