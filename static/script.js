const dictionary = {
    az: {
        mainTitle: "Symptom Triage", inputHeading: "Diaqnostik Giriş Sistemi", inputSub: "Simptomlarınızı sərbəst şəkildə yazın:",
        placeholder: "Məsələn: Qəfil sinə ağrısı başladı, nəfəs almaq çətindir...", checkboxText: "Bunun rəsmi tibbi məsləhət olmadığını və bir AI simulyasiyası olduğunu anlayıram.",
        btnText: "Təhlil Et", btnLoading: "Simptomlar təhlil olunur və nəticələr hazırlanır...", disclaimer: "<strong>DİQQƏT:</strong> Bu proqram AI hackathon prototipidir. Ciddi və həyati təhlükə zamanı dərhal yerli təcili yardım xidmətinə (103) zəng edin.",
        outputHeading: "Klinik Qiymətləndirmə Paneli", lblReason: "Səbəb:", lblSpecialist: "Məsləhət Görülən Həkim:", facilitiesHeading: "Yaxın Hospitals/Klinikalar (Təkliflər)", mapHeading: "OpenStreetMap - İnteraktiv Xəritə",
        statusRed: "🔴 TƏCİLİ - Qırmızı Status", statusYellow: "🟡 VACİB - Sarı Status", statusGreen: "🟢 Stabil - Yaşıl Status", erOpen: "🔴 24/7 Təcili Yardım Var", erClosed: "⏰ Yalnız İş Saatları", kmAway: "km",
        pharmaciesHeading: "Yaxın Apteklər (Əlavə)",
        noHospitals: "Yaxınlıqda xəstəxana/klinika tapılmadı.",
        noPharmacies: "Yaxınlıqda aptek tapılmadı.",
        locActive: "📍 Mövqe sinxronizasiyası aktivdir. Hazırkı mövqeyiniz yüklənir.", locDenied: "🔒 Mövqe icazəsi verilmədi. Standart koordinatlara geri dönüldü.",
        agePlh: "Yaşınız (Məs: 35)", genNone: "Cinsiyyət (Seçilməyib)", genM: "Kişi", genF: "Qadın", chronicPlh: "Xroniki xəstəliklər (Məs: Diabet, Astma... Yoxdursa boş buraxın)"
    },
    en: {
        mainTitle: "Symptom Triage", inputHeading: "Diagnostic Input Engine", inputSub: "Describe your symptoms in plain language:",
        placeholder: "Example: Experiencing sudden sharp chest pain and tightness...", checkboxText: "I understand this is an AI hackathon simulation and not official medical advice.",
        btnText: "Analyze", btnLoading: "Analyzing symptoms and preparing your results...", disclaimer: "<strong>CRITICAL NOTICE:</strong> This application is an AI prototype mockup template. If experiencing emergency threats, dial 103 immediately.",
        outputHeading: "Clinical Assessment Dashboard", lblReason: "Clinical Reason:", lblSpecialist: "Direct Route Referral:", facilitiesHeading: "Nearby Hospitals/Clinics (Suggested)", mapHeading: "OpenStreetMap - Interactive Map",
        statusRed: "RED EMERGENCY CARE STATUS", statusYellow: "YELLOW URGENT DISPATCH REQUIRED", statusGreen: "GREEN LOW URGENCY PROFILE", erOpen: "🔴 Emergency Services Operational", erClosed: "⏰ Clinic Hours Apply", kmAway: "km",
        pharmaciesHeading: "Nearby Pharmacies (Additional)",
        noHospitals: "No nearby hospital/clinic suggestions are available.",
        noPharmacies: "No nearby pharmacies are available.",
        locActive: "📍 Location sync active: your current position is being used.", locDenied: "🔒 Geolocation blocked. Fallback coordinates are active.",
        agePlh: "Age (e.g. 35)", genNone: "Gender (Not specified)", genM: "Male", genF: "Female", chronicPlh: "Chronic conditions (e.g. Diabetes... Leave empty if none)"
    },
    ru: {
        mainTitle: "Symptom Triage", inputHeading: "Система Диагностики", inputSub: "Опишите ваши симптомы в свободной форме:",
        placeholder: "Например: Началась внезапная острая боль в груди, трудно дышать...", checkboxText: "Я понимаю, что это симуляция AI для хакатона и не является официальной медицинской консультацией.",
        btnText: "Анализировать", btnLoading: "Анализ симптомов и подготовка результатов...", disclaimer: "<strong>ВАЖНОЕ УВЕДОМЛЕНИЕ:</strong> Это приложение является прототипом AI для хакатона. При угрозе жизни немедленно звоните 103.",
        outputHeading: "Панель Клинической Оценки", lblReason: "Причина:", lblSpecialist: "Рекомендуемый Специалист:", facilitiesHeading: "Ближайшие Больницы/Клиники (Рекомендации)", mapHeading: "OpenStreetMap - Интерактивная Карта",
        statusRed: "🔴 СРОЧНО - Красный Статус", statusYellow: "🟡 ВНИМАНИЕ - Желтый Статус", statusGreen: "🟢 Стабильно - Зеленый Статус", erOpen: "🔴 Есть Экстренная Помощь", erClosed: "⏰ Только в рабочие часы", kmAway: "км",
        pharmaciesHeading: "Ближайшие Аптеки (Дополнительно)",
        noHospitals: "Поблизости нет рекомендаций больниц/клиник.",
        noPharmacies: "Поблизости нет аптек.",
        locActive: "📍 Геопозиция синхронизирована: используется ваше текущее положение.", locDenied: "🔒 Доступ к геопозиции ограничен. Используются стандартные координаты.",
        agePlh: "Возраст (напр. 35)", genNone: "Пол (Не указан)", genM: "Мужской", genF: "Женский", chronicPlh: "Хронические заболевания (напр. Диабет... Оставьте пустым, если нет)"
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
    if (!document.getElementById('osmMap')) return;
    if (!osmMap) {
        initializeOSMMap();
    }
    if (!osmMap) return;
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
    if (!osmMap) {
        hospitalMarkers = [];
        return;
    }
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
    
    const titleEl = document.getElementById('mainTitle');
    if (titleEl) titleEl.innerText = dict.mainTitle;
    const inputHeading = document.getElementById('inputHeading');
    if (inputHeading) inputHeading.innerText = dict.inputHeading;
    const inputSub = document.getElementById('inputSub');
    if (inputSub) inputSub.innerText = dict.inputSub;
    const symptomsInput = document.getElementById('symptomsInput');
    if (symptomsInput) symptomsInput.placeholder = dict.placeholder;
    const checkboxText = document.getElementById('checkboxText');
    if (checkboxText) checkboxText.innerText = dict.checkboxText;
    const ageInput = document.getElementById('ageInput');
    if (ageInput) ageInput.placeholder = dict.agePlh;
    const optGenNone = document.getElementById('optGenNone');
    if (optGenNone) optGenNone.innerText = dict.genNone;
    const optGenM = document.getElementById('optGenM');
    if (optGenM) optGenM.innerText = dict.genM;
    const optGenF = document.getElementById('optGenF');
    if (optGenF) optGenF.innerText = dict.genF;
    const chronicInput = document.getElementById('chronicInput');
    if (chronicInput) chronicInput.placeholder = dict.chronicPlh;
    
    const submitBtn = document.getElementById('submitBtn');
    if (submitBtn) submitBtn.innerText = dict.btnText;
    const disclaimerText = document.getElementById('disclaimerText');
    if (disclaimerText) disclaimerText.innerHTML = dict.disclaimer;
    const outputHeading = document.getElementById('outputHeading');
    if (outputHeading) outputHeading.innerText = dict.outputHeading;
    const lblReason = document.getElementById('lblReason');
    if (lblReason) lblReason.innerText = dict.lblReason;
    const lblSpecialist = document.getElementById('lblSpecialist');
    if (lblSpecialist) lblSpecialist.innerText = dict.lblSpecialist;
    const facilitiesHeading = document.getElementById('facilitiesHeading');
    if (facilitiesHeading) facilitiesHeading.innerText = dict.facilitiesHeading;
    const mapHeading = document.getElementById('mapHeading');
    if (mapHeading) mapHeading.innerText = dict.mapHeading;

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
        const ageVal = document.getElementById('ageInput').value;
        const genderVal = document.getElementById('genderInput').value;
        const chronicVal = document.getElementById('chronicInput').value.trim();
        const parsedAge = ageVal === '' ? null : Number(ageVal);

        const payloadBody = {
            symptoms: symptoms,
            age: Number.isFinite(parsedAge) ? parsedAge : null,
            gender: genderVal || "",
            chronic_conditions: chronicVal,
            use_specialty: true,
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
                openResultInNewTab(payload.data, lang);  // ← dəyişiklik burada
                lastServerResponse = null;
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
    if (osmMap) {
        if (accuracyCircle) {
            try { osmMap.removeLayer(accuracyCircle); } catch(e){}
            accuracyCircle = null;
        }
        if (lastAccuracy) {
            accuracyCircle = L.circle([hardwareLat, hardwareLng], { radius: lastAccuracy, color: '#60a5fa', weight: 1, fillOpacity: 0.05 }).addTo(osmMap);
        }
    }

    // Helpful debug logging (console only, no UI change)
    console.debug('GPS sample count:', lastPositions.length);
    console.debug('Latest raw:', lat.toFixed(6), lng.toFixed(6));
    console.debug('Smoothed (median):', hardwareLat, hardwareLng, 'accuracy:', lastAccuracy);

    updateAdvisorAlertStatus("locActive", hardwareLat, hardwareLng);
    updateMapCenter(hardwareLat, hardwareLng);
}

function openResultInNewTab(aiData, lang) {
    const dict = dictionary[lang];
    const urgencyColors = { RED: '#ef4444', YELLOW: '#eab308', GREEN: '#10b981' };
    const badgeColor = urgencyColors[aiData.urgency] || '#10b981';
    const badgeText = aiData.urgency === 'RED' ? dict.statusRed :
                      (aiData.urgency === 'YELLOW' ? dict.statusYellow : dict.statusGreen);

    const hospitals = aiData.hospitals || [];
    const hospitalsHTML = hospitals.length ? hospitals.map((h, i) =>
        '<div class="list-card">' +
        '<strong>' + (i + 1) + '. ' + h.name + '</strong><br>' +
        '<small>' + h.address + '</small><br>' +
        '<small><b>' + h.distance + ' km</b></small><br>' +
        '<span class="status-text" style="color:' + (h.has_emergency ? '#ef4444' : '#64748b') + ';">' +
        (h.has_emergency ? dict.erOpen : dict.erClosed) +
        '</span></div>'
    ).join('') : '<div class="empty-state">' + dict.noHospitals + '</div>';

    const pharmacies = aiData.pharmacies || [];
    const pharmaciesHTML = pharmacies.length ? pharmacies.map((p, i) =>
        '<div class="list-card pharmacy-card">' +
        '<strong>' + (i + 1) + '. ' + p.name + '</strong><br>' +
        '<small>' + p.address + '</small><br>' +
        '<small><b>' + p.distance + ' km</b></small>' +
        '</div>'
    ).join('') : '<div class="empty-state">' + dict.noPharmacies + '</div>';

    const centerLat = hardwareLat;
    const centerLng = hardwareLng;
    const hospitalsJSON = JSON.stringify(aiData.hospitals || []);

    const htmlContent =
        '<!DOCTYPE html><html lang="' + lang + '">' +
        '<head><meta charset="UTF-8"><title>' + dict.outputHeading + '</title>' +
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>' +
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"><\/script>' +
        '<style>' +
        'body{font-family:sans-serif;max-width:980px;margin:40px auto;padding:0 20px;background:#f8fafc;}' +
        '.badge{display:inline-block;padding:10px 20px;border-radius:999px;color:#fff;font-weight:bold;font-size:15px;background:' + badgeColor + ';margin-bottom:16px;}' +
        '.results-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start;}' +
        '.list-card{border:1px solid #e2e8f0;border-radius:8px;padding:12px;margin-bottom:10px;background:#fff;}' +
        '.pharmacy-card{border-color:#d8f5ea;background:#f8fffb;}' +
        '.status-text{font-size:11px;font-weight:bold;}' +
        '.empty-state{border:1px dashed #cbd5e1;border-radius:8px;padding:12px;background:#f8fafc;color:#64748b;font-size:13px;}' +
        '#resultMap{height:420px;border-radius:12px;margin-top:20px;}' +
        'h2{color:#0f172a;}h3{color:#1e40af;margin-top:0;margin-bottom:12px;}' +
        '@media(max-width:820px){.results-grid{grid-template-columns:1fr;} }' +
        '</style></head>' +
        '<body>' +
        '<h2>' + dict.outputHeading + '</h2>' +
        '<div class="badge">' + badgeText + '</div>' +
        '<p><strong>' + dict.lblReason + '</strong> ' + aiData.reason[lang] + '</p>' +
        '<p><strong>' + dict.lblSpecialist + '</strong> ' + aiData.specialist[lang] + '</p>' +
        '<div class="results-grid">' +
        '<div>' +
        '<h3>' + dict.facilitiesHeading + '</h3>' +
        hospitalsHTML +
        '</div>' +
        '<div>' +
        '<h3>' + dict.pharmaciesHeading + '</h3>' +
        pharmaciesHTML +
        '</div>' +
        '</div>' +
        '<h3 style="margin-top:24px;">' + dict.mapHeading + '</h3>' +
        '<div id="resultMap"></div>' +
        '<script>' +
        'var map=L.map("resultMap").setView([' + centerLat + ',' + centerLng + '],13);' +
        'L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:"© OpenStreetMap contributors",maxZoom:19}).addTo(map);' +
        'L.circleMarker([' + centerLat + ',' + centerLng + '],{radius:10,fillColor:"#3b82f6",color:"#fff",weight:2,fillOpacity:0.8}).addTo(map).bindPopup("Your Location");' +
        'var hospitals=' + hospitalsJSON + ';' +
        'hospitals.forEach(function(h){' +
        'L.circleMarker([h.latitude,h.longitude],{radius:8,fillColor:h.has_emergency?"#ef4444":"#eab308",color:"#fff",weight:2,fillOpacity:0.8})' +
        '.addTo(map).bindPopup("<strong>"+h.name+"<\/strong><br>"+h.distance+" km");' +
        '});' +
        'if(hospitals.length>0){' +
        'var pts=[[' + centerLat + ',' + centerLng + ']].concat(hospitals.map(function(h){return[h.latitude,h.longitude];}));' +
        'map.fitBounds(L.latLngBounds(pts),{padding:[50,50]});' +
        '}' +
        '<\/script>' +
        '</body></html>';

    // Blob URL metodu — popup blocker-i keçir
    var blob = new Blob([htmlContent], { type: 'text/html' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function() { URL.revokeObjectURL(url); }, 15000);
}

function updateOutputUIValues(aiData, lang) {
    const dict = dictionary[lang];
    const outputPanel = document.getElementById('outputPanel');
    if (!outputPanel) return;
    outputPanel.style.opacity = "1";
    outputPanel.style.pointerEvents = "auto";

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
