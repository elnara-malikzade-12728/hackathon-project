const dictionary = {
    az: {
        mainTitle: "🏥 AI SymptomTriage", inputHeading: "Diaqnostik Giriş Sistemi", inputSub: "Simptomlarınızı sərbəst şəkildə yazın:",
        placeholder: "Məsələn: Qəfil sinə ağrısı başladı, nəfəs almaq çətindir...", checkboxText: "Bunun rəsmi tibbi məsləhət olmadığını və bir AI simulyasiyası olduğunu anlayıram.",
        btnText: "Təhlil Et & AI Xəritəni Qur", btnLoading: "Mövqe Təyin Edilir və AI Xəritə Qurulur...", disclaimer: "<strong>DİQQƏT:</strong> Bu proqram AI hackathon prototipidir. Ciddi və həyati təhlükə zamanı dərhal yerli təcili yardım xidmətinə (112) zəng edin.",
        outputHeading: "Klinik Qiymətləndirmə Paneli", lblReason: "Səbəb:", lblSpecialist: "Məsləhət Görülən Həkim:", facilitiesHeading: "AI Regional Tibb Obyektləri", mapHeading: "Nativ İnteraktiv AI Xəritə Paneli",
        statusRed: "🔴 TƏCİLİ - Qırmızı Status", statusYellow: "🟡 VACİB - Sarı Status", statusGreen: "🟢 Stabil - Yaşıl Status", erOpen: "🔴 24/7 Təcili Yardım Var", erClosed: "⏰ Yalnız İş Saatları", kmAway: "km (AI Təxmini)",
        locBaku: "📍 Mövqe Sinxronizasiyası Aktivdir: Hazırkı qlobal mövqeyiniz izlənilir.", locDenied: "🔒 Mövqe icazəsi verilmədi. Standart şəhər koordinatları aktivdir."
    },
    en: {
        mainTitle: "🏥 AI SymptomTriage", inputHeading: "Diagnostic Input Engine", inputSub: "Describe your symptoms in plain language:",
        placeholder: "Example: Experiencing sudden sharp chest pain and tightness...", checkboxText: "I understand this is an AI hackathon simulation and not official medical advice.",
        btnText: "Analyze Status & Render AI Map", btnLoading: "Syncing GPS and generating AI vectors...", disclaimer: "<strong>CRITICAL NOTICE:</strong> This application is an AI prototype mockup template. If experiencing emergency threats, dial 112 immediately.",
        outputHeading: "Clinical Assessment Dashboard", lblReason: "Clinical Reason:", lblSpecialist: "Direct Route Referral:", facilitiesHeading: "AI Generated Regional Facilities", mapHeading: "Native Interactive AI Map Canvas",
        statusRed: "RED EMERGENCY CARE STATUS", statusYellow: "YELLOW URGENT DISPATCH REQUIRED", statusGreen: "GREEN LOW URGENCY PROFILE", erOpen: "🔴 Emergency Services Operational", erClosed: "⏰ Clinic Hours Apply", kmAway: "km (AI Estimated)",
        locBaku: "📍 Location Sync Active: Your real-time position is tracked.", locDenied: "🔒 Geolocation blocked. Running fallback town baseline."
    },
    ru: {
        mainTitle: "🏥 AI SymptomTriage", inputHeading: "Система Диагностики", inputSub: "Опишите ваши симптомы в свободной форме:",
        placeholder: "Например: Началась внезапная острая боль в груди, трудно дышать...", checkboxText: "Я понимаю, что это симуляция AI для хакатона и не является официальной медицинской консультацией.",
        btnText: "Анализировать и Создать AI Карту", btnLoading: "Синхронизация GPS и расчет AI карт...", disclaimer: "<strong>ВАЖНОЕ УВЕДОМЛЕНИЕ:</strong> Это приложение является прототипом AI для хакатона. При угрозе жизни немедленно звоните 112.",
        outputHeading: "Панель Клинической Оценки", lblReason: "Причина:", lblSpecialist: "Рекомендуемый Специалист:", facilitiesHeading: "Объекты, Сгенерированные AI", mapHeading: "Интерактивный AI Холст Карты",
        statusRed: "🔴 СРОЧНО - Красный Статус", statusYellow: "🟡 ВНИМАНИЕ - Желтый Статус", statusGreen: "🟢 Стабильно - Зеленый Статус", erOpen: "🔴 Есть Экстренная Помощь", erClosed: "⏰ Только в рабочие часы", kmAway: "км (Расчет AI)",
        locBaku: "📍 Геопозиция Синхронизирована: Живое отслеживание активно.", locDenied: "🔒 Доступ к геопозиции ограничен. Используются стандартные координаты."
    }
};

let lastServerResponse = null;
let hardwareLat = 40.3700; 
let hardwareLng = 49.8372;

window.addEventListener('load', () => {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                hardwareLat = pos.coords.latitude;
                hardwareLng = pos.coords.longitude;
                updateAdvisorAlertStatus("locBaku");
                renderBlankGridOnCanvas();
            },
            () => {
                updateAdvisorAlertStatus("locDenied");
                renderBlankGridOnCanvas();
            }
        );
    } else {
        updateAdvisorAlertStatus("locDenied");
        renderBlankGridOnCanvas();
    }
    switchLanguageInterface();
});

function updateAdvisorAlertStatus(key) {
    const lang = document.getElementById('langSheet').value;
    const banner = document.getElementById('locationAdvisor');
    if (banner) {
        banner.innerHTML = dictionary[lang][key];
        banner.setAttribute('data-loc-state', key);
        if (key === 'locBaku') {
            banner.style.background = "#f0fdf4"; banner.style.borderColor = "#bbf7d0"; banner.style.color = "#166534";
        } else {
            banner.style.background = "#f8fafc"; banner.style.borderColor = "#cbd5e1"; banner.style.color = "#475569";
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
        const currentStateKey = banner.getAttribute('data-loc-state') || "locBaku";
        updateAdvisorAlertStatus(currentStateKey);
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

    // Fast configuration setup ensuring async timing safety bounds
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

    const canvas = document.getElementById('aiMapCanvas');
    const ctx = canvas.getContext('2d');
    
    canvas.width = canvas.parentElement.clientWidth || 600;
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;

    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = "rgba(51, 65, 85, 0.4)"; ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke(); }
    for (let y = 0; y < canvas.height; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke(); }

    aiData.map_vector_data.roads.forEach(r => {
        ctx.strokeStyle = "#334155"; ctx.lineWidth = 8; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(cx + r.from_x, cy - r.from_y); ctx.lineTo(cx + r.to_x, cy - r.to_y); ctx.stroke();
    });

    ctx.fillStyle = "#3b82f6"; ctx.beginPath(); ctx.arc(cx, cy, 12, 0, 2 * Math.PI); ctx.fill();
    ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2.5; ctx.stroke();
    ctx.fillStyle = "#ffffff"; ctx.font = "bold 10px system-ui"; ctx.fillText("YOU", cx - 11, cy + 3);

    const ai_hospitals = aiData.map_vector_data.hospitals;
    ai_hospitals.forEach((h, index) => {
        const localName = h[`name_${lang}`];
        const localAddress = h[`address_${lang}`];
        
        const distanceVal = Math.round((Math.sqrt(h.offset_x*h.offset_x + h.offset_y*h.offset_y) / 25) * 100) / 100;

        const card = document.createElement('div');
        card.className = 'hospital-card';
        card.innerHTML = `
            <strong>${index + 1}. ${localName}</strong><br>
            <small>${localAddress} (<b>${distanceVal}</b> ${dict.kmAway})</small><br>
            <span style="font-size:11px; color:${h.er ? 'var(--red)' : '#64748b'}; font-weight:bold;">
                ${h.er ? dict.erOpen : dict.erClosed}
            </span>
        `;
        listContainer.appendChild(card);

        const hx = cx + h.offset_x;
        const hy = cy - h.offset_y;

        ctx.strokeStyle = aiData.urgency === 'RED' ? "rgba(239, 68, 68, 0.4)" : "rgba(234, 179, 8, 0.4)";
        ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(hx, hy); ctx.stroke();

        ctx.fillStyle = h.er ? "#ef4444" : "#eab308"; ctx.beginPath(); ctx.arc(hx, hy, 9, 0, 2 * Math.PI); ctx.fill();
        ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.5; ctx.stroke();
        
        ctx.fillStyle = "#ffffff"; ctx.font = "bold 10px system-ui"; ctx.fillText(index + 1, hx - 3, hy + 3.5);

        ctx.fillStyle = "#94a3b8"; ctx.font = "11px system-ui";
        ctx.fillText(`${localName}`, hx + 14, hy + 4);
    });

    ctx.fillStyle = "rgba(15, 23, 42, 0.85)"; ctx.fillRect(10, canvas.height - 35, 410, 25);
    ctx.fillStyle = "#38bdf8"; ctx.font = "11px monospace";
    ctx.fillText(`⚡ AUTOMATIC TRACKING ONLINE | SECTOR: ${aiData.city.toUpperCase()} | LAT: ${hardwareLat.toFixed(2)} LNG: ${hardwareLng.toFixed(2)}`, 18, canvas.height - 18);
}

function renderBlankGridOnCanvas() {
    const canvas = document.getElementById('aiMapCanvas');
    if(!canvas) return;
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.parentElement.clientWidth || 600;
    ctx.fillStyle = "#0f172a"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(51, 65, 85, 0.3)"; ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke(); }
    for (let y = 0; y < canvas.height; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke(); }
    ctx.fillStyle = "#475569"; ctx.font = "12px monospace";
    ctx.fillText(`[ GPS Synced. Enter symptoms to draw dynamic AI map layers ]`, 30, canvas.height / 2);
}
