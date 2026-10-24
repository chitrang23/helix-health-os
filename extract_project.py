import os
import sys

# Directories and files to exclude from text extraction
IGNORED_DIRS = {
    '.git', '.svn', '.idea', '.vscode', '__pycache__', 'node_modules',
    'venv', '.venv', 'env', '.env', 'dist', 'build', 'target', 'bin', 'obj',
    '.next', 'out', 'coverage', '.pytest_cache'
}

IGNORED_FILES = {
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'extract_project.py',
    '.DS_Store', 'Thumbs.db'
}

# Relevant extensions for reports and architecture summaries
ALLOWED_EXTENSIONS = {
    '.py', '.java', '.c', '.cpp', '.h', '.js', '.jsx', '.ts', '.tsx',
    '.html', '.css', '.scss', '.sql', '.sh', '.bash', '.json', '.yaml',
    '.yml', '.xml', '.toml', '.md', '.txt', '.env.example', '.dockerignore',
    'Dockerfile', 'Makefile'
}

def is_text_file(filename):
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS or filename in ALLOWED_EXTENSIONS

def generate_tree(dir_path, prefix=""):
    """Generates an ASCII directory tree representation."""
    tree_str = ""
    try:
        entries = sorted(os.listdir(dir_path))
    except PermissionError:
        return prefix + "[Permission Denied]\n"

    entries = [e for e in entries if e not in IGNORED_DIRS and e not in IGNORED_FILES]
    entries = [e for e in entries if not (os.path.isfile(os.path.join(dir_path, e)) and not is_text_file(e))]

    for i, entry in enumerate(entries):
        path = os.path.join(dir_path, entry)
        is_last = (i == len(entries) - 1)
        connector = "└── " if is_last else "├── "
        tree_str += f"{prefix}{connector}{entry}\n"

        if os.path.isdir(path):
            extension = "    " if is_last else "│   "
            tree_str += generate_tree(path, prefix + extension)
            
    return tree_str

def dump_project(root_dir, output_file):
    with open(output_file, 'w', encoding='utf-8', errors='ignore') as out:
        out.write(f"PROJECT OVERVIEW & SOURCE EXTRACTION\n")
        out.write(f"Root Directory: {os.path.abspath(root_dir)}\n")
        out.write("=" * 80 + "\n\n")

        # 1. Directory Tree
        out.write("### DIRECTORY TREE STRUCTURE ###\n\n")
        out.write(f"{os.path.basename(os.path.abspath(root_dir))}/\n")
        out.write(generate_tree(root_dir))
        out.write("\n" + "=" * 80 + "\n\n")

        # 2. File Contents
        out.write("### SOURCE CODE & CONFIGURATIONS ###\n\n")
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

            for file in sorted(files):
                if file in IGNORED_FILES or not is_text_file(file):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, root_dir)

                out.write(f"--- START FILE: {rel_path} ---\n")
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='replace') as infile:
                        out.write(infile.read().strip())
                except Exception as e:
                    out.write(f"[Error reading file: {e}]")
                out.write(f"\n--- END FILE: {rel_path} ---\n\n")

    print(f"Extraction complete! File saved as: {output_file}")

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    output_filename = "project_context.txt"
    dump_project(target_dir, output_filename)