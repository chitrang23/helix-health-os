file_path = "schemas/dtos.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add Pydantic schemas for Lifestyle Metadata
lifestyle_dtos = """

class LifestyleData(BaseModel):
    activity_level: str  # e.g., "sedentary", "lightly_active", "moderately_active", "very_active"
    sleep_hours_avg: float  # e.g., 7.5
    diet_type: str  # e.g., "balanced", "keto", "vegetarian", "vegan", "mediterranean"
    smoking_status: str  # e.g., "never", "former", "current"
    alcohol_consumption: str  # e.g., "none", "occasional", "moderate", "heavy"
    primary_goal: Optional[str] = "general_wellness"
"""

if "class LifestyleData" not in content:
    content += lifestyle_dtos

# Extend UserCreate and UserResponse to include mandatory/structured lifestyle fields
if "lifestyle: Optional[LifestyleData]" not in content and "lifestyle: LifestyleData" not in content:
    if "class UserCreate(" in content:
        content = content.replace("class UserCreate(BaseModel):", "class UserCreate(BaseModel):\n    lifestyle: Optional[LifestyleData] = None")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Successfully added LifestyleData schema to schemas/dtos.py!")
