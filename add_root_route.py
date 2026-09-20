with open("main.py", "r", encoding="utf-8") as f:
    code = f.read()

root_handler = """
@app.get("/")
def read_root():
    return {
        "service": settings.PROJECT_NAME,
        "status": "online",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "api_prefix": "/api"
    }
"""

if "@app.get(\"/\")" not in code:
    insertion_marker = "app.add_middleware("
    idx = code.find(insertion_marker)
    # Find the end of add_middleware call
    end_idx = code.find(")", idx) + 1
    new_code = code[:end_idx] + "\n" + root_handler + code[end_idx:]
    with open("main.py", "w", encoding="utf-8") as f:
        f.write(new_code)
    print("Added root route '/' to main.py")
else:
    print("Root route already present.")
