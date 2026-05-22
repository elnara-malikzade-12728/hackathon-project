import math
import os
import json
import re
import sys
import time
import sqlite3
import requests
from rag_pipeline import build_index, retrieve_rules, format_evidence, get_max_urgency_from_evidence, RAG_AVAILABLE
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
PHARMACY_CACHE_TTL_SECONDS = 1800
PHARMACY_CACHE_RADIUS_KM = 0.6
PHARMACY_CACHE = {
    "coords": None,
    "results": [],
    "timestamp": 0.0
}
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
    'pulmonologist': {
        'high': [
            'nəfəs almada çətinlik', 'nəfəs almaqda çətinlik', 'təngnəfəslik', 'boğulma',
            'astma tutması', 'hırıltı', 'xırıltı', 'nefes darligi',
            'difficulty breathing', 'shortness of breath', 'breathing difficulty', 'wheezing',
            'asthma attack', 'respiratory distress', 'dyspnea',
            'одышка', 'затрудненное дыхание', 'приступ астмы', 'свистящее дыхание'
        ],
        'medium': [
            'öskürək', 'cough', 'bronchitis', 'bronxit', 'chest congestion', 'sinədə sıxılma',
            'ağciyər', 'lung', 'пульмонолог', 'легкие'
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
    },
    'endocrinologist': {
        'high': [
            'diabet', 'diabetes', 'şəkər', 'qan şəkəri', 'hipoqlikemiya', 'hiperglikemiya',
            'hypoglycemia', 'hyperglycemia', 'blood sugar', 'insulin',
            'эндокринолог', 'диабет', 'глюкоза', 'сахар в крови'
        ],
        'medium': [
            'soyuq tər', 'tər basma', 'əllərdə titrəmə', 'üşütmə', 'başgicəllənmə',
            'cold sweat', 'shaking hands', 'tremor', 'chills', 'dizziness', 'weakness',
            'холодный пот', 'дрожь', 'озноб'
        ]
    }
}

SPECIALTY_KEYWORD_MAP = {
    specialty: signals['high'] + signals['medium']
    for specialty, signals in SPECIALTY_SIGNAL_MAP.items()
}

SPECIALTY_PRIORITY = [
    'cardiologist', 'pediatrician', 'pulmonologist', 'endocrinologist', 'gynecologist', 'neurologist', 
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
    'şüur itkisi', 'nəfəs ala bilmir', 'nəfəs ala bilmirəm', 'dayanmayan qanaxma', 'kəskin',
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

RESPIRATORY_RED_PHRASES = [
    'nəfəs almada çətinlik', 'nəfəs almaqda çətinlik', 'nəfəs ala bilmir',
    'təngnəfəslik', 'boğulma', 'boğulur', 'hava çatmır',
    'difficulty breathing', 'shortness of breath', 'cannot breathe', "can't breathe",
    'respiratory distress', 'dyspnea', 'struggling to breathe',
    'одышка', 'затрудненное дыхание', 'не может дышать'
]

RESPIRATORY_URGENT_PHRASES = [
    'hırıltı', 'xırıltı', 'wheezing', 'asthma', 'astma',
    'rapid breathing', 'fast breathing', 'tachypnea',
    'chest retraction', 'intercostal retraction'
]

SWEATING_ALERT_PHRASES = [
    'tər basma', 'soyuq tər', 'tərləmə', 'sweating', 'cold sweat',
    'потливость', 'холодный пот'
]

DIABETIC_URGENT_PHRASES = [
    'soyuq tər', 'tər basma', 'əllərdə titrəmə', 'titrəmə', 'üşütmə',
    'başgicəllənmə', 'halsızlıq', 'bayılma', 'ürəkbulanma', 'qusma',
    'cold sweat', 'shaking', 'tremor', 'chills', 'dizziness', 'weakness',
    'nausea', 'vomiting', 'palpitations', 'blurred vision', 'rapid heartbeat',
    'холодный пот', 'дрожь', 'озноб', 'слабость', 'тошнота'
]

DIABETIC_CRITICAL_PHRASES = [
    'şüur itkisi', 'qıcolma', 'dayanmadan qusma', 'nəfəsdə aseton qoxusu',
    'unconscious', 'cannot wake', 'seizure', 'persistent vomiting',
    'fruity breath', 'confusion severe', 'disoriented severe',
    'потеря сознания', 'судороги', 'неукротимая рвота'
]

FACILITY_EXCLUDE_TERMS = [
    'onkolog', 'oncolog', 'патол', 'patholog', 'morgue', 'forensic',
    'ekspertiza', 'autopsy', 'cadaver', 'experimental', 'bio lab',
    'laborator', 'laboratory', 'anatom', 'anotomy'
]

SPECIALTY_FACILITY_HINTS = {
    'pediatrician': ['uşaq', 'pediatr', 'pediatric', 'paediatric', 'children', 'ребен', 'дет'],
    'pulmonologist': ['pulmon', 'respir', 'lung', 'ağciyər', 'asthma', 'астм', 'пульмон'],
    'otolaryngologist': ['lor', 'otolaryng', 'ear', 'nose', 'throat', 'qulaq', 'burun', 'boğaz', 'ухо', 'горло'],
    'cardiologist': ['cardio', 'kardio', 'heart', 'ürək', 'серд'],
    'neurologist': ['nevro', 'neuro', 'невр'],
    'gastroenterologist': ['gastro', 'qastro', 'digest', 'həzm', 'желуд'],
    'urologist': ['urolo', 'urolog', 'sidik', 'kidney', 'почек'],
    'endocrinologist': ['endocrin', 'diabet', 'metabolic', 'şəkər', 'глюкоз', 'эндокрин'],
    'gynecologist': ['ginek', 'gynec', 'women', 'qadın', 'берем'],
    'ophthalmologist': ['oftalm', 'ophthalm', 'eye', 'göz', 'глаз'],
    'orthopedic': ['ortop', 'trauma', 'bone', 'sümük', 'сустав'],
    'dentist': ['diş', 'stomat', 'dental', 'tooth', 'зуб'],
    'dermatologist': ['dəri', 'derma', 'skin', 'кож']
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
    'pulmonologist': [
        'node["healthcare"="pulmonologist"]',
        'way["healthcare"="pulmonologist"]',
        'relation["healthcare"="pulmonologist"]',
        'node["healthcare:specialty"="pulmonology"]',
        'way["healthcare:specialty"="pulmonology"]',
        'node["healthcare:speciality"="pulmonology"]',
        'way["healthcare:speciality"="pulmonology"]',
        'node["healthcare:specialty"="emergency"]',
        'way["healthcare:specialty"="emergency"]'
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
    ],
    'endocrinologist': [
        'node["healthcare"="endocrinologist"]',
        'way["healthcare"="endocrinologist"]',
        'relation["healthcare"="endocrinologist"]',
        'node["healthcare:specialty"="endocrinology"]',
        'way["healthcare:specialty"="endocrinology"]',
        'relation["healthcare:specialty"="endocrinology"]',
        'node["healthcare:speciality"="endocrinology"]',
        'way["healthcare:speciality"="endocrinology"]',
        'relation["healthcare:speciality"="endocrinology"]'
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


def contains_any(text, terms):
    return any(term in text for term in terms)


def detect_life_threatening_flags(text, patient_context=None):
    """Return list of triggered red-flag groups."""
    text_lower = normalize_symptom_text(text)
    flags = []
    risk_flags = (patient_context or {}).get('risk_flags', {})

    if contains_any(text_lower, RED_URGENCY_PHRASES):
        flags.append('general_red')

    respiratory_red = contains_any(text_lower, RESPIRATORY_RED_PHRASES)
    respiratory_urgent = contains_any(text_lower, RESPIRATORY_URGENT_PHRASES)
    sweating = contains_any(text_lower, SWEATING_ALERT_PHRASES)
    diabetic_critical = contains_any(text_lower, DIABETIC_CRITICAL_PHRASES)
    diabetic_urgent = contains_any(text_lower, DIABETIC_URGENT_PHRASES)

    if respiratory_red:
        flags.append('respiratory_distress')
    if diabetic_critical:
        flags.append('diabetic_critical_event')

    if patient_context:
        if risk_flags.get('diabetes') and diabetic_urgent:
            flags.append('diabetic_instability')

        if patient_context.get('is_child') and (respiratory_red or respiratory_urgent):
            if sweating or risk_flags.get('respiratory') or contains_any(text_lower, ['astma', 'asthma', 'wheezing', 'hırıltı']):
                flags.append('pediatric_respiratory_crisis')

        if (patient_context.get('is_elderly') or risk_flags.get('cardio')) and contains_any(text_lower, CARDIAC_ALERT_PHRASES):
            if sweating:
                flags.append('possible_acute_cardiac_event')

    return list(dict.fromkeys(flags))


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


def normalize_gender(value):
    raw = (value or '').strip().lower()
    if raw in ('female', 'qadın', 'qadin', 'женский', 'woman'):
        return 'female'
    if raw in ('male', 'kişi', 'kisi', 'мужской', 'man'):
        return 'male'
    return 'unknown'


def build_patient_context(age=None, gender=None, chronic_conditions=''):
    """Create patient-level risk context used in triage scoring and specialty routing."""
    age_value = parse_age(age)
    gender_text = normalize_gender(gender)
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
        respiratory_red = contains_any(text_lower, RESPIRATORY_RED_PHRASES)
        respiratory_urgent = contains_any(text_lower, RESPIRATORY_URGENT_PHRASES)
        diabetic_urgent = contains_any(text_lower, DIABETIC_URGENT_PHRASES)
        diabetic_critical = contains_any(text_lower, DIABETIC_CRITICAL_PHRASES)
        diabetes_risk = patient_context.get('risk_flags', {}).get('diabetes')

        # Young children should be routed to pediatrics for mixed acute complaints.
        if patient_context.get('is_child') and any(term in text_lower for term in PEDIATRIC_ALERT_PHRASES):
            scores['pediatrician'] = scores.get('pediatrician', 0) + 4

        if respiratory_red or respiratory_urgent:
            if patient_context.get('is_child'):
                scores['pediatrician'] = scores.get('pediatrician', 0) + 10
            scores['pulmonologist'] = scores.get('pulmonologist', 0) + 4

        if patient_context.get('risk_flags', {}).get('respiratory'):
            scores['pulmonologist'] = scores.get('pulmonologist', 0) + 2

        # Diabetes context should avoid neurological over-routing for metabolic instability.
        if diabetes_risk and (diabetic_urgent or diabetic_critical):
            scores['endocrinologist'] = scores.get('endocrinologist', 0) + 7
            scores['neurologist'] = max(0, scores.get('neurologist', 0) - 1)

        if diabetic_critical:
            scores['endocrinologist'] = scores.get('endocrinologist', 0) + 4

        # Elderly + chest/cardiac symptoms should strongly favor cardiology.
        if patient_context.get('is_elderly') and any(term in text_lower for term in CARDIAC_ALERT_PHRASES):
            scores['cardiologist'] = scores.get('cardiologist', 0) + 3

        # Pregnancy context should prioritize gynecology for abdominal/pelvic symptom wording.
        if (
            patient_context.get('risk_flags', {}).get('pregnancy') and
            any(term in text_lower for term in ['abdominal pain', 'qarın ağrısı', 'pelvic', 'qasıq', 'bleeding', 'qanaxma'])
        ):
            scores['gynecologist'] = scores.get('gynecologist', 0) + 4

        gender = patient_context.get('gender', '')
        if gender in ('female', 'qadın', 'женский', 'woman'):
            if any(term in text_lower for term in ['menstruation', 'period', 'aybaşı', 'menstrual', 'pelvic', 'qasıq', 'vaginal', 'hamilə']):
                scores['gynecologist'] = scores.get('gynecologist', 0) + 4

        # Known kidney disease + urinary phrases should favor urology.
        if (
            patient_context.get('risk_flags', {}).get('renal') and
            any(term in text_lower for term in ['sidik', 'urine', 'urination', 'böyrək', 'kidney', 'burning'])
        ):
            scores['urologist'] = scores.get('urologist', 0) + 3

        if any(term in text_lower for term in ['sidik', 'urine', 'urination', 'burning urination', 'tez-tez sidiyə getmə']):
            scores['urologist'] = scores.get('urologist', 0) + 2

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

    life_threatening_flags = detect_life_threatening_flags(text, patient_context=patient_context)
    hard_red_flags = {
        'general_red',
        'respiratory_distress',
        'pediatric_respiratory_crisis',
        'possible_acute_cardiac_event',
        'diabetic_critical_event'
    }
    if any(flag in hard_red_flags for flag in life_threatening_flags):
        return "RED"

    urgency_score = 0
    if contains_any(text_lower, YELLOW_URGENCY_PHRASES):
        urgency_score += 2

    if contains_any(text_lower, RESPIRATORY_URGENT_PHRASES):
        urgency_score += 2

    if 'diabetic_instability' in life_threatening_flags:
        urgency_score += 3

    if contains_any(text_lower, MILD_QUALIFIERS):
        urgency_score -= 1

    if patient_context:
        risk_flags = patient_context.get('risk_flags', {})

        if patient_context.get('is_infant') and any(term in text_lower for term in PEDIATRIC_ALERT_PHRASES):
            urgency_score += 2
        elif patient_context.get('is_child') and any(term in text_lower for term in PEDIATRIC_ALERT_PHRASES):
            urgency_score += 1

        if patient_context.get('is_elderly') and contains_any(text_lower, CARDIAC_ALERT_PHRASES):
            urgency_score += 2

        if (risk_flags.get('cardio') or risk_flags.get('diabetes')) and contains_any(text_lower, CARDIAC_ALERT_PHRASES):
            urgency_score += 2

        if (risk_flags.get('immunosuppressed') or risk_flags.get('diabetes')) and contains_any(text_lower, INFECTION_ALERT_PHRASES):
            urgency_score += 1

        if risk_flags.get('pregnancy') and contains_any(text_lower, ['qanaxma', 'bleeding', 'qarın ağrısı', 'abdominal pain']):
            urgency_score += 2

        if risk_flags.get('respiratory') and contains_any(text_lower, RESPIRATORY_URGENT_PHRASES):
            urgency_score += 1

    if detected_specialty in ('cardiologist', 'pulmonologist', 'urologist', 'otolaryngologist') and urgency_score > 0:
        urgency_score += 1

    return "YELLOW" if urgency_score >= 2 else "GREEN"


def max_urgency_level(primary, secondary):
    """Return higher urgency from two labels."""
    p = str(primary or 'GREEN').upper()
    s = str(secondary or 'GREEN').upper()
    return p if URGENCY_RANK.get(p, 0) >= URGENCY_RANK.get(s, 0) else s


def get_specialist_labels_for_specialty(specialty):
    labels = {
        'pediatrician': {'en': 'Pediatrician', 'az': 'Pediatr', 'ru': 'Педиатр'},
        'pulmonologist': {'en': 'Pulmonologist', 'az': 'Pulmonoloq', 'ru': 'Пульмонолог'},
        'cardiologist': {'en': 'Cardiologist', 'az': 'Kardioloq', 'ru': 'Кардиолог'},
        'endocrinologist': {'en': 'Endocrinologist', 'az': 'Endokrinoloq', 'ru': 'Эндокринолог'},
        'urologist': {'en': 'Urologist', 'az': 'Uroloq', 'ru': 'Уролог'},
        'gynecologist': {'en': 'Gynecologist', 'az': 'Ginekoloq', 'ru': 'Гинеколог'},
        'neurologist': {'en': 'Neurologist', 'az': 'Nevroloq', 'ru': 'Невролог'},
        'gastroenterologist': {'en': 'Gastroenterologist', 'az': 'Qastroenteroloq', 'ru': 'Гастроэнтеролог'},
        'otolaryngologist': {'en': 'ENT Specialist (Otolaryngologist)', 'az': 'LOR Mütəxəssisi (Otolarinqoloq)', 'ru': 'ЛОР-врач (Отоларинголог)'},
        'ophthalmologist': {'en': 'Ophthalmologist', 'az': 'Oftalmoloq', 'ru': 'Офтальмолог'},
        'orthopedic': {'en': 'Orthopedic Specialist', 'az': 'Ortopedik Mütəxəssis', 'ru': 'Ортопед'},
        'dentist': {'en': 'Dental Care Specialist', 'az': 'Diş Həkimi / Stomatoloq', 'ru': 'Стоматолог'},
        'dermatologist': {'en': 'Dermatologist', 'az': 'Dermatoloq', 'ru': 'Дерматолог'},
        'general': {'en': 'Primary Care Practitioner', 'az': 'Ailə Həkimi / Terapevt', 'ru': 'Участковый Терапевт'}
    }
    return labels.get(specialty)


def choose_safe_specialty(ai_specialty, heuristic_specialty, text, patient_context=None):
    ai_spec = (ai_specialty or '').strip().lower()
    heuristic_spec = (heuristic_specialty or '').strip().lower()
    text_lower = normalize_symptom_text(text)
    risk_flags = (patient_context or {}).get('risk_flags', {})

    has_respiratory_distress = contains_any(text_lower, RESPIRATORY_RED_PHRASES) or contains_any(text_lower, RESPIRATORY_URGENT_PHRASES)
    has_diabetic_instability = contains_any(text_lower, DIABETIC_URGENT_PHRASES) or contains_any(text_lower, DIABETIC_CRITICAL_PHRASES)

    if (patient_context or {}).get('is_child') and has_respiratory_distress:
        return 'pediatrician'

    if risk_flags.get('diabetes') and has_diabetic_instability:
        return 'endocrinologist'

    if ai_spec in ALLOWED_SPECIALTIES and ai_spec != 'general':
        return ai_spec

    if heuristic_spec in ALLOWED_SPECIALTIES:
        return heuristic_spec
    return 'general'


def get_ai_symptom_assessment(text, city, detected_specialty=None, patient_context=None):
    """Use an OpenAI model to interpret symptoms and return structured triage output."""
    if not USE_AI_SYMPTOMS or not OPENAI_API_KEY or not client:
        return None

    try:
        client.api_key = OPENAI_API_KEY
        age_context = patient_context.get('age') if patient_context else None
        gender_context = patient_context.get('gender') if patient_context else ''
        chronic_context = patient_context.get('chronic_text') if patient_context else ''

        # RAG: simptoma uyğun tibbi qaydaları al
        rag_rules    = retrieve_rules(text, top_k=5) if RAG_AVAILABLE else []
        rag_evidence = format_evidence(rag_rules)
        rag_urgency_floor = get_max_urgency_from_evidence(rag_rules)
        prompt = f"""
            You are a strict medical TRIAGE AI. Your goal: SAFE triage, avoiding under-triage.

            ==== CRITICAL CONTEXT ====
            Patient Age: {age} years old
            Patient Gender: {gender}
            Chronic Conditions: {chronic or 'none'}

            ==== MULTI-FACTOR ASSESSMENT FRAMEWORK ====

            For RED urgency, evaluate these dimensions:
            1. RESPIRATORY: Any breathing difficulty? Wheezing, stridor, gasping, "cannot breathe"?
            2. NEUROLOGICAL: Altered consciousness? Seizure? Stroke signs? Severe confusion?
            3. CARDIOVASCULAR: Chest pressure + SOB? Severe palpitations? Syncope risk?
            4. TRAUMA/BLEEDING: Uncontrolled bleeding? Severe deformity? Open fracture?
            5. METABOLIC (if diabetic): Loss of consciousness? Seizure? Fruity breath? Persistent vomiting?
            6. PEDIATRIC (if child): Breathing trouble + asthma/wheezing? Fever + lethargy + rash?
            7. CHEMICAL/BURN: Chemical exposure? Eye splash? Severe burn?

            If ANY dimension is HIGH RISK → RED. Do not skip dimensions.

            For YELLOW urgency, evaluate:
            1. ACUTE INFLAMMATION: High fever? Severe pain? Swollen joint/limb?
            2. CARDIAC WARNING: Palpitations on exertion? Chest tightness without collapse risk?
            3. METABOLIC (if diabetic): Tremor + cold sweat? Dizziness + weakness? 
            4. ELDERLY (60+): ANY cardiac complaint should be YELLOW unless clearly transient and mild.
            5. PROGRESSIVE WORSENING: Is condition getting worse over hours?

            If condition is acute and uncomfortable → YELLOW. Do not assign GREEN hastily.

            For GREEN urgency:
            - Mild, stable, NO progression, NO red/yellow flags.
            - Examples: mild cold, localized rash without fever, minor ache.

            ==== SPECIALTY SELECTION (after urgency) ====
            Choose ONE dominant system:
            - Respiratory dominance? → Pulmonologist (or Pediatrician if child)
            - Cardiac dominance? → Cardiologist
            - Neurological dominance? → Neurologist
            - Metabolic/Endocrine dominance? (diabetes, glucose instability) → Endocrinologist
            - Psychiatric/neuro-behavioral? → General
            - Organ-specific (skin, GI, etc)? → Appropriate specialist
            - Reproductive/urinary? → Gynecologist/Urologist (sex-specific)

            Do NOT output "general" if one system clearly dominates.

            ==== RAG EVIDENCE (Authoritative) ====
            {rag_evidence}

            If retrieved evidence contradicts your assessment, the evidence has priority.

            ==== PATIENT SYMPTOMS ====
            {symptoms}

            ==== YOUR DECISION PROCESS ====
            1. Read symptoms carefully.
            2. Check EVERY RED dimension above. If any HIGH → RED.
            3. If no RED, check YELLOW dimensions. If any present → YELLOW.
            4. If neither → GREEN.
            5. Select specialty by dominant organ system.
            6. Verify specialty aligns with urgency (RED cardiac → Cardiologist, etc).
            7. Output brief, clinically coherent reason.

            Return ONLY valid JSON:
            {{
                "urgency": "RED or YELLOW or GREEN",
                "specialist": {{"en": "...", "az": "...", "ru": "..."}},
                "reason": {{"en": "Brief clinical trigger", "az": "...", "ru": "..."}},
                "detected_specialty": "exact_specialty_key",
                "confidence": 0.85,
                "dimensions_checked": ["respiratory", "cardiac", ...]
            }}
            """
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
            parsed_urgency = str(parsed.get('urgency', 'GREEN')).strip().upper()
            if parsed_urgency not in URGENCY_RANK:
                parsed_urgency = 'GREEN'

            parsed_specialty = str(parsed.get('detected_specialty', 'general')).strip().lower()
            if parsed_specialty not in ALLOWED_SPECIALTIES:
                parsed_specialty = detected_specialty or 'general'
            if parsed_specialty == 'general' and detected_specialty in ALLOWED_SPECIALTIES:
                parsed_specialty = detected_specialty
            
            # RAG urgency floor: AI aşağı qiymətləndirirsə düzəlt
            if rag_urgency_floor:
                rank = {'RED': 3, 'YELLOW': 2, 'GREEN': 1}
                if rank.get(rag_urgency_floor, 0) > rank.get(parsed_urgency, 0):
                    parsed_urgency = rag_urgency_floor
            
            return {
                'city': city,
                'urgency': parsed_urgency,
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
            if tags.get('addr:city'):
                address_parts.append(tags.get('addr:city'))
            address = ', '.join(filter(None, address_parts)).strip()

            # OSM-də ünvan yoxdursa Nominatim reverse geocoding ilə al
            if not address:
                try:
                    nom_resp = requests.get(
                        'https://nominatim.openstreetmap.org/reverse',
                        params={
                            'lat': h_lat,
                            'lon': h_lng,
                            'format': 'json',
                            'zoom': 18,
                            'addressdetails': 1
                        },
                        headers={'User-Agent': 'AI-SymptomTriage/1.0'},
                        timeout=5
                    )
                    if nom_resp.status_code == 200:
                        nom_data = nom_resp.json()
                        nom_addr = nom_data.get('address', {})
                        parts = [
                            nom_addr.get('road') or nom_addr.get('pedestrian') or nom_addr.get('path'),
                            nom_addr.get('house_number'),
                            nom_addr.get('suburb') or nom_addr.get('neighbourhood'),
                            nom_addr.get('city') or nom_addr.get('town')
                        ]
                        address = ', '.join(filter(None, parts)).strip()
                except Exception:
                    pass

            if not address:
                address = f"{round(h_lat, 4)}, {round(h_lng, 4)}"

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
                    'has_emergency': has_emergency,
                    'tags': tags
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


def _facility_text_blob(hospital):
    tags = hospital.get('tags', {}) or {}
    tag_text = " ".join([f"{k} {v}" for k, v in tags.items()])
    return normalize_symptom_text(f"{hospital.get('name', '')} {hospital.get('address', '')} {tag_text}")


def _is_irrelevant_facility(hospital):
    blob = _facility_text_blob(hospital)
    return contains_any(blob, FACILITY_EXCLUDE_TERMS)


def _facility_relevance_score(hospital, specialty=None):
    blob = _facility_text_blob(hospital)
    tags = hospital.get('tags', {}) or {}
    amenity = str(tags.get('amenity', '')).lower()

    score = 0
    if hospital.get('has_emergency'):
        score += 4
    if amenity == 'hospital':
        score += 3
    elif amenity == 'clinic':
        score += 1

    if specialty and specialty in SPECIALTY_FACILITY_HINTS:
        hint_matches = sum(1 for hint in SPECIALTY_FACILITY_HINTS[specialty] if hint in blob)
        score += min(6, hint_matches * 2)

    return score


def filter_hospitals_by_specialty(hospitals, specialty=None, urgency='GREEN'):
    """Remove clearly irrelevant facilities and rank by specialty relevance."""
    if not hospitals:
        return []

    filtered = [h for h in hospitals if not _is_irrelevant_facility(h)]
    if not filtered:
        return []

    for hospital in filtered:
        hospital['relevance_score'] = _facility_relevance_score(hospital, specialty=specialty)

    if urgency in ('RED', 'YELLOW'):
        filtered.sort(
            key=lambda h: (
                0 if h.get('has_emergency') else 1,
                -h.get('relevance_score', 0),
                h.get('distance', 9999)
            )
        )
    else:
        filtered.sort(
            key=lambda h: (
                -h.get('relevance_score', 0),
                h.get('distance', 9999)
            )
        )

    for hospital in filtered:
        hospital.pop('relevance_score', None)
    return filtered


def sanitize_hospital_output(hospitals):
    cleaned = []
    for hospital in hospitals:
        entry = dict(hospital)
        entry.pop('tags', None)
        entry.pop('relevance_score', None)
        cleaned.append(entry)
    return cleaned


def get_cached_pharmacies(lat, lng):
    if not PHARMACY_CACHE["results"] or not PHARMACY_CACHE["coords"]:
        return []
    if time.time() - PHARMACY_CACHE["timestamp"] > PHARMACY_CACHE_TTL_SECONDS:
        return []
    try:
        distance = geodesic((lat, lng), PHARMACY_CACHE["coords"]).km
    except Exception:
        return []
    if distance > PHARMACY_CACHE_RADIUS_KM:
        return []
    return list(PHARMACY_CACHE["results"])


def update_pharmacy_cache(lat, lng, pharmacies):
    PHARMACY_CACHE["coords"] = (lat, lng)
    PHARMACY_CACHE["results"] = list(pharmacies)
    PHARMACY_CACHE["timestamp"] = time.time()


def get_nearby_pharmacies(lat, lng, radius_km=3, limit=5):
    """Fetch nearby pharmacies around the provided coordinates."""
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
        radius_m = int(radius_km * 1000)
        query = (
            '[out:json][timeout:25];('
            f'node["amenity"="pharmacy"](around:{radius_m},{lat},{lng});'
            f'way["amenity"="pharmacy"](around:{radius_m},{lat},{lng});'
            f'relation["amenity"="pharmacy"](around:{radius_m},{lat},{lng});'
            ');out center tags;'
        )

        response = requests.get(
            overpass_url,
            params={'data': query},
            headers={'User-Agent': 'AI-SymptomTriage/1.0', 'Accept': 'application/json'},
            timeout=25
        )
        if response.status_code != 200:
            return get_cached_pharmacies(lat, lng)

        data = response.json()
        pharmacies = []
        for element in data.get('elements', []):
            if 'center' in element:
                p_lat = element['center']['lat']
                p_lng = element['center']['lon']
            elif 'lat' in element:
                p_lat = element['lat']
                p_lng = element['lon']
            else:
                continue

            tags = element.get('tags', {})
            name = tags.get('name', 'Pharmacy')
            address_parts = []
            if tags.get('addr:full'):
                address_parts.append(tags.get('addr:full'))
            else:
                street = tags.get('addr:street') or tags.get('addr:place')
                if street:
                    address_parts.append(street)
                if tags.get('addr:housenumber'):
                    address_parts.append(tags.get('addr:housenumber'))
                for key in ('addr:suburb', 'addr:district', 'addr:city', 'addr:province', 'addr:state'):
                    if tags.get(key):
                        address_parts.append(tags.get(key))
            address = ', '.join(address_parts).strip()
            if not address:
                address = reverse_geocode_address(p_lat, p_lng) or f"{p_lat:.5f}, {p_lng:.5f}"

            try:
                distance = geodesic((lat, lng), (p_lat, p_lng)).km
            except Exception:
                distance = 0.0

            pharmacies.append({
                'name': name,
                'address': address,
                'latitude': p_lat,
                'longitude': p_lng,
                'distance': round(distance, 2)
            })

        pharmacies.sort(key=lambda x: x['distance'])
        if pharmacies:
            pharmacies = pharmacies[:limit]
            update_pharmacy_cache(lat, lng, pharmacies)
            return pharmacies
        return get_cached_pharmacies(lat, lng)
    except Exception:
        return get_cached_pharmacies(lat, lng)


def reverse_geocode_address(lat, lng):
    """Resolve a human-readable address for coordinates using OpenStreetMap Nominatim."""
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={'format': 'jsonv2', 'lat': lat, 'lon': lng},
            headers={'User-Agent': 'AI-SymptomTriage/1.0', 'Accept': 'application/json'},
            timeout=10
        )
        if response.status_code != 200:
            return None
        data = response.json()
        return data.get('display_name')
    except Exception:
        return None

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
        safe_specialty = choose_safe_specialty(
            ai_result.get('detected_specialty'),
            detected_specialty,
            text,
            patient_context=patient_context
        )
        ai_result['detected_specialty'] = safe_specialty
        safe_labels = get_specialist_labels_for_specialty(safe_specialty)
        if safe_labels:
            ai_result['specialist'] = safe_labels

        deterministic_urgency = detect_urgency_from_symptoms(
            text,
            patient_context=patient_context,
            detected_specialty=safe_specialty or detected_specialty
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
    elif detected_specialty == 'pulmonologist':
        spec_en = "Pulmonologist"
        spec_az = "Pulmonoloq"
        spec_ru = "Пульмонолог"
        reas_en = "Breathing-related complaints suggest urgent respiratory evaluation."
        reas_az = "Nəfəsalma ilə bağlı şikayətlər tənəffüs sistemi üzrə təcili qiymətləndirmə tələb edir."
        reas_ru = "Жалобы на дыхание требуют срочной оценки дыхательной системы."
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
    elif detected_specialty == 'endocrinologist':
        spec_en = "Endocrinologist"
        spec_az = "Endokrinoloq"
        spec_ru = "Эндокринолог"
        reas_en = "Symptoms and history suggest endocrine or blood-glucose instability."
        reas_az = "Simptomlar və anamnez endokrin və ya qan şəkəri qeyri-sabitliyinə işarə edir."
        reas_ru = "Симптомы и анамнез указывают на эндокринную или гликемическую нестабильность."

    if urgency == "RED":
        reas_en = "Critical red-flag symptoms detected. Seek emergency care immediately (call emergency services now)."
        reas_az = "Kritik qırmızı bayraq simptomları aşkarlandı. Dərhal təcili tibbi yardıma müraciət edin (indi 103-ə zəng edin)."
        reas_ru = "Выявлены критические тревожные симптомы. Немедленно обратитесь за экстренной медицинской помощью (сейчас звоните 103)."

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
        critical_flags = detect_life_threatening_flags(symptoms, patient_context=patient_context)
        hospitals = get_hospitals_from_openstreetmap(lat, lng, radius_km=10, specialty=specialty_for_search)
        if not hospitals:
            hospitals = get_nearest_health_suggestions(lat, lng, detected_city)

        ai_payload['specialty_search'] = detected_specialty or 'general'
        ai_payload['critical_flags'] = critical_flags
        urgency = ai_payload.get('urgency', 'GREEN')
        hospitals = filter_hospitals_by_specialty(hospitals, detected_specialty, urgency=urgency)
        if not hospitals:
            hospitals = get_nearest_health_suggestions(lat, lng, detected_city)
            hospitals = filter_hospitals_by_specialty(hospitals, detected_specialty, urgency=urgency) or hospitals
        hospitals = hospitals[:8]

        # Always push emergency-capable centers to the top for urgent/critical cases.
        if urgency in ('RED', 'YELLOW'):
            hospitals.sort(key=lambda h: (0 if h.get('has_emergency') else 1, h.get('distance', 0)))
            if not any(h.get('has_emergency') for h in hospitals):
                emergency_fallback = [h for h in get_nearest_health_suggestions(lat, lng, detected_city) if h.get('has_emergency')]
                hospitals = (hospitals + emergency_fallback)[:8]

        ai_payload['hospitals'] = sanitize_hospital_output(hospitals[:5])
        ai_payload['pharmacies'] = get_nearby_pharmacies(lat, lng, radius_km=3, limit=4)
        
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
        urgency = str(request.args.get('urgency', 'GREEN')).upper()
        hospitals = get_hospitals_from_openstreetmap(lat, lng, radius_km=radius, specialty=specialty)
        if not hospitals:
            hospitals = get_nearest_health_suggestions(lat, lng, request.args.get('city', ''))
        hospitals = filter_hospitals_by_specialty(hospitals, specialty=specialty, urgency=urgency)
        if not hospitals:
            hospitals = get_nearest_health_suggestions(lat, lng, request.args.get('city', ''))
        if urgency in ('RED', 'YELLOW'):
            hospitals.sort(key=lambda h: (0 if h.get('has_emergency') else 1, h.get('distance', 0)))
        return jsonify({"status": "success", "hospitals": sanitize_hospital_output(hospitals[:5])})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    setup_database_automatically()
    if RAG_AVAILABLE:
        build_index() 
    app.run(debug=True, port=5005)