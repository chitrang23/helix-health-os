file_path = "models/orm.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

if "lifestyle_data" not in content:
    # Add JSON column for flexible, structured lifestyle metrics
    replacement = """    gender = Column(String, nullable=False)
    lifestyle_data = Column(JSON, nullable=True)  # Stores activity, sleep, diet, smoking, alcohol"""
    
    if "gender = Column(" in content:
        # Find exact line
        lines = content.splitlines()
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if "gender = Column(" in line:
                new_lines.append("    lifestyle_data = Column(JSON, nullable=True)")
        content = "\n".join(new_lines)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ Successfully added lifestyle_data column to models/orm.py!")
else:
    print("ℹ️ lifestyle_data column already present in models/orm.py.")
