import os
from pathlib import Path

workspace = Path(__file__).parent.parent
search_terms = ["Policy Block", "ROLL rejected", "Delta 0.0"]

print(f"Scanning all files in {workspace}...")

for root, dirs, files in os.walk(workspace):
    # Skip python virtual envs or cache if present
    if any(p in root for p in ['.venv', '__pycache__', '.git']):
        continue
    for file in files:
        file_path = Path(root) / file
        try:
            content = file_path.read_text(errors='ignore')
            for term in search_terms:
                if term in content:
                    print(f"Found '{term}' in file: {file_path}")
        except Exception as e:
            pass
