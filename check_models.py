with open("models/orm.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

class_lines = [line.strip() for line in lines if line.strip().startswith("class ")]
print("Defined ORM Classes:")
for cl in class_lines:
    print(" -", cl)
