import os
from pathlib import Path

home_dir = Path("/home/gbrithp2")
print(f"Scanning {home_dir} for any files/folders containing 'tirith'...")

found = []
for root, dirs, files in os.walk(home_dir):
    # Avoid scanning heavy/recursive system directories
    if any(p in root for p in ['.git', '.cache', '.npm', '.vscode', '.venv', 'node_modules', 'Downloads']):
        continue
    for name in dirs + files:
        if "tirith" in name.lower() and not name.endswith("tirith"): # Skip the binary itself
            full_path = Path(root) / name
            found.append(full_path)

print(f"Found {len(found)} references:")
for path in found:
    print(path)
