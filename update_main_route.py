# -*- coding: utf-8 -*-
with open("main.py", "r", encoding="utf-8") as f:
    code = f.read()

# Replace the helix_portal route to read cleanly from templates/portal.html
old_portal_needle = 'def helix_portal():'
idx = code.find(old_portal_needle)
if idx != -1:
    # Truncate anything from @app.get("/") onwards
    route_idx = code.rfind('@app.get("/",', 0, idx)
    base_code = code[:route_idx]
else:
    base_code = code

new_route = '''@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def helix_portal():
    with open("templates/portal.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
'''

final_code = base_code.strip() + "\n\n" + new_route

with open("main.py", "w", encoding="utf-8") as f:
    f.write(final_code)

print("main.py updated to serve templates/portal.html")
