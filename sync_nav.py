import os, glob, re

navbar_html = """    <!-- Unified Navbar -->
    <nav class="border-b border-slate-800 bg-slate-900/90 backdrop-blur px-6 py-4 flex justify-between items-center sticky top-0 z-50">
        <div class="flex items-center space-x-3">
            <div class="h-3 w-3 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_10px_#10b981]"></div>
            <span class="font-bold text-lg tracking-wider text-emerald-400">HELIX // ENTERPRISE OS</span>
        </div>
        <div class="space-x-4 text-xs font-medium text-slate-300 flex items-center">
            <a href="/dashboard.html" class="hover:text-emerald-400 transition">Dashboard</a>
            <a href="/history.html" class="hover:text-emerald-400 transition">Medical History</a>
            <a href="/safety.html" class="hover:text-emerald-400 transition">Drug Safety</a>
            <a href="/chat.html" class="hover:text-emerald-400 transition">Assistant</a>
            <a href="/prediction.html" class="hover:text-emerald-400 transition">30-Day</a>
            <a href="/stress.html" class="hover:text-emerald-400 transition">Stress & Flow</a>
            <a href="/soap.html" class="hover:text-emerald-400 transition">SOAP & Billing</a>
            <a href="/register.html" class="hover:text-emerald-400 transition">Register</a>
            <a href="/dashboard.html" class="bg-rose-600/20 text-rose-400 border border-rose-500/30 px-3 py-1 rounded-lg hover:bg-rose-600/30 transition font-bold">Sign Out</a>
        </div>
    </nav>"""

for path in glob.glob(os.path.join('public', '*.html')):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Remove any existing <nav>...</nav> blocks completely
    content = re.sub(r'<nav[\s\S]*?</nav>', '', content, flags=re.IGNORECASE)
    
    # 2. Remove any old custom <header>...</header> blocks completely
    content = re.sub(r'<header[\s\S]*?</header>', '', content, flags=re.IGNORECASE)
    
    # 3. Insert the single unified navbar right after the <body> tag
    if re.search(r'<body[^>]*>', content, re.IGNORECASE):
        content = re.sub(r'(<body[^>]*>)', r'\1\n' + navbar_html, content, count=1, flags=re.IGNORECASE)
        
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Cleaned and synchronized navbar in {os.path.basename(path)}")
