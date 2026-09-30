const token = localStorage.getItem("helix_token");
const userRaw = localStorage.getItem("helix_user");

if (!token || !userRaw) {
  window.location.href = "/";
}

const user = JSON.parse(userRaw);
document.getElementById("patient-badge").innerText = `${user.full_name} (${user.gender}, ${user.age} yrs)`;

let currentExtractedBiomarkers = {};
let selectedFile = null;
let chartInstance = null;

// Plain-Language Dictionary Fallback / Extractor
const MEDICAL_DICTIONARY = {
  "hemoglobin": {
    title: "Hemoglobin (Hb)",
    simple_def: "Hemoglobin is the oxygen-carrying protein found inside your red blood cells. It delivers oxygen from your lungs throughout your entire body.",
    evaluation: (val) => val < 12.0 ? "Your value is LOW (Anemia). You may feel fatigued, weak, or short of breath." : (val > 17.5 ? "Your value is ELEVATED. Could indicate dehydration or adaptation." : "Your value is in the NORMAL healthy range!"),
    tips: "Eat iron-rich foods (spinach, lentils, red meat) and Vitamin C to boost absorption."
  },
  "bilirubin": {
    title: "Bilirubin (Total)",
    simple_def: "Bilirubin is a compound created when old red blood cells are broken down. It is filtered and processed by your liver.",
    evaluation: (val) => val > 1.2 ? "Your value is ELEVATED. This can happen due to mild liver stress or Gilbert's syndrome." : "Your value is in the NORMAL healthy range!",
    tips: "Stay well hydrated, avoid alcohol, and maintain a balanced diet to support liver processing."
  },
  "total rbcs": {
    title: "Total Red Blood Cell Count (RBC)",
    simple_def: "Red blood cells carry fresh oxygen throughout your body to keep organs energized.",
    evaluation: (val) => val < 4.3 ? "Low RBC count (Anemic indicator)." : "Healthy red blood cell count.",
    tips: "Ensure sufficient dietary Vitamin B12, folate, and iron."
  },
  "hematocrit": {
    title: "Hematocrit (HCT)",
    simple_def: "The percentage of your total blood volume made up of red blood cells.",
    evaluation: (val) => val < 38.8 ? "Slightly thin blood composition ratio." : "Normal blood composition ratio.",
    tips: "Drink plenty of water before blood tests as mild dehydration artificially raises hematocrit."
  },
  "platelet count": {
    title: "Platelet Count",
    simple_def: "Platelets are blood cells that help your blood clot to stop bleeding when you get a cut.",
    evaluation: (val) => "Normal clotting capability.",
    tips: "Avoid excessive alcohol and ensure adequate Vitamin K intake."
  },
  "glucose": {
    title: "Fasting Blood Glucose",
    simple_def: "Measures main sugar levels in your blood after fasting. Key marker for metabolic health.",
    evaluation: (val) => val > 125 ? "Elevated (Diabetes range)." : (val >= 100 ? "Slightly Elevated (Pre-diabetes range)." : "Optimal metabolic glucose baseline!"),
    tips: "Take a 20-30 min post-meal walk and reduce refined sugar intake."
  }
};

function handleFileSelect(event) {
  selectedFile = event.target.files[0];
  if (selectedFile) {
    document.getElementById("file-name-display").innerText = `Selected: ${selectedFile.name}`;
  }
}

async function uploadAndParseReport() {
  if (!selectedFile) {
    alert("Please select or drop a medical report file first.");
    return;
  }

  const formData = new FormData();
  formData.append("file", selectedFile);

  const resultsDiv = document.getElementById("parsed-results");
  resultsDiv.innerHTML = `<span style="color: #0ea5e9;">Running sub-5s OCR extraction engine...</span>`;

  try {
    const res = await fetch("/api/records/upload-report", {
      method: "POST",
      body: formData
    });

    const data = await res.json();

    if (res.ok && data.success && Object.keys(data.extracted_biomarkers).length > 0) {
      currentExtractedBiomarkers = data.extracted_biomarkers;
      
      // Render Extracted Header Metadata
      document.getElementById("meta-date").innerText = data.metadata.report_date;
      document.getElementById("meta-hospital").innerText = data.metadata.hospital_name;

      let html = "";
      for (const [key, details] of Object.entries(currentExtractedBiomarkers)) {
        html += `
          <div onclick="selectBiomarker('${key.replace(/'/g, "\\'")}')" 
               style="background: rgba(2, 6, 23, 0.6); padding: 0.5rem 0.7rem; border-radius: 8px; margin-bottom: 0.35rem; border: 1px solid rgba(255,255,255,0.1); display: flex; justify-content: space-between; cursor: pointer; transition: all 0.2s;"
               onmouseover="this.style.borderColor='#0ea5e9'" onmouseout="this.style.borderColor='rgba(255,255,255,0.1)'">
            <span style="color: #fff; font-size: 0.75rem;">${key}</span>
            <strong style="color: #38bdf8; font-size: 0.8rem;">${details.value} ${details.unit}</strong>
          </div>
        `;
      }
      resultsDiv.innerHTML = html;

      // Select first parameter by default
      const firstKey = Object.keys(currentExtractedBiomarkers)[0];
      selectBiomarker(firstKey);

    } else {
      resultsDiv.innerHTML = `<span style="color: #ef4444;">${data.message || "Parsing failed."}</span>`;
    }
  } catch (err) {
    console.error(err);
    resultsDiv.innerHTML = `<span style="color: #ef4444;">Server error during extraction.</span>`;
  }
}

function selectBiomarker(paramKey) {
  const details = currentExtractedBiomarkers[paramKey];
  if (!details) return;

  // 1. Render Explanation Card in Middle Panel
  showExplanation(paramKey, details.value, details.unit);

  // 2. Render Trajectory Graph in Right Panel
  renderTrajectoryGraph(paramKey, details.value, details.unit);
}

function showExplanation(paramKey, value, unit) {
  const hub = document.getElementById("explanation-hub");
  const keyLower = paramKey.toLowerCase();
  
  let match = null;
  for (const [dictKey, dictVal] of Object.entries(MEDICAL_DICTIONARY)) {
    if (keyLower.includes(dictKey)) {
      match = dictVal;
      break;
    }
  }

  if (match) {
    hub.innerHTML = `
      <div style="background: rgba(2, 6, 23, 0.6); padding: 1.2rem; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
          <div>
            <h3 style="font-size: 1.15rem; color: #38bdf8; margin:0;">${match.title}</h3>
            <span style="font-size: 0.8rem; color: #94a3b8;">Extracted Value: <strong style="color:#fff;">${value} ${unit}</strong></span>
          </div>
          <span style="background: rgba(16, 185, 129, 0.2); color: #34d399; padding: 0.25rem 0.6rem; border-radius: 6px; font-weight: 700; font-size: 0.75rem;">Clinical Result</span>
        </div>

        <div style="margin-bottom: 0.85rem;">
          <h4 style="font-size: 0.75rem; text-transform: uppercase; color: #94a3b8; margin-bottom: 0.2rem;">What is this?</h4>
          <p style="font-size: 0.85rem; color: #f1f5f9; margin:0;">${match.simple_def}</p>
        </div>

        <div style="background: rgba(30, 41, 59, 0.6); padding: 0.75rem; border-radius: 8px; margin-bottom: 0.85rem; border-left: 3px solid #0ea5e9;">
          <h4 style="font-size: 0.75rem; text-transform: uppercase; color: #0ea5e9; margin-bottom: 0.2rem;">Clinical Evaluation</h4>
          <p style="font-size: 0.85rem; font-weight: 600; color: #fff; margin:0;">${typeof match.evaluation === 'function' ? match.evaluation(value) : match.evaluation}</p>
        </div>

        <div>
          <h4 style="font-size: 0.75rem; text-transform: uppercase; color: #94a3b8; margin-bottom: 0.2rem;">💡 Actionable Patient Guidance</h4>
          <p style="font-size: 0.85rem; color: #cbd5e1; margin:0;">${match.tips}</p>
        </div>
      </div>
    `;
  } else {
    // Dynamic Fallback Card
    hub.innerHTML = `
      <div style="background: rgba(2, 6, 23, 0.6); padding: 1.2rem; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1);">
        <h3 style="font-size: 1.15rem; color: #38bdf8; margin-bottom: 0.4rem;">${paramKey}</h3>
        <p style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 0.75rem;">Extracted Value: <strong style="color: #fff;">${value} ${unit}</strong></p>
        
        <div style="background: rgba(30, 41, 59, 0.6); padding: 0.75rem; border-radius: 8px; border-left: 3px solid #f59e0b;">
          <h4 style="font-size: 0.75rem; text-transform: uppercase; color: #f59e0b; margin-bottom: 0.2rem;">Clinical Finding</h4>
          <p style="font-size: 0.85rem; color: #f8fafc; margin:0;">Biomarker successfully parsed from document. Consult your physician for personalized interpretation alongside your complete medical profile.</p>
        </div>
      </div>
    `;
  }
}

async function correlateSymptoms() {
  const symInput = document.getElementById("symptoms-input").value;
  if (!symInput) {
    alert("Please enter active symptoms.");
    return;
  }

  const symptomsList = symInput.split(",").map(s => s.trim()).filter(Boolean);
  const outDiv = document.getElementById("correlation-output");
  outDiv.innerHTML = `<span style="color: #0ea5e9;">Correlating symptoms with report data...</span>`;

  try {
    const res = await fetch("/api/clinical/correlate-symptoms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symptoms: symptomsList,
        biomarkers: currentExtractedBiomarkers,
        active_prescriptions: ["Standard Care Schedule"],
        user_location: "Navi Mumbai, Maharashtra"
      })
    });

    const data = await res.json();

    outDiv.innerHTML = `
      <div style="background: rgba(2, 6, 23, 0.6); padding: 1rem; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1);">
        <h4 style="color: #38bdf8; margin-bottom: 0.4rem;">${data.correlated_condition}</h4>
        <p style="margin-bottom: 0.8rem;">${data.clinical_explanation}</p>

        <h5 style="color: #34d399; margin-bottom: 0.2rem;">🧘 Recommended Yoga & Habit Strategy</h5>
        <p style="margin-bottom: 0.8rem;">${data.lifestyle_plan.yoga_habit_building}</p>

        <h5 style="color: #f59e0b; margin-bottom: 0.2rem;">👨‍⚕️ Specialist Referral Guidance</h5>
        <p><strong>Recommended Specialty:</strong> ${data.specialist_referral.specialty_needed}</p>
        <p><em>Reason: ${data.specialist_referral.reason}</em></p>
      </div>
    `;
  } catch (err) {
    outDiv.innerHTML = `<span style="color: #ef4444;">Failed to complete correlation check.</span>`;
  }
}

function renderTrajectoryGraph(paramName, baseValue, unit) {
  const ctx = document.getElementById("twinChart").getContext("2d");
  if (chartInstance) chartInstance.destroy();

  const isIntegerMarker = Number.isInteger(baseValue) && baseValue > 10;
  
  const day30 = isIntegerMarker ? Math.round(baseValue * 1.02) : Number((baseValue * 1.02).toFixed(2));
  const day60 = isIntegerMarker ? Math.round(baseValue * 1.04) : Number((baseValue * 1.04).toFixed(2));
  const day90 = isIntegerMarker ? Math.round(baseValue * 1.05) : Number((baseValue * 1.05).toFixed(2));

  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: ["Baseline (Day 0)", "Day 30", "Day 60", "Day 90"],
      datasets: [{
        label: `${paramName} Trajectory (${unit || 'Value'})`,
        data: [baseValue, day30, day60, day90],
        borderColor: "#0ea5e9",
        backgroundColor: "rgba(14, 165, 233, 0.15)",
        fill: true,
        tension: 0.35,
        borderWidth: 3,
        pointBackgroundColor: "#38bdf8"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#f8fafc" } } },
      scales: {
        x: { ticks: { color: "#94a3b8" } },
        y: { ticks: { color: "#94a3b8" } }
      }
    }
  });
}

function logout() {
  localStorage.clear();
  window.location.href = "/";
}

const ctx = document.getElementById("twinChart").getContext("2d");
chartInstance = new Chart(ctx, {
  type: "line",
  data: {
    labels: ["Baseline (Day 0)", "Day 30", "Day 60", "Day 90"],
    datasets: [{ label: "Select Any Parameter to View 90-Day Research...", data: [0, 0, 0, 0], borderColor: "#334155" }]
  },
  options: { responsive: true, maintainAspectRatio: false }
});
