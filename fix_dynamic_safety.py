import re

file_path = "services/dynamic_safety_engine.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace direct problematic import with actual models or dynamic handling
old_import = "from models.orm import DrugInteraction, Prescription"
new_import = "from models.orm import SafetyRule, User"

if old_import in content:
    content = content.replace(old_import, new_import)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ Updated imports in services/dynamic_safety_engine.py")
else:
    print("⚠️ Import string not found directly; check services/dynamic_safety_engine.py line 2.")
