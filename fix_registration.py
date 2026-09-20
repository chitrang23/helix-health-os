file_path = "schemas/dtos.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace any optional age/gender defaults in UserCreate schema
updated = False
if "age: int = 30" in content:
    content = content.replace("age: int = 30", "age: int")
    updated = True
if 'gender: str = "male"' in content:
    content = content.replace('gender: str = "male"', 'gender: str')
    updated = True

if updated:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ Successfully made age and gender required in schemas/dtos.py")
else:
    print("ℹ️ DTO schema already enforces age and gender or uses a different structure.")
