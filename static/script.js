const dictionary = {
    az: {
        mainTitle: "🏥 AI SymptomTriage", inputHeading: "Diaqnostik Giriş Sistemi", inputSub: "Simptomlarınızı sərbəst şəkildə yazın:",
        placeholder: "Məsələn: Qəfil sinə ağrısı başladı, nəfəs almaq çətindir...", checkboxText: "Bunun rəsmi tibbi məsləhət olmadığını və bir AI simulyasiyası olduğunu anlayıram.",
        btnText: "Təhlil Et & Xəritəni Qur", btnLoading: "Simptomlar tehlil olunur ve yaxın tibb məntəqələri siyahısı yüklənir...", disclaimer: "<strong>DİQQƏT:</strong> Bu proqram AI hackathon prototipidir. Ciddi və həyati təhlükə zamanı dərhal yerli təcili yardım xidmətinə (112) zəng edin.",
        outputHeading: "Klinik Qiymətləndirmə Paneli", lblReason: "Səbəb:", lblSpecialist: "Məsləhət Görülən Həkim:", facilitiesHeading: "Yaxın Hospitals/Klinikalar (Təkliflər)", mapHeading: "OpenStreetMap - İnteraktiv Xəritə",
        statusRed: "🔴 TƏCİLİ - Qırmızı Status", statusYellow: "🟡 VACİB - Sarı Status", statusGreen: "🟢 Stabil - Yaşıl Status", erOpen: "🔴 24/7 Təcili Yardım Var", erClosed: "⏰ Yalnız İş Saatları", kmAway: "km",
        locActive: "📍 Mövqe sinxronizasiyası aktivdir. Hazırkı mövqeyiniz yüklənir.", locDenied: "🔒 Mövqe icazəsi verilmədi. Standart koordinatlara geri dönüldü."
    },
    en: {
        mainTitle: "🏥 AI SymptomTriage", inputHeading: "Diagnostic Input Engine", inputSub: "Describe your symptoms in plain language:",
        placeholder: "Example: Experiencing sudden sharp chest pain and tightness...", checkboxText: "I understand this is an AI hackathon simulation and not official medical advice.",
        btnText: "Analyze & Load Map", btnLoading: "Analyzing symptoms and loading nearby medical facilities' list...", disclaimer: "<strong>CRITICAL NOTICE:</strong> This application is an AI prototype mockup template. If experiencing emergency threats, dial 112 immediately.",
        outputHeading: "Clinical Assessment Dashboard", lblReason: "Clinical Reason:", lblSpecialist: "Direct Route Referral:", facilitiesHeading: "Nearby Hospitals/Clinics (Suggested)", mapHeading: "OpenStreetMap - Interactive Map",
        statusRed: "RED EMERGENCY CARE STATUS", statusYellow: "YELLOW URGENT DISPATCH REQUIRED", statusGreen: "GREEN LOW URGENCY PROFILE", erOpen: "🔴 Emergency Services Operational", erClosed: "⏰ Clinic Hours Apply", kmAway: "km",
        locActive: "📍 Location sync active: your current position is being used.", locDenied: "🔒 Geolocation blocked. Fallback coordinates are active."
    },
    ru: {
        mainTitle: "🏥 AI SymptomTriage", inputHeading: "Система Диагностики", inputSub: "Опишите ваши симптомы в свободной форме:",
        placeholder: "Например: Началась внезапная острая боль в груди, трудно дышать...", checkboxText: "Я понимаю, что это симуляция AI для хакатона и не является официальной медицинской консультацией.",
        btnText: "Анализировать & Загрузить Карту", btnLoading: "Анализ симптомов и загрузка списка ближайших медицинских учреждений...", disclaimer: "<strong>ВАЖНОЕ УВЕДОМЛЕНИЕ:</strong> Это приложение является прототипом AI для хакатона. При угрозе жизни немедленно звоните 112.",
        outputHeading: "Панель Клинической Оценки", lblReason: "Причина:", lblSpecialist: "Рекомендуемый Специалист:", facilitiesHeading: "Ближайшие Больницы/Клиники (Рекомендации)", mapHeading: "OpenStreetMap - Интерактивная Карта",
        statusRed: "🔴 СРОЧНО - Красный Статус", statusYellow: "🟡 ВНИМАНИЕ - Желтый Статус", statusGreen: "🟢 Стабильно - Зеленый Статус", erOpen: "🔴 Есть Экстренная Помощь", erClosed: "⏰ Только в рабочие часы", kmAway: "км",
        locActive: "📍 Геопозиция синхронизирована: используется ваше текущее положение.", locDenied: "🔒 Доступ к геопозиции ограничен. Используются стандартные координаты."
    }
};

let lastServerResponse = null;
let hardwareLat = 40.3700; 
let hardwareLng = 49.8372;
let lastPositions = [];
let lastAccuracy = null;
let accuracyCircle = null;
let osmMap = null;
let hospitalMarkers = [];
let userMarker = null;
let watchId = null;

window.addEventListener('load', () => {
    initializeOSMMap();
    
    if (navigator.geolocation) {
        startGeolocationWatch();
    } else {
        updateAdvisorAlertStatus("locDenied");
        initializeOSMMap();
    }
    switchLanguageInterface();
});

function initializeOSMMap() {
    const mapContainer = document.getElementById('osmMap');
    if (!mapContainer || osmMap) return;
    
    // Initialize Leaflet map centered on user location
    osmMap = L.map('osmMap').setView([hardwareLat, hardwareLng], 13);
    
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(osmMap);
    
    // Add user location marker
    userMarker = L.circleMarker([hardwareLat, hardwareLng], {
        radius: 10,
        fillColor: "#3b82f6",
        color: "#ffffff",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.8
    }).addTo(osmMap).bindPopup("📍 Your Location");
}

function updateMapCenter(lat, lng) {
    if (!osmMap) {
        initializeOSMMap();
    }
    osmMap.setView([lat, lng], 13);
    if (userMarker) {
        userMarker.setLatLng([lat, lng]);
    } else {
        userMarker = L.circleMarker([lat, lng], {
            radius: 10,
            fillColor: "#3b82f6",
            color: "#ffffff",
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        }).addTo(osmMap).bindPopup("📍 Your Location");
    }
}

function startGeolocationWatch() {
    if (!navigator.geolocation) {
        updateAdvisorAlertStatus("locDenied");
        return;
    }

    watchId = navigator.geolocation.watchPosition(
        (pos) => {
            handleNewPosition(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
        },
        () => {
            updateAdvisorAlertStatus("locDenied");
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
}

function clearHospitalMarkers() {
    hospitalMarkers.forEach(marker => osmMap.removeLayer(marker));
    hospitalMarkers = [];
}

function updateAdvisorAlertStatus(key, lat, lng) {
    const lang = document.getElementById('langSheet').value;
    const banner = document.getElementById('locationAdvisor');
    if (banner) {
        let message = dictionary[lang][key] || '';
        banner.innerHTML = message;
        banner.setAttribute('data-loc-state', key);
        if (key === 'locActive') {
            banner.style.background = "#f0fdf4";
            banner.style.borderColor = "#bbf7d0";
            banner.style.color = "#166534";
        } else {
            banner.style.background = "#f8fafc";
            banner.style.borderColor = "#cbd5e1";
            banner.style.color = "#475569";
        }
    }
}

function switchLanguageInterface() {
    const lang = document.getElementById('langSheet').value;
    const dict = dictionary[lang];
    
    document.getElementById('mainTitle').innerText = dict.mainTitle;
    document.getElementById('inputHeading').innerText = dict.inputHeading;
    document.getElementById('inputSub').innerText = dict.inputSub;
    document.getElementById('symptomsInput').placeholder = dict.placeholder;
    document.getElementById('checkboxText').innerText = dict.checkboxText;
    
    document.getElementById('submitBtn').innerText = dict.btnText;
    document.getElementById('disclaimerText').innerHTML = dict.disclaimer;
    document.getElementById('outputHeading').innerText = dict.outputHeading;
    document.getElementById('lblReason').innerText = dict.lblReason;
    document.getElementById('lblSpecialist').innerText = dict.lblSpecialist;
    document.getElementById('facilitiesHeading').innerText = dict.facilitiesHeading;
    document.getElementById('mapHeading').innerText = dict.mapHeading;

    const banner = document.getElementById('locationAdvisor');
    if (banner) {
        const currentStateKey = banner.getAttribute('data-loc-state') || "locActive";
        updateAdvisorAlertStatus(currentStateKey, hardwareLat, hardwareLng);
    }

    if (lastServerResponse) {
        updateOutputUIValues(lastServerResponse, lang);
    }
}

function runTriagePipeline() {
    const lang = document.getElementById('langSheet').value;
    const symptoms = document.getElementById('symptomsInput').value.trim();
    if (!symptoms) return alert(dictionary[lang].alertEmpty || "Please specify active input data.");
    if (!document.getElementById('disclaimerCheck').checked) return alert(dictionary[lang].alertCheck || "Accept confirmation statement parameter box.");

    const btn = document.getElementById('submitBtn');
    btn.disabled = true; btn.innerText = dictionary[lang].btnLoading;

    const submitData = () => {
        const payloadBody = {
            symptoms: symptoms,
            latitude: typeof hardwareLat !== 'undefined' ? hardwareLat : 40.3700,
            longitude: typeof hardwareLng !== 'undefined' ? hardwareLng : 49.8372
        };
            

        fetch('/api/triage', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payloadBody)
        })
        .then(res => {
            if (!res.ok) throw new Error("HTTP error: " + res.status);
            return res.json();
        })
        .then(payload => {
            if (payload.status === 'success') {
                lastServerResponse = payload.data;
                updateOutputUIValues(payload.data, lang);
            } else {
                alert('AI Core Route Fault: ' + payload.message);
            }
        })
        .catch(err => {
            console.warn("Handshake exception bypassed:", err);
            alert("Server network sync delay. Please try clicking the button again.");
        })
        .finally(() => {
            btn.disabled = false; btn.innerText = dictionary[lang].btnText;
        });
    };

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                handleNewPosition(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
                submitData();
            },
            () => {
                submitData();
            },
            { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
        );
    } else {
        submitData();
    }
}

function median(values){
    if (!values.length) return null;
    const sorted = values.slice().sort((a,b)=>a-b);
    const mid = Math.floor(sorted.length/2);
    if (sorted.length % 2) return sorted[mid];
    return (sorted[mid-1] + sorted[mid]) / 2.0;
}

function handleNewPosition(lat, lng, accuracy) {
    // keep a short rolling window of recent positions
    lastPositions.push([lat, lng]);
    if (lastPositions.length > 9) lastPositions.shift();

    const lats = lastPositions.map(p => p[0]);
    const lngs = lastPositions.map(p => p[1]);

    // median filter reduces occasional spikes
    const medLat = median(lats);
    const medLng = median(lngs);

    // fallback to mean if median is null
    const avgLat = lats.reduce((a,b)=>a+b,0)/lats.length;
    const avgLng = lngs.reduce((a,b)=>a+b,0)/lngs.length;

    hardwareLat = parseFloat((medLat !== null ? medLat : avgLat).toFixed(6));
    hardwareLng = parseFloat((medLng !== null ? medLng : avgLng).toFixed(6));

    // record accuracy and draw an accuracy circle centered on true averaged coords
    lastAccuracy = typeof accuracy === 'number' ? accuracy : lastAccuracy;
    if (accuracyCircle) {
        try { osmMap.removeLayer(accuracyCircle); } catch(e){}
        accuracyCircle = null;
    }
    if (lastAccuracy && osmMap) {
        accuracyCircle = L.circle([hardwareLat, hardwareLng], { radius: lastAccuracy, color: '#60a5fa', weight: 1, fillOpacity: 0.05 }).addTo(osmMap);
    }

    // Helpful debug logging (console only, no UI change)
    console.debug('GPS sample count:', lastPositions.length);
    console.debug('Latest raw:', lat.toFixed(6), lng.toFixed(6));
    console.debug('Smoothed (median):', hardwareLat, hardwareLng, 'accuracy:', lastAccuracy);

    updateAdvisorAlertStatus("locActive", hardwareLat, hardwareLng);
    updateMapCenter(hardwareLat, hardwareLng);
}

function updateOutputUIValues(aiData, lang) {
    const dict = dictionary[lang];
    document.getElementById('outputPanel').style.opacity = "1";
    document.getElementById('outputPanel').style.pointerEvents = "auto";

    const badge = document.getElementById('urgencyBadge');
    badge.style.display = "inline-block";
    badge.className = `badge urgency-${aiData.urgency}`;
    badge.innerText = aiData.urgency === 'RED' ? dict.statusRed : (aiData.urgency === 'YELLOW' ? dict.statusYellow : dict.statusGreen);

    document.getElementById('clinicalReason').innerText = aiData.reason[lang];
    document.getElementById('specialistTarget').innerText = aiData.specialist[lang];

    const listContainer = document.getElementById('hospitalList');
    listContainer.innerHTML = '';

    // Clear existing markers and add hospital data to map
    clearHospitalMarkers();

    const hospitals = aiData.hospitals || [];
    if (hospitals.length === 0) {
        listContainer.innerHTML = `<div class="hospital-card" style="border-color:#d1d5db;color:#334155;">No nearby hospital/clinic suggestions are available for your location.</div>`;
    }
    
    // Determine marker color based on urgency
    const markerColor = aiData.urgency === 'RED' ? '#ef4444' : (aiData.urgency === 'YELLOW' ? '#eab308' : '#10b981');
    
    hospitals.forEach((hospital, index) => {
        // Create hospital list card
        const card = document.createElement('div');
        card.className = 'hospital-card';
        card.innerHTML = `
            <strong>${index + 1}. ${hospital.name}</strong><br>
            <small>${hospital.address}</small><br>
            <small><b>${hospital.distance} ${dict.kmAway}</b></small><br>
            <span style="font-size:11px; color:${hospital.has_emergency ? 'var(--red)' : '#64748b'}; font-weight:bold;">
                ${hospital.has_emergency ? dict.erOpen : dict.erClosed}
            </span>
        `;
        listContainer.appendChild(card);

        // Add marker to map
        const iconColor = hospital.has_emergency ? '#ef4444' : '#eab308';
        const marker = L.circleMarker([hospital.latitude, hospital.longitude], {
            radius: 8,
            fillColor: iconColor,
            color: "#ffffff",
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        }).addTo(osmMap).bindPopup(`
            <strong>${hospital.name}</strong><br>
            ${hospital.address}<br>
            <b>Distance:</b> ${hospital.distance} km<br>
            ${hospital.has_emergency ? '🔴 Emergency Services Available' : '⏰ Limited Hours'}
        `);

        hospitalMarkers.push(marker);
    });

    // Fit map bounds to show user and all hospitals
    if (hospitals.length > 0 && osmMap) {
        const allPoints = [
            [hardwareLat, hardwareLng],
            ...hospitals.map(h => [h.latitude, h.longitude])
        ];
        const bounds = L.latLngBounds(allPoints);
        osmMap.fitBounds(bounds, { padding: [50, 50] });
    }
}

