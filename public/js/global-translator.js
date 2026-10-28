// Get current language preference (defaults to 'en')
// Get current language preference (defaults to 'en')
function getCurrentLang() {
    const stored = localStorage.getItem("app_lang");
    if (!stored) {
        localStorage.setItem("app_lang", "en");
        return "en";
    }
    return stored;
}

// 1. GLOBAL FETCH WRAPPER: Automatically translates ANY JSON response from your backend
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const response = await originalFetch.apply(this, args);
    const currentLang = getCurrentLang();

    // Skip translation if language is English or if it's an internal translation call itself
    if (currentLang === 'en' || args[0].includes('/api/translate/') || args[0].includes('/api/translator/')) {
        return response;
    }

    // Clone response so we can read and modify JSON safely
    try {
        const clone = response.clone();
        const data = await clone.json();

        // Send the entire JSON payload to your separate translator backend
        const transRes = await originalFetch('/api/translator/object', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                data: data,
                target_language: currentLang
            })
        });
        const transJson = await transRes.json();

        // Return a fake Response object with the translated data
        return new Response(JSON.stringify(transJson.translated_data || data), {
            status: response.status,
            statusText: response.statusText,
            headers: response.headers
        });
    } catch (e) {
        return response;
    }
};

// 2. AUTOMATIC UI TRANSLATOR: Translates static text elements on the page (buttons, headings, labels)
document.addEventListener("DOMContentLoaded", async () => {
    const currentLang = getCurrentLang();
    if (currentLang === 'en') return;

    // Select common text elements you want translated automatically
    const elementsToTranslate = document.querySelectorAll("h1, h2, h3, h4, p, label, button, a, th, td");
    const texts = Array.from(elementsToTranslate).map(el => el.innerText.trim()).filter(t => t.length > 0 && !t.startsWith("{"));

    if (texts.length === 0) return;

    try {
        const res = await originalFetch('/api/translator/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                texts: texts,
                target_language: currentLang
            })
        });
        const json = await res.json();
        const translations = json.translations || [];

        let index = 0;
        elementsToTranslate.forEach(el => {
            const text = el.innerText.trim();
            if (text.length > 0 && !text.startsWith("{") && translations[index]) {
                el.innerText = translations[index];
                index++;
            }
        });
    } catch (err) {
        console.error("UI Translation failed:", err);
    }
});