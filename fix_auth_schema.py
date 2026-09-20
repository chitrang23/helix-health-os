file_path = "schemas/dtos.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace optional/default age and gender with required fields
old_schema = """class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    age: int = 30
    gender: str = "male" """

new_schema = """class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    age: int
    gender: str"""

if "age: int = 30" in content:
    content = content.replace("age: int = 30", "age: int")
    content = content.replace('gender: str = "male"', 'gender: str')
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ Fixed UserCreate schema in schemas/dtos.py")
else:
    print("⚠️ Check schemas/dtos.py manually for age/gender defaults.")
