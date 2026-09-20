import os
import subprocess

print("🧹 1. Cleaning up temporary fix and debug scripts...")
temp_files = [
    "fix_auth_prefix.py",
    "debug_main.py",
    "fix_main_routes.py",
    "fix_idor_route.py",
    "fix_dynamic_flow_routes.py",
    "fix_sim_response.py",
    "fix_user_id.py"
]

for file in temp_files:
    if os.path.exists(file):
        os.remove(file)
        print(f"   Deleted {file}")

print("\n🔧 2. Refactoring routes/admin.py to fix Pydantic V2 ConfigDict deprecation warning...")
admin_path = os.path.join("routes", "admin.py")
if os.path.exists(admin_path):
    with open(admin_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Replace class Config with ConfigDict if needed
    if "class Config:" in content or "orm_mode = True" in content or "from_attributes = True" in content:
        content = content.replace("from pydantic import BaseModel", "from pydantic import BaseModel, ConfigDict")
        content = content.replace("class Config:\n        orm_mode = True", "model_config = ConfigDict(from_attributes=True)")
        content = content.replace("class Config:\n        from_attributes = True", "model_config = ConfigDict(from_attributes=True)")
        
        with open(admin_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("   ✅ Updated routes/admin.py to use ConfigDict!")

print("\n🚀 3. Executing Pytest with Coverage Report...")
subprocess.run(["python", "-m", "pytest", "tests/", "-v", "--cov=.", "--cov-report=term-missing"])
