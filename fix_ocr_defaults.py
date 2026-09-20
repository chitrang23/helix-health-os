file_path = "services/ocr_engine.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Strip out default mock dicts that insert glucose and bp automatically
mock_default = '"glucose": 95, "bp_systolic": 120, "bp_diastolic": 80'
if mock_default in content:
    content = content.replace(mock_default, '')
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ Removed hardcoded glucose/BP defaults from services/ocr_engine.py")
else:
    print("⚠️ Standardized check: Verify services/ocr_engine.py manually.")
