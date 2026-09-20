file_path = "services/dynamic_safety_engine.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace any incorrect rule model imports with DrugRuleModel
content = content.replace("SafetyRule", "DrugRuleModel")
content = content.replace("DynamicSafetyRule", "DrugRuleModel")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Updated services/dynamic_safety_engine.py to use DrugRuleModel")
