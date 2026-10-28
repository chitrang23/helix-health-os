// public/js/dashboard.js
const token = localStorage.getItem("helix_token");
const userRaw = localStorage.getItem("helix_user");

if (!token) {
    window.location.href = "/";
}

let trendChartInstance = null;
let simulationChartInstance = null;
let activeObservationsMap = {};

let currentSelectionController = null;
let currentSelectedAnalyte = "";
const biomarkerExplanationCache = {};
let currentLanguage = "en";

window.addEventListener('DOMContentLoaded', async () => {
    // Ensure default language is English if not explicitly set
    let savedLang = localStorage.getItem("app_lang");
    if (!savedLang) {
        savedLang = "en";
        localStorage.setItem("app_lang", "en");
    }
    const langSelector = document.getElementById("globalLangSelector");
    if (langSelector) {
        langSelector.value = savedLang;
    }

    if (userRaw) {
        try {
            const user = JSON.parse(userRaw);
            const displayName = user.full_name || user.email || 'Authenticated Patient';
            const nameBadge = document.getElementById('userNameBadge');
            const metaPatient = document.getElementById('metaPatientName');
            if (nameBadge) nameBadge.innerText = displayName;
            if (metaPatient) metaPatient.innerText = displayName;
        } catch (e) {
            console.warn("User profile parse notice:", e);
        }
    }

    const cachedExtraction = localStorage.getItem("helix_active_report");
    if (cachedExtraction) {
        try {
            const parsedData = JSON.parse(cachedExtraction);
            if (parsedData.patient_name && document.getElementById('metaPatientName')) {
                document.getElementById('metaPatientName').innerText = parsedData.patient_name;
            }
            if (parsedData.hospital_name && document.getElementById('metaHospital')) {
                document.getElementById('metaHospital').innerText = parsedData.hospital_name;
            }
            if (parsedData.report_date && document.getElementById('metaDate')) {
                document.getElementById('metaDate').innerText = parsedData.report_date;
            }
            if (parsedData.extracted_biomarkers) {
                renderExtractedParameters(parsedData.extracted_biomarkers);
            }
        } catch (err) {
            console.error("Cache restoration failure:", err);
            renderEmptyTrendChart();
        }
    } else {
        renderEmptyTrendChart();
    }

    renderEmptySimulationChart();
    await loadUserAnalytes();
});

window.switchTab = function(tabId, element) {
    document.querySelectorAll('.section-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-links a').forEach(el => el.classList.remove('active'));
    
    const target = document.getElementById(tabId);
    if (target) {
        target.classList.add('active');
    }
    
    if (element) {
        element.classList.add('active');
    } else {
        document.querySelectorAll('.nav-links a').forEach(a => {
            const onclickAttr = a.getAttribute('onclick');
            if (onclickAttr && onclickAttr.includes(`'${tabId}'`)) {
                a.classList.add('active');
            }
        });
    }

    if (tabId === 'organRadar') {
        if (typeof computeAndRenderOrganRadar === 'function') {
            computeAndRenderOrganRadar();
        }
    }

    if (tabId === 'dashboard') {
        const cached = localStorage.getItem("helix_active_report");
        if (cached) {
            try {
                const parsed = JSON.parse(cached);
                if (parsed.extracted_biomarkers) {
                    renderExtractedParameters(parsed.extracted_biomarkers);
                }
            } catch (e) {
                console.error("Tab switch hydration error:", e);
            }
        }
    }
};

window.switchGlobalLanguage = function(lang) {
    currentLanguage = lang;
    localStorage.setItem("app_lang", lang);
    if (typeof window.applyOfflineLocalization === "function") {
        window.applyOfflineLocalization(lang);
    }
    window.location.reload();
};

window.logout = function() {
    localStorage.removeItem("helix_token");
    localStorage.removeItem("helix_user");
    localStorage.removeItem("helix_active_report");
    window.location.href = "/";
};

async function loadUserAnalytes() {
    const markerSelect = document.getElementById("pred-marker");
    if (!markerSelect) return;

    try {
        const res = await fetch("/api/metrics/available-analytes", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();

        if (res.ok && data.analytes && data.analytes.length > 0) {
            markerSelect.innerHTML = data.analytes.map(a => 
                `<option value="${a.test_name}">${a.test_name} (${a.unit || ''})</option>`
            ).join("");
            await handleTwinMarkerChange(data.analytes[0].test_name);
        } else {
            const activeKeys = Object.keys(activeObservationsMap);
            if (activeKeys.length > 0) {
                markerSelect.innerHTML = activeKeys.map(k => 
                    `<option value="${k}">${k} (${activeObservationsMap[k].unit || ''})</option>`
                ).join("");
                await handleTwinMarkerChange(activeKeys[0]);
            } else {
                markerSelect.innerHTML = `<option value="" disabled selected>Upload diagnostic report to begin</option>`;
            }
        }
    } catch (e) {
        markerSelect.innerHTML = `<option value="" disabled selected>Synchronizing clinical biomarkers...</option>`;
    }
}

async function handleTwinMarkerChange(analyteName) {
    if (!analyteName) return;
    const baseInput = document.getElementById("pred-baseline");

    try {
        const res = await fetch(`/api/metrics/history?test_name=${encodeURIComponent(analyteName)}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();

        if (res.ok && data.history && data.history.length > 0) {
            const latest = data.history[data.history.length - 1];
            if (baseInput) baseInput.value = latest.value;
            renderSimulationChart(analyteName, parseFloat(latest.value) || 0, parseFloat(latest.value) || 0);
        } else if (activeObservationsMap[analyteName]) {
            const raw = activeObservationsMap[analyteName].value;
            const parsed = parseFloat(String(raw).replace(/[^\d\.]/g, '')) || 0;
            if (baseInput) baseInput.value = parsed;
            renderSimulationChart(analyteName, parsed, parsed);
        }
    } catch (e) {
        console.error("Twin baseline synchronization error:", e);
    }
}

window.handleReportUpload = async function(e) {
    if (e && typeof e.preventDefault === "function") {
        e.preventDefault();
        e.stopPropagation();
    }
    const fileInput = document.getElementById('reportFile');
    const statusDiv = document.getElementById('uploadStatus');
    
    if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        if (statusDiv) statusDiv.innerHTML = `<span style="color: var(--warning);">⚠️ Please select a report file first.</span>`;
        return false;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    if (statusDiv) {
        statusDiv.innerHTML = `<span style="color: var(--primary);">⏳ Ingesting multi-page report and running clinical validation...</span>`;
    }

    try {
        let response = await fetch('/api/records/upload-report', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });

        if (response.status === 404) {
            response = await fetch('/api/clinical/upload-report', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
        }

        const result = await response.json();
        if (response.ok && result.success) {
            const cacheNotice = result.cached ? " (Verified Index)" : "";
            if (statusDiv) {
                statusDiv.innerHTML = `<span style="color: var(--accent);">✅ ${result.message}${cacheNotice}</span>`;
            }
            
            const metaPat = document.getElementById('metaPatientName');
            const metaHosp = document.getElementById('metaHospital');
            const metaDt = document.getElementById('metaDate');

            if (metaPat) metaPat.innerText = result.patient_name || 'Authenticated Patient';
            if (metaHosp) metaHosp.innerText = result.hospital_name || 'Diagnostic Laboratory';
            if (metaDt) metaDt.innerText = result.report_date || 'Encounter Series Verified';

            const biomarkers = result.extracted_biomarkers || {};

            localStorage.setItem("helix_active_report", JSON.stringify({
                patient_name: result.patient_name,
                hospital_name: result.hospital_name,
                report_date: result.report_date,
                extracted_biomarkers: biomarkers
            }));

            renderExtractedParameters(biomarkers);
            await loadUserAnalytes();
        } else {
            if (statusDiv) {
                statusDiv.innerHTML = `<span style="color: var(--danger);">⚠️ ${result.detail || result.message || 'Verification halted.'}</span>`;
            }
        }
    } catch (err) {
        console.error("Upload error:", err);
        if (statusDiv) {
            statusDiv.innerHTML = `<span style="color: var(--danger);">❌ Ingestion connection failed. Verify server state.</span>`;
        }
    }
    return false;
};

function renderExtractedParameters(biomarkers) {
    const container = document.getElementById('paramListContainer');
    if (!container) return;
    container.innerHTML = '';
    activeObservationsMap = biomarkers || {};

    const keys = Object.keys(activeObservationsMap);
    if (keys.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem; padding: 12px;">No parameters parsed from document.</p>';
        return;
    }

    keys.forEach((key, index) => {
        const item = activeObservationsMap[key];
        const card = document.createElement('div');
        
        let flagBorderColor = 'var(--accent)';
        let badgeColor = 'var(--accent)';
        const cleanFlag = (item.flag || 'NORMAL').toUpperCase();

        if (cleanFlag.includes('HIGH') || cleanFlag === 'H') {
            flagBorderColor = 'var(--danger)';
            badgeColor = 'var(--danger)';
        } else if (cleanFlag.includes('LOW') || cleanFlag === 'L') {
            flagBorderColor = 'var(--warning)';
            badgeColor = 'var(--warning)';
        }

        card.className = "param-card" + (index === 0 ? " active-card" : "");
        card.setAttribute('data-analyte', key);
        card.style.borderLeft = `4px solid ${flagBorderColor}`;
        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <h4 style="margin: 0; font-size: 0.92rem; font-weight: 600; color: #f8fafc;">${key}</h4>
                <span style="font-size: 0.72rem; font-weight: 700; color: ${badgeColor}; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.04);">
                    ${cleanFlag}
                </span>
            </div>
            <div class="val" style="margin-top: 6px; font-size: 1.25rem; font-weight: 700;">
                ${item.value} <span style="font-size: 0.8rem; font-weight: normal; color: var(--text-muted);">${item.unit || ''}</span>
            </div>
            <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">
                Ref: ${item.reference_range || 'Standard'}
            </div>
        `;

        card.onclick = () => {
            document.querySelectorAll('.param-card').forEach(c => c.classList.remove('active-card'));
            card.classList.add('active-card');
            selectBiomarker(key, item.value, item.unit, item.reference_range);
        };
        container.appendChild(card);
    });

    const firstKey = keys[0];
    selectBiomarker(firstKey, activeObservationsMap[firstKey].value, activeObservationsMap[firstKey].unit, activeObservationsMap[firstKey].reference_range);
}

function parseReferenceLimits(refStr) {
    if (!refStr) return { min: null, max: null };
    const rangeMatch = String(refStr).match(/(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)/i);
    if (rangeMatch) {
        return { min: parseFloat(rangeMatch[1]), max: parseFloat(rangeMatch[2]) };
    }
    const lessMatch = String(refStr).match(/<\s*(\d+(?:\.\d+)?)/);
    if (lessMatch) {
        return { min: 0, max: parseFloat(lessMatch[1]) };
    }
    const greaterMatch = String(refStr).match(/>\s*(\d+(?:\.\d+)?)/);
    if (greaterMatch) {
        return { min: parseFloat(greaterMatch[1]), max: null };
    }
    return { min: null, max: null };
}

async function selectBiomarker(biomarkerName, value, unit, refRange) {
    currentSelectedAnalyte = biomarkerName;

    if (currentSelectionController) {
        currentSelectionController.abort();
    }
    currentSelectionController = new AbortController();
    const signal = currentSelectionController.signal;

    const titleEl = document.getElementById('selectedTitle');
    const expEl = document.getElementById('selectedExplanation');
    if (!titleEl || !expEl) return;

    titleEl.innerText = biomarkerName;

    if (biomarkerExplanationCache[biomarkerName]) {
        renderExplanationHTML(expEl, biomarkerName, value, unit, refRange, biomarkerExplanationCache[biomarkerName]);
    } else {
        expEl.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px; color: var(--primary); padding: 6px 0;">
                <span class="spinner-border spinner-border-sm" role="status"></span>
                <span>Synthesizing biomarker intelligence...</span>
            </div>
        `;
    }

    let histDates = [];
    let histValues = [];

    try {
        const fetchTasks = [
            fetch(`/api/metrics/history?test_name=${encodeURIComponent(biomarkerName)}`, {
                headers: { 'Authorization': `Bearer ${token}` },
                signal: signal
            })
        ];

        if (!biomarkerExplanationCache[biomarkerName]) {
            fetchTasks.push(
                fetch('/api/clinical/explain', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        biomarker: biomarkerName,
                        value: String(value),
                        unit: unit || '',
                        printed_reference_range: refRange || ''
                    }),
                    signal: signal
                })
            );
        }

        const responses = await Promise.all(fetchTasks);
        const histRes = responses[0];
        const expRes = responses.length > 1 ? responses[1] : null;

        if (currentSelectedAnalyte !== biomarkerName) return;

        if (expRes && expRes.ok) {
            const expData = await expRes.json();
            if (expData.explanation) {
                biomarkerExplanationCache[biomarkerName] = expData.explanation;
            }
        }

        const activeExplanation = biomarkerExplanationCache[biomarkerName] || 
            `${biomarkerName} is a clinical biomarker evaluating physiological homeostasis. Your recorded value is ${value} ${unit || ''} relative to the diagnostic target (${refRange || 'Standard reference'}).`;

        renderExplanationHTML(expEl, biomarkerName, value, unit, refRange, activeExplanation);

        if (histRes.ok) {
            const histData = await histRes.json();
            if (histData.history && histData.history.length > 0) {
                const sortedHistory = histData.history.sort((a, b) => new Date(a.date) - new Date(b));
                histDates = sortedHistory.map(h => h.date);
                histValues = sortedHistory.map(h => parseFloat(String(h.value).replace(/[^\d\.]/g, ''))).filter(v => !isNaN(v));
            }
        }
    } catch (e) {
        if (e.name === 'AbortError') return;
        console.error("Clinical retrieval error:", e);
    }

    if (currentSelectedAnalyte !== biomarkerName) return;

    const currentNum = parseFloat(String(value).replace(/[^\d\.]/g, ''));
    if (histDates.length > 0 && !isNaN(currentNum)) {
        renderTrendChart(biomarkerName, histDates, histValues, unit || '', refRange);
    } else if (!isNaN(currentNum)) {
        const encounterDate = document.getElementById('metaDate') ? document.getElementById('metaDate').innerText.split(" ")[0] : "Recorded Date";
        renderTrendChart(biomarkerName, [encounterDate], [currentNum], unit || '', refRange);
    }
}

function renderExplanationHTML(container, name, val, unit, ref, explanationText) {
    container.innerHTML = `
        <div style="font-size: 0.92rem; line-height: 1.55; color: #e2e8f0; margin-bottom: 10px;">
            ${explanationText}
        </div>
        <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.08); display: flex; justify-content: space-between; font-size: 0.82rem;">
            <span><strong style="color: var(--accent);">Quantified Result:</strong> ${val} ${unit || ''}</span>
            <span style="color: var(--text-muted);"><strong style="color: #94a3b8;">Normal Target:</strong> ${ref || 'Not stated'}</span>
        </div>
    `;
}

function renderTrendChart(biomarkerName, dates, values, unit, refRange) {
    const canvas = document.getElementById('trendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (trendChartInstance) trendChartInstance.destroy();

    const isSinglePoint = values.length === 1;
    const cleanUnit = unit ? ` (${unit})` : '';
    const ref = parseReferenceLimits(refRange);
    const datasets = [];

    datasets.push({
        label: `Patient Result${cleanUnit}`,
        data: values,
        borderColor: '#00f2fe',
        backgroundColor: 'rgba(0, 242, 254, 0.12)',
        borderWidth: 2.5,
        fill: !isSinglePoint,
        tension: 0.28,
        pointRadius: isSinglePoint ? 7 : 5,
        pointHoverRadius: 9,
        pointBackgroundColor: '#00f2fe',
        pointBorderColor: '#0f172a',
        pointBorderWidth: 2,
        order: 1
    });

    if (ref.max !== null) {
        datasets.push({
            label: `Upper Normal (${ref.max})`,
            data: dates.map(() => ref.max),
            borderColor: 'rgba(239, 68, 68, 0.55)',
            borderDash: [5, 5],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
            order: 2
        });
    }

    if (ref.min !== null) {
        datasets.push({
            label: `Lower Normal (${ref.min})`,
            data: dates.map(() => ref.min),
            borderColor: 'rgba(16, 185, 129, 0.55)',
            borderDash: [5, 5],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
            order: 3
        });
    }

    let allPoints = [...values];
    if (ref.min !== null) allPoints.push(ref.min);
    if (ref.max !== null) allPoints.push(ref.max);

    const dataMin = Math.min(...allPoints);
    const dataMax = Math.max(...allPoints);
    const margin = (dataMax - dataMin) * 0.2 || (dataMax * 0.1) || 1.0;

    trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { color: '#94a3b8', font: { size: 10, weight: '600' } }
                },
                tooltip: {
                    enabled: true,
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y} ${unit || ''}`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#94a3b8', font: { size: 10 } }
                },
                y: {
                    min: Math.max(0, parseFloat((dataMin - margin).toFixed(2))),
                    max: parseFloat((dataMax + margin).toFixed(2)),
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', font: { size: 10 } }
                }
            }
        }
    });
}

function renderEmptyTrendChart() {
    const canvas = document.getElementById('trendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (trendChartInstance) trendChartInstance.destroy();
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
}

window.run30DayTwinSimulation = async function() {
    const markerEl = document.getElementById("pred-marker");
    const baselineEl = document.getElementById("pred-baseline");
    const sleepEl = document.getElementById("lifestyle-sleep");
    const actEl = document.getElementById("lifestyle-activity");
    const dietEl = document.getElementById("lifestyle-diet");
    const output = document.getElementById("prediction-output");

    if (!markerEl || !baselineEl || !output) return;

    const marker = markerEl.value;
    const baseline = parseFloat(baselineEl.value);
    const sleep = sleepEl ? sleepEl.value : "7";
    const activity = actEl ? actEl.value : "Moderate";
    const diet = dietEl ? dietEl.value : "Balanced";

    if (!marker || isNaN(baseline)) {
        alert("Please select a verified biomarker with baseline telemetry.");
        return;
    }

    output.innerHTML = `<span style="color: var(--primary);">⏳ Computing non-linear projection model...</span>`;

    try {
        const res = await fetch("/api/clinical/predict-30-days", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ marker, baseline, sleep, activity, diet })
        });
        const data = await res.json();

        if (res.ok) {
            let bulletsHtml = "";
            if (Array.isArray(data.explanation_bullets)) {
                bulletsHtml = `<ul style="margin-left: 18px; margin-top: 6px; margin-bottom: 8px;">` +
                    data.explanation_bullets.map(b => `<li style="margin-bottom: 4px;">${b}</li>`).join("") + `</ul>`;
            } else {
                bulletsHtml = `<p style="margin: 8px 0; line-height: 1.5;">${data.explanation || ''}</p>`;
            }

            output.innerHTML = `
                <div style="margin-bottom: 8px;">
                    <strong style="color: var(--primary);">Scenario Trajectory:</strong> 
                    <span style="color: var(--accent); font-weight:700;">${data.status}</span>
                </div>
                ${bulletsHtml}
                <div style="margin-top: 8px; font-size: 0.85rem;">
                    <strong style="color: var(--warning);">Actionable Consideration:</strong> 
                    <span style="color: var(--text-muted);">${data.recommendation}</span>
                </div>
            `;
            renderSimulationChart(marker, baseline, data.projected_day_30);
        } else {
            output.innerHTML = `<span style="color: var(--danger);">⚠️ ${data.detail || 'Simulation computation aborted.'}</span>`;
        }
    } catch (err) {
        output.innerHTML = `<span style="color: var(--danger);">❌ Connection failure to predictive engine.</span>`;
    }
}

function renderSimulationChart(marker, base, finalVal) {
    const canvas = document.getElementById("simulationChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (simulationChartInstance) simulationChartInstance.destroy();

    const d10 = Number((base + (finalVal - base) * 0.33).toFixed(2));
    const d20 = Number((base + (finalVal - base) * 0.66).toFixed(2));

    simulationChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: ["Baseline", "Day 10", "Day 20", "Day 30 (Projected)"],
            datasets: [{
                label: `${marker} Projection`,
                data: [base, d10, d20, finalVal],
                borderColor: "#00f2fe",
                backgroundColor: "rgba(0, 242, 254, 0.12)",
                fill: true,
                tension: 0.32,
                borderWidth: 2,
                pointBackgroundColor: "#00f2fe",
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8", font: { size: 10 } } },
                y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8", font: { size: 10 } } }
            }
        }
    });
}

function renderEmptySimulationChart() {
    const canvas = document.getElementById("simulationChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (simulationChartInstance) simulationChartInstance.destroy();
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
}

window.sendGeminiChat = async function() {
    const input = document.getElementById('chatInput');
    const messages = document.getElementById('chatMessages');
    if (!input || !messages) return;

    const userText = input.value.trim();
    if (!userText) return;

    messages.innerHTML += `<div style="margin-bottom: 14px; text-align: right;"><strong>You:</strong> ${userText}</div>`;
    input.value = '';

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ message: userText })
        });
        const data = await res.json();
        const reply = data.response || data.message || 'No diagnostic output provided.';
        messages.innerHTML += `<div style="margin-bottom: 14px; color: var(--primary);"><strong>Helix AI:</strong> ${reply}</div>`;
        messages.scrollTop = messages.scrollHeight;
    } catch (e) {
        messages.innerHTML += `<div style="margin-bottom: 14px; color: var(--danger);"><strong>Error:</strong> Assistant interface unreachable.</div>`;
    }
}

window.loadSoapBriefing = async function() {
    const box = document.getElementById("soapOutputBox");
    if (!box) return;

    box.innerHTML = `<span style="color: var(--primary);">⏳ Compiling source-grounded SOAP documentation...</span>`;
    try {
        const res = await fetch("/api/soap/generate", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();
        if (res.ok) {
            box.innerHTML = `
                <h4 style="color: var(--primary); margin-bottom: 12px;">📋 Clinical SOAP Summary</h4>
                <p><strong>Subjective:</strong><br>${data.subjective ? data.subjective.join("<br>") : 'None recorded'}</p><br>
                <p><strong>Objective:</strong><br>${data.objective ? data.objective.join("<br>") : 'No observation records present'}</p><br>
                <p><strong>Assessment:</strong><br>${data.assessment}</p><br>
                <strong style="color: var(--accent);">Action Plan:</strong>
                <ul style="margin-left: 20px;">${data.plan ? data.plan.map(p => `<li>${p}</li>`).join("") : ''}</ul>
            `;
        } else {
            box.innerHTML = `<span style="color: var(--warning);">⚠️ Unable to generate briefing: ${data.detail || 'Insufficient documentation.'}</span>`;
        }
    } catch (e) {
        box.innerHTML = `<span style="color: var(--danger);">SOAP generator service failure.</span>`;
    }
}

window.runDashboardDrugSafetyAudit = async function() {
    const rxInput = document.getElementById("rx-input");
    const suppInput = document.getElementById("supp-input");
    const output = document.getElementById("safety-output");
    if (!rxInput || !output) return;

    const medications = rxInput.value.split(",").map(s => s.trim()).filter(Boolean);
    const supplements = suppInput ? suppInput.value.split(",").map(s => s.trim()).filter(Boolean) : [];

    output.innerHTML = `<span style="color: var(--primary);">⏳ Cross-referencing adverse pharmacological interactions...</span>`;

    try {
        const res = await fetch("/api/drug-safety/audit", {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ medications, supplements })
        });
        const data = await res.json();

        if (!data.interactions_found) {
            output.innerHTML = `<div style="color: var(--accent); font-weight: 700; padding: 12px; background: rgba(16,185,129,0.1); border-radius: 8px; border: 1px solid var(--accent);">✓ ${data.message || 'No contraindications identified.'}</div>`;
        } else {
            let html = `<div style="color: var(--danger); font-weight: 700; margin-bottom: 12px; padding: 8px; background: rgba(239,68,68,0.1); border-radius: 8px;">⚠️ Interaction Risk: ${data.severity}</div>`;
            for (const item of data.findings) {
                html += `<div style="background: rgba(15,23,42,0.9); border: 1px solid rgba(239,68,68,0.3); padding: 14px; border-radius: 10px; margin-bottom: 10px;">
                    <strong style="color: #fff;">${item.combination}</strong><br>
                    <span style="color: var(--text-muted);">${item.clinical_effect}</span><br>
                    <em style="color: var(--primary); display: block; margin-top: 6px;">Protocol: ${item.recommendation}</em>
                </div>`;
            }
            output.innerHTML = html;
        }
    } catch (err) {
        output.innerHTML = `<span style="color: var(--danger);">Pharmacological safety audit connection failed.</span>`;
    }
}

window.searchSpecialists = async function() {
    const specRes = document.getElementById('specialistResults');
    const regionEl = document.getElementById('specRegion');
    const catEl = document.getElementById('specCategory');
    if (!specRes || !regionEl || !catEl) return;

    const region = regionEl.value;
    const category = catEl.value;
    specRes.innerHTML = `<span style="color: var(--primary);">⏳ Searching regional registry...</span>`;

    try {
        const res = await fetch(`/api/soap/recommend-doctor?specialty=${encodeURIComponent(category)}&location=${encodeURIComponent(region)}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();
        const recommendations = data.directory_results?.recommendations || [];

        if (res.ok && recommendations.length > 0) {
            let html = `<h4 style="color: var(--primary); margin-bottom: 12px;">Verified Practitioners in ${region.toUpperCase()}</h4>`;
            recommendations.forEach((doc, idx) => {
                html += `
                    <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border); padding: 14px; border-radius: 10px; margin-bottom: 10px;">
                        <strong style="color: #fff;">${idx + 1}. ${doc.name}</strong><br>
                        <span style="color: var(--text-muted); font-size: 0.85rem;">🏥 ${doc.hospital}</span><br>
                        <span style="color: var(--accent); font-size: 0.8rem;">📍 ${doc.contact}</span>
                    </div>
                `;
            });
            specRes.innerHTML = html;
        } else {
            specRes.innerHTML = `<p style="color: var(--warning);">${data.directory_results?.message || 'No verified practitioners found for selected criteria.'}</p>`;
        }
    } catch (e) {
        specRes.innerHTML = `<p style="color: var(--danger);">Directory service unavailable.</p>`;
    }
}

window.submitStressCheckIn = async function() {
    const rangeEl = document.getElementById('stressRange');
    const triggersEl = document.getElementById('stressTriggersInput');
    const output = document.getElementById('stressResultsOutput');
    if (!rangeEl || !output) return;

    const score = parseInt(rangeEl.value, 10);
    const triggers = triggersEl ? triggersEl.value : "";

    output.innerHTML = `<span style="color: var(--primary);">⏳ Recording biometric assessment...</span>`;

    try {
        const res = await fetch("/api/stress/check-in", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ stress_score: score, triggers: triggers })
        });
        const data = await res.json();
        if (res.ok) {
            output.innerHTML = `
                <strong style="color: var(--primary);">Logged Score:</strong> ${data.stress_score}/10<br><br>
                <strong>Autonomic Regulation Protocol:</strong><br>${data.personalized_recommendation}
                ${data.urgent_support_guidance ? `<div style="margin-top:10px; color:var(--danger);">${data.urgent_support_guidance}</div>` : ''}
            `;
        }
    } catch (e) {
        output.innerHTML = `<span style="color: var(--danger);">Failed to log somatic entry.</span>`;
    }
}

let breathInterval = null;
window.toggleBreathingExercise = function() {
    const btn = document.getElementById('breathBtn');
    const circle = document.getElementById('breathCircle');
    const inst = document.getElementById('breathInstruction');
    if (!btn || !circle || !inst) return;

    if (breathInterval) {
        clearInterval(breathInterval);
        breathInterval = null;
        btn.innerText = "Start Exercise";
        circle.innerText = "Ready";
        circle.className = "breathing-circle";
        inst.innerText = "Engage parasympathetic nerve stimulation to stabilize acute sympathetic arousal.";
        return;
    }

    btn.innerText = "Stop Exercise";
    let phase = 0;
    const runCycle = () => {
        if (phase === 0) {
            circle.innerText = "Inhale (4s)";
            circle.className = "breathing-circle inhale";
            inst.innerText = "Inhale deeply through your nose...";
            phase = 1;
        } else if (phase === 1) {
            circle.innerText = "Hold (4s)";
            inst.innerText = "Hold breath gently...";
            phase = 2;
        } else if (phase === 2) {
            circle.innerText = "Exhale (4s)";
            circle.className = "breathing-circle exhale";
            inst.innerText = "Slowly exhale completely through your mouth...";
            phase = 3;
        } else {
            circle.innerText = "Hold (4s)";
            inst.innerText = "Hold lungs empty...";
            phase = 0;
        }
    };
    runCycle();
    breathInterval = setInterval(runCycle, 4000);
}

window.runPathologySynthesis = async function() {
    const fileInput = document.getElementById('scanFile');
    const focusSelect = document.getElementById('scanFocus');
    const resArea = document.getElementById('synthResult');
    const resText = document.getElementById('synthText');
    if (!fileInput || !resArea || !resText) return;

    if (!fileInput.files[0]) {
        alert("Please upload a scan file first.");
        return;
    }

    resArea.style.display = 'block';
    resText.innerHTML = "⏳ Uploading scan and analyzing visual pathology...";

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('clinical_focus', focusSelect ? focusSelect.value : "general");

    try {
        const response = await fetch('/api/pathology/synthesize', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });
        const result = await response.json();
        if (response.ok) {
            resText.innerHTML = `<strong style="color: var(--accent);">Analysis Complete:</strong><br>${result.synthesis_report}`;
        } else {
            resText.innerHTML = `<span style="color: var(--danger);">⚠️ ${result.detail || 'Synthesis error'}</span>`;
        }
    } catch (err) {
        resText.innerHTML = `<span style="color: var(--danger);">❌ Multi-modal analysis connection failed.</span>`;
    }
}

window.handleReportUpload = async function(e) {
    if (e && typeof e.preventDefault === "function") {
        e.preventDefault();
        e.stopPropagation();
    }

    const fileInput = document.getElementById("reportFile");
    const statusDiv = document.getElementById("uploadStatus");

    if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        if (statusDiv) {
            statusDiv.innerHTML = `<span style="color: var(--warning);">⚠️ Please choose a report file first.</span>`;
        }
        return false;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    if (statusDiv) {
        statusDiv.innerHTML = `<span style="color: var(--primary);">⏳ Ingesting multi-page report and running clinical validation...</span>`;
    }

    try {
        let response = await fetch("/api/records/upload-report", {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` },
            body: formData
        });

        if (response.status === 404) {
            response = await fetch("/api/clinical/upload-report", {
                method: "POST",
                headers: { "Authorization": `Bearer ${token}` },
                body: formData
            });
        }

        const result = await response.json();
        if (response.ok && result.success) {
            const cacheNotice = result.cached ? " (Instant Verified Index)" : "";
            if (statusDiv) {
                statusDiv.innerHTML = `<span style="color: var(--accent);">✅ ${result.message}${cacheNotice}</span>`;
            }

            const metaPat = document.getElementById("metaPatientName");
            const metaHosp = document.getElementById("metaHospital");
            const metaDt = document.getElementById("metaDate");

            if (metaPat) metaPat.innerText = result.patient_name || 'Authenticated Patient';
            if (metaHosp) metaHosp.innerText = result.hospital_name || 'Diagnostic Laboratory';
            if (metaDt) metaDt.innerText = result.report_date || 'Verified Encounter';

            const biomarkers = result.extracted_biomarkers || {};

            localStorage.setItem("helix_active_report", JSON.stringify({
                patient_name: result.patient_name,
                hospital_name: result.hospital_name,
                report_date: result.report_date,
                extracted_biomarkers: biomarkers
            }));

            renderExtractedParameters(biomarkers);
            await loadUserAnalytes();
        } else {
            if (statusDiv) {
                statusDiv.innerHTML = `<span style="color: var(--danger);">⚠️ ${result.detail || result.message || "Verification halted."}</span>`;
            }
        }
    } catch (err) {
        console.error("Upload error:", err);
        if (statusDiv) {
            statusDiv.innerHTML = `<span style="color: var(--danger);">❌ Ingestion connection failed. Verify server state.</span>`;
        }
    }
    return false;
};

// -------------------------------------------------------------
// MULTI-ORGAN HOMEOSTATIC RADAR & ZERO-API CLINICAL INDICES
// -------------------------------------------------------------

let organRadarChartInstance = null;

const _existingSwitchTab = window.switchTab;
if (typeof window.switchTab === "function") {
    window.switchTab = function(tabId, element) {
        if (_existingSwitchTab) _existingSwitchTab(tabId, element);
        if (tabId === 'organRadar') {
            computeAndRenderOrganRadar();
        }
    };
}

function computeAndRenderOrganRadar() {
    let map = typeof activeObservationsMap !== "undefined" ? activeObservationsMap : {};
    if (Object.keys(map).length === 0) {
        const cached = localStorage.getItem("helix_active_report");
        if (cached) {
            try { map = JSON.parse(cached).extracted_biomarkers || {}; } catch (e) {}
        }
    }

    const findBm = (keywords) => {
        for (const [k, obj] of Object.entries(map)) {
            if (keywords.some(kw => k.toLowerCase().includes(kw))) {
                const val = parseFloat(String(obj.value).replace(/[^\d\.\-]/g, ""));
                if (!isNaN(val)) return { name: k, value: val, unit: obj.unit || "", ref: obj.reference_range || "" };
            }
        }
        return null;
    };

    const hb = findBm(["hemoglobin", "haemoglobin", "hb"]);
    const rbc = findBm(["total rbc", "rbc"]);
    const wbc = findBm(["wbc", "leukocyte", "tlc"]);
    const neut = findBm(["neutrophil"]);
    const lymph = findBm(["lymphocyte"]);
    const sgpt = findBm(["sgpt", "alt"]);
    const creat = findBm(["creatinine"]);
    const gluc = findBm(['glucose', 'sugar', 'hba1c']);

    const hema = hb ? (hb.value >= 12 && hb.value <= 17 ? 92 : 65) : 78;
    const imm = wbc ? (wbc.value >= 4000 && wbc.value <= 11000 ? 90 : 68) : 82;
    const hep = sgpt ? (sgpt.value <= 45 ? 94 : 70) : 85;
    const ren = creat ? (creat.value <= 1.2 ? 95 : 60) : 88;
    const met = gluc ? (gluc.value <= 100 ? 92 : 72) : 80;

    const overall = Math.round((hema + imm + hep + ren + met) / 5);
    const badge = document.getElementById("allostaticScoreBadge");
    if (badge) badge.innerText = `Homeostatic Index: ${overall}/100`;

    const canvas = document.getElementById("organRadarChart");
    if (canvas) {
        const ctx = canvas.getContext("2d");
        if (organRadarChartInstance) organRadarChartInstance.destroy();
        organRadarChartInstance = new Chart(ctx, {
            type: "radar",
            data: {
                labels: ['Hematopoietic & O₂', 'Immunological', 'Hepatic Function', 'Renal Clearance', 'Metabolic Control'],
                datasets: [{
                    label: 'Patient Homeostatic Resilience',
                    data: [hema, imm, hep, ren, met],
                    backgroundColor: 'rgba(0, 242, 254, 0.18)',
                    borderColor: '#00f2fe',
                    borderWidth: 2.5,
                    pointBackgroundColor: '#00f2fe'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        min: 20, max: 100,
                        grid: { color: 'rgba(255, 255, 255, 0.08)' },
                        pointLabels: { color: '#f8fafc', font: { size: 11, weight: '600' } },
                        ticks: { display: false }
                    }
                },
                plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8' } } }
            }
        });
    }

    const derivedList = [];
    if (findBm(["mcv"]) && rbc && rbc.value > 0) {
        const mcvVal = findBm(["mcv"]).value;
        const mentzer = (mcvVal / rbc.value).toFixed(1);
        derivedList.push({
            title: "Mentzer Erythrocyte Index (MCV ÷ RBC)",
            val: mentzer,
            note: mentzer > 13 ? "Suggestive of Iron-Deficiency Kinetics (>13.0)" : "Normal / Thalassemia Screen (<13.0)",
            color: mentzer > 13 ? "var(--warning)" : "var(--accent)"
        });
    }
    if (neut && lymph && lymph.value > 0) {
        const nlr = (neut.value / lymph.value).toFixed(2);
        derivedList.push({
            title: "Neutrophil-to-Lymphocyte Ratio (NLR)",
            val: nlr,
            note: nlr > 3.0 ? "Elevated Systemic Stress (>3.0)" : "Balanced Inflammatory Load (1.0–3.0)",
            color: nlr > 3.0 ? "var(--danger)" : "var(--accent)"
        });
    }

    const box = document.getElementById("derivedIndicesContainer");
    if (box) {
        box.innerHTML = derivedList.length ? derivedList.map(item => `
            <div style="background: rgba(255,255,255,0.03); border-left: 4px solid ${item.color}; padding: 12px; border-radius: 10px; border: 1px solid var(--border);">
                <div style="display: flex; justify-content: space-between;">
                    <strong style="font-size: 0.84rem; color: #fff;">${item.title}</strong>
                    <span style="font-family: monospace; font-weight: 800; color: ${item.color};">${item.val}</span>
                </div>
                <div style="font-size: 0.78rem; color: #cbd5e1; margin-top: 4px;">${item.note}</div>
            </div>
        `).join("") : `<div style="color: var(--text-muted); font-size: 0.85rem;">Upload a report to compute derived indices.</div>`;
    }
}

window.downloadFHIRBundle = function() {
    const map = typeof activeObservationsMap !== "undefined" ? activeObservationsMap : {};
    let entries = [];
    
    if (Object.keys(map).length > 0) {
        entries = Object.entries(map).map(([name, obj], idx) => ({
            resource: {
                resourceType: "Observation",
                id: `obs-${idx + 1}`,
                status: "final",
                code: { text: name },
                valueQuantity: { value: parseFloat(obj.value) || 0, unit: obj.unit || "" }
            }
        }));
    } else {
        const cached = localStorage.getItem("helix_active_report");
        if (cached) {
            try {
                const parsed = JSON.parse(cached);
                const biomarkers = parsed.extracted_biomarkers || {};
                entries = Object.entries(biomarkers).map(([name, obj], idx) => ({
                    resource: {
                        resourceType: "Observation",
                        id: `obs-${idx + 1}`,
                        status: "final",
                        code: { text: name },
                        valueQuantity: { value: parseFloat(obj.value) || 0, unit: obj.unit || "" }
                    }
                }));
            } catch (e) {}
        }
    }

    const bundle = { resourceType: "Bundle", type: "collection", entry: entries };
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "helix_hl7_fhir_bundle.json";
    a.click();
    URL.revokeObjectURL(url);
};

// -------------------------------------------------------------
// REAL-WORLD STRESS MANAGEMENT & NEURO-SOMATIC REGULATION
// -------------------------------------------------------------

let sighInterval = null;

window.togglePhysiologicalSigh = function() {
    const btn = document.getElementById('sighBtn');
    const circle = document.getElementById('sighCircle');
    const inst = document.getElementById('sighInstruction');
    if (!btn || !circle || !inst) return;

    if (sighInterval) {
        clearInterval(sighInterval);
        sighInterval = null;
        btn.innerText = "Start 60-Second Protocol";
        circle.innerText = "Ready";
        circle.style.transform = "scale(1)";
        inst.innerText = "Click start for a 60-second real-time nervous system reset.";
        return;
    }

    btn.innerText = "Stop Protocol";
    let step = 0;

    const runSighCycle = () => {
        circle.innerText = "Deep Inhale (1)";
        circle.style.transform = "scale(1.25)";
        inst.innerText = "Take a deep, full breath in through your nose...";
        
        setTimeout(() => {
            if (!sighInterval) return;
            circle.innerText = "Top-off Inhale (2)";
            circle.style.transform = "scale(1.35)";
            inst.innerText = "Immediately take a quick second puff of air to fully expand lungs!";
        }, 1500);

        setTimeout(() => {
            if (!sighInterval) return;
            circle.innerText = "Slow Exhale";
            circle.style.transform = "scale(0.85)";
            inst.innerText = "Now, slowly and completely exhale through your mouth until empty...";
        }, 3000);
    };

    runSighCycle();
    sighInterval = setInterval(runSighCycle, 7000);
};

window.submitClinicalStressLog = async function() {
    const rangeEl = document.getElementById('stressRange');
    const triggersEl = document.getElementById('stressTriggersInput');
    const somaticEl = document.getElementById('somaticManifestation');
    const output = document.getElementById('stressResultsOutput');
    if (!rangeEl || !output) return;

    const score = parseInt(rangeEl.value, 10);
    const triggers = triggersEl ? triggersEl.value.trim() : "General";
    const somatic = somaticEl ? somaticEl.value : "Tension";

    output.innerHTML = `<span style="color: var(--primary);">⏳ Analyzing acute autonomic load and generating recovery directives...</span>`;

    try {
        const res = await fetch("/api/stress/check-in", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ 
                stress_score: score, 
                triggers: `${triggers} [Manifestation: ${somatic}]` 
            })
        });
        const data = await res.json();
        
        if (res.ok) {
            let clinicalAction = "Maintain hydration and engage in 3 cycles of the physiological sigh.";
            if (score >= 7) {
                clinicalAction = "High autonomic arousal detected. Disengage from screen tasks immediately, practice 2 minutes of double-inhale box breathing, and re-evaluate physical posture.";
            } else if (score >= 4) {
                clinicalAction = "Moderate sympathetic load. Integrate a 10-minute post-meal walk or acoustic pacing to reduce cortisol drift.";
            }

            output.innerHTML = `
                <div style="margin-bottom: 10px;">
                    <strong style="color: var(--primary);">Logged Distress Load:</strong> 
                    <span style="color: var(--text-main); font-weight:700;">${data.stress_score}/10</span> 
                    <span style="color: var(--text-muted); font-size: 0.8rem;">(Trigger: ${triggers})</span>
                </div>
                <div style="background: rgba(0,242,254,0.04); border: 1px solid rgba(0,242,254,0.15); padding: 14px; border-radius: 10px; margin-bottom: 10px;">
                    <strong style="color: var(--accent);">Targeted Behavioral Pacing:</strong><br>
                    <p style="margin-top: 4px; color: #f8fafc; font-size: 0.88rem;">${clinicalAction}</p>
                </div>
                <div style="font-size: 0.82rem; color: var(--text-muted);">
                    <em>Clinical Note: ${data.personalized_recommendation || 'Autonomic regulation protocol active.'}</em>
                </div>
                ${data.urgent_support_guidance ? `<div style="margin-top:10px; color:var(--danger); font-weight:600;">${data.urgent_support_guidance}</div>` : ''}
            `;
        } else {
            output.innerHTML = `<span style="color: var(--danger);">⚠️ Failed to record stress check-in.</span>`;
        }
    } catch (e) {
        output.innerHTML = `<span style="color: var(--danger);">❌ Connection failure to stress service.</span>`;
    }
};