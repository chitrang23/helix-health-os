import os

keywords = ["glucose", "bp_systolic", "bp_diastolic"]
target_dirs = ["services", "routes", "models"]

print("🔍 Searching for hardcoded fallback biomarkers...")
for t_dir in target_dirs:
    if not os.path.exists(t_dir):
        continue
    for root, _, files in os.walk(t_dir):
        for file in files:
            if file.endswith(".py"):
                p = os.path.join(root, file)
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                for line_idx, line in enumerate(lines):
                    if any(kw in line.lower() for kw in keywords) and ("=" in line or ":" in line):
                        print(f"  📍 {p}:{line_idx + 1} -> {line.strip()}")
