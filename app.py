import math
import os
import json
import sqlite3
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DB_FILE = 'ai_auto_map_audit.db'

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
    Analyzes coordinates to determine the target city area locally,
    ensuring rapid hackathon delivery with zero external API timeout risks.
    """
    # Baku coordinate bounding box constraints
    if 40.30 <= lat <= 40.50 and 49.70 <= lng <= 49.95:
        return "Baku"
    # Ganja coordinate bounding box constraints
    elif 40.60 <= lat <= 40.75 and 46.30 <= lng <= 46.45:
        return "Ganja"
    # Sumqayit coordinate bounding box constraints
    elif 40.50 <= lat <= 40.65 and 49.55 <= lng <= 49.70:
        return "Sumqayit"
    else:
        return "Baku" # Safe production default fallback

def analyze_symptoms_and_generate_map_ai(text, city):
    """Consolidated logic analyzing symptom context and building map arrays."""
    text_lower = text.lower()
    
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
        
        # 2. Build consolidated AI analytical assessment payload
        ai_payload = analyze_symptoms_and_generate_map_ai(symptoms, detected_city)
        
        # 3. Log results inside relational database ledger tables
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO triage_logs (symptoms_text, urgency_level, detected_city, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
                       (symptoms, ai_payload['urgency'], detected_city, lat, lng))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "data": ai_payload})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    setup_database_automatically()
    app.run(debug=True, port=5000)
