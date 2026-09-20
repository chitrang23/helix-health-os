import os
import subprocess

print("⚙️ 1. Creating pyproject.toml to exclude root migration/setup scripts from coverage...")

pyproject_content = """[tool.coverage.run]
omit = [
    "apply_*.py",
    "fix_*.py",
    "update_*.py",
    "upgrade_*.py",
    "serve_frontend.py",
    "add_root_route.py",
    "inspect_auth_setup.py",
    "cleanup_and_refactor.py",
    "finalize_project_config.py"
]

[tool.pytest.ini_options]
addopts = "-v --cov=. --cov-report=term-missing"
"""

with open("pyproject.toml", "w", encoding="utf-8") as f:
    f.write(pyproject_content)

print("  ✅ pyproject.toml created successfully!")

print("\n🚀 2. Re-running Pytest with updated coverage rules...")
subprocess.run(["python", "-m", "pytest", "tests/"])
