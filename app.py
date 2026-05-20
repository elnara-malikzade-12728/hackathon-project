import math
import os
import json
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from geopy.distance import geodesic
from openai import OpenAI


client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


app = Flask(__name__)
DB_FILE = 'ai_auto_map_audit.db'
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
USE_AI_SYMPTOMS = os.environ.get('USE_AI_SYMPTOMS', 'false').lower() in ('1', 'true', 'yes')

SPECIALTY_KEYWORD_MAP = {
    'dentist': ['tooth', 'teeth', 'dental', 'toothache', 'gum', 'cavity', 'dentist', 'wisdom tooth', 'root canal'],
    'dermatologist': ['skin', 'rash', 'eczema', 'psoriasis', 'acne', 'itch', 'blister', 'dermatology', 'sunburn', 'pimple'],
    'cardiologist': ['chest', 'heart', 'palpitations', 'angina', 'heartburn', 'cardiac', 'palpitation', 'arrhythmia', 'stroke'],
    'ophthalmologist': ['eye', 'vision', 'blurred', 'red eye', 'stye', 'eye pain', 'glasses', 'contacts', 'blindness'],
    'orthopedic': ['bone', 'fracture', 'sprain', 'joint', 'knee', 'hip', 'back pain', 'fractured', 'arm', 'leg']
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
    ]
}

# Local fallback dataset for known hospitals / clinics by geographic coordinates.
# This is used when OpenStreetMap does not return results for the user location.
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

def detect_specialty_from_symptoms(text):
    """Detect a likely medical specialty based on symptom keywords."""
    text_lower = text.lower()
    for specialty, keywords in SPECIALTY_KEYWORD_MAP.items():
        if any(word in text_lower for word in keywords):
            return specialty
    return None


def get_ai_symptom_assessment(text, city):
    """Use an OpenAI model to interpret symptoms and return structured triage output."""
    if not USE_AI_SYMPTOMS or not OPENAI_API_KEY or not client:
        return None

    try:
        client.api_key = OPENAI_API_KEY
        prompt = (
            "You are a medical triage assistant for an emergency navigation app. "
            "Analyze the user symptom description and return only a JSON object with the following keys: "
            "urgency, specialist, reason, detected_specialty. "
            "urgency must be one of RED, YELLOW, or GREEN. "
            "specialist should be an object with en, az, ru translations. "
            "reason should be an object with en, az, ru translations. "
            "detected_specialty should be one of dentist, dermatologist, cardiologist, ophthalmologist, orthopedic, or general. "
            "Use the city only for context if helpful. "
            "Do not include any additional text outside the JSON object.\n\n"
            f"Symptoms: {text}\n"
            f"City: {city}\n"
        )

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': 'You are a safely constrained assistant for symptom triage.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.2,
            max_tokens=400
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        # Validate returned structure and normalize values
        if isinstance(parsed, dict):
            return {
                'city': city,
                'urgency': parsed.get('urgency', 'GREEN'),
                'specialist': parsed.get('specialist', {'en': 'Primary Care Practitioner', 'az': 'Ailə Həkimi / Terapevt', 'ru': 'Участковый Терапевт'}),
                'reason': parsed.get('reason', {'en': 'Mild symptoms. Monitor locally.', 'az': 'Yüngül simptomlar. Nəzarət edin.', 'ru': 'Легкие симптомы. Наблюдайте за состоянием.'}),
                'detected_specialty': parsed.get('detected_specialty', 'general'),
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
            headers={
                'User-Agent': 'AI-SymptomTriage/1.0',
                'Accept': 'application/json'
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()

            for element in data.get('elements', []):
                # Get coordinates
                if 'center' in element:
                    h_lat = element['center']['lat']
                    h_lng = element['center']['lon']
                elif 'lat' in element:
                    h_lat = element['lat']
                    h_lng = element['lon']
                else:
                    continue
                
                # Get name and address
                tags = element.get('tags', {})
                name = tags.get('name', tags.get('operator', 'Hospital/Clinic'))
                address_parts = []
                if tags.get('addr:street'):
                    address_parts.append(tags.get('addr:street'))
                if tags.get('addr:housenumber'):
                    address_parts.append(tags.get('addr:housenumber'))
                address = ', '.join(address_parts).strip() or 'Address unavailable'

                # Calculate distance correctly
                try:
                    distance = geodesic((lat, lng), (h_lat, h_lng)).km
                except:
                    distance = 0.0

                # Check if has emergency services
                has_emergency = tags.get('emergency') == 'yes' or tags.get('amenity') == 'hospital'
                
                hospitals.append({
                    'name': name,
                    'address': address,
                    'latitude': h_lat,
                    'longitude': h_lng,
                    'distance': round(distance, 2),
                    'has_emergency': has_emergency
                })
            
            # Sort hospitals by distance if any results exist
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

def analyze_symptoms_and_generate_map_ai(text, city, specialty=None):
    """Consolidated logic analyzing symptom context and building map arrays."""
    text_lower = text.lower()

    # If enabled, try the AI-powered symptom analysis first
    ai_result = get_ai_symptom_assessment(text, city)
    if ai_result is not None:
        return ai_result
    
    # Generate hospital nodes matching the user's automatically detected location
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

    # Symptom urgency mapping logic
    red_keywords = ['chest', 'heart', 'nəfəs', 'ürək', 'insult', 'nəfəsalma', 'qan', 'боль', 'грудь', 'сердце', 'дыхание', 'кровь', 'инсульт']
    yellow_keywords = ['burn', 'cut', 'fever', 'fracture', 'yanıq', 'kəsik', 'qızdırma', 'sınıq', 'göz', 'baş ağrısı', 'ожог', 'порез', 'лихорадка', 'перелом', 'глаз', 'головная боль']
    
    if any(word in text_lower for word in red_keywords):
        urgency, spec_en, spec_az, spec_ru, reas_en, reas_az, reas_ru = "RED", "Emergency Physician / Cardiologist", "Təcili Tibbi Yardım Həkimi / Kardioloq", "Врач Скорой Помощи / Кардиолог", "Potential life-threatening critical cardiovascular event.", "Həyat üçün təhlükə yarada bilən kəskin ürək-damar çatışmazlığı.", "Потенциально опасное для жизни острое сердечно-сосудистое нарушение."
    elif any(word in text_lower for word in yellow_keywords):
        urgency, spec_en, spec_az, spec_ru, reas_en, reas_az, reas_ru = "YELLOW", "Urgent Care Specialist", "Təcili Baxım Mütəxəssisi", "Специалист Неотложной Помощи", "Acute condition requiring rapid target diagnostic screening.", "Tez diaqnostik müayinə tələb edən kəskin vəziyyət.", "Острое состояние, требующее быстрой целенаправленной диагностики."
    else:
        urgency, spec_en, spec_az, spec_ru, reas_en, reas_az, reas_ru = "GREEN", "Primary Care Practitioner", "Ailə Həkimi / Terapevt", "Участковый Терапевт", "Mild systemic presentation. Monitor symptoms locally.", "Yüngül simptomlar. Vəziyyəti yerli olaraq nəzarətdə saxlayın.", "Легкие симптомы. Наблюдайте за состоянием дома."

    if specialty == 'dentist':
        spec_en = "Dental Care Specialist"
        spec_az = "Diş Həkimi / Stomatoloq"
        spec_ru = "Стоматолог"
        reas_en = "Symptom pattern suggests dental pain or oral health care."
        reas_az = "Simptomlar diş ağrısı və ya ağız sağlamığına işarə edir."
        reas_ru = "Симптомы указывают на зубную боль или стоматологическую помощь."
    elif specialty == 'dermatologist':
        spec_en = "Dermatologist"
        spec_az = "Dermatoloq"
        spec_ru = "Дерматолог"
        reas_en = "Skin-related symptoms suggest consultation with a dermatologist."
        reas_az = "Dəri ilə bağlı simptomlar dermatoloq məsləhətinə ehtiyac olduğunu göstərir."
        reas_ru = "Симптомы кожи указывают на консультацию у дерматолога."
    elif specialty == 'cardiologist':
        spec_en = "Cardiologist"
        spec_az = "Kardioloq"
        spec_ru = "Кардиолог"
        reas_en = "Complaints are consistent with heart or cardiovascular care."
        reas_az = "Şikayətlər ürək və ya ürək-damar baxımına uyğundur."
        reas_ru = "Жалобы соответствуют сердечно-сосудистому уходу."
    elif specialty == 'ophthalmologist':
        spec_en = "Ophthalmologist"
        spec_az = "Oftalmoloq"
        spec_ru = "Офтальмолог"
        reas_en = "Eye symptoms indicate specialist eye care is recommended."
        reas_az = "Göz simptomları ixtisaslı göz baxımını tövsiyə edir."
        reas_ru = "Симптомы глаз указывают на необходимость специализированной офтальмологической помощи."
    elif specialty == 'orthopedic':
        spec_en = "Orthopedic Specialist"
        spec_az = "Ortopedik Mütəxəssis"
        spec_ru = "Ортопед"
        reas_en = "Musculoskeletal complaints suggest orthopedic evaluation."
        reas_az = "Əzələ-sümük şikayətləri ortopedik müayinə tələb edir."
        reas_ru = "Мышечно-скелетные жалобы требуют ортопедической оценки."

    return {
        "city": city,
        "urgency": urgency,
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
        
        # 1. Automatically track user location city based on incoming telemetry coordinates
        detected_city = get_city_from_coordinates(lat, lng)
        
        # 2. Optionally perform specialty-aware search if the client requested it
        use_specialty = bool(data.get('use_specialty', False))
        if use_specialty:
            detected_specialty = detect_specialty_from_symptoms(symptoms)
            ai_payload = analyze_symptoms_and_generate_map_ai(symptoms, detected_city, specialty=detected_specialty)
            hospitals = get_hospitals_from_openstreetmap(lat, lng, radius_km=10, specialty=detected_specialty)
            if not hospitals:
                hospitals = get_nearest_health_suggestions(lat, lng, detected_city)
            ai_payload['specialty_search'] = detected_specialty or 'general'
        else:
            ai_payload = analyze_symptoms_and_generate_map_ai(symptoms, detected_city)
            hospitals = get_hospitals_from_openstreetmap(lat, lng, radius_km=10)
            if not hospitals:
                hospitals = get_nearest_health_suggestions(lat, lng, detected_city)
        ai_payload['hospitals'] = hospitals

        # 4. Log results inside relational database ledger tables
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO triage_logs (symptoms_text, urgency_level, detected_city, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
                       (symptoms, ai_payload['urgency'], detected_city, lat, lng))
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
