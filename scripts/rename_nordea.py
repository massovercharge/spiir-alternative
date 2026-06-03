import os
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

def process_file(path: Path):
    if path.suffix not in {".py", ".ts", ".tsx", ".json"}:
        return
    if "node_modules" in path.parts or ".venv" in path.parts or ".git" in path.parts or "dist" in path.parts:
        return
        
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return
        
    new_content = content
    # Case sensitive replacements
    new_content = new_content.replace("Bank", "Bank")
    new_content = new_content.replace("BANK_", "BANK_")
    new_content = new_content.replace("_bank_", "_bank_")
    new_content = new_content.replace("bank_", "bank_")
    new_content = new_content.replace("_bank", "_bank")
    new_content = new_content.replace("bank", "bank")
    
    if new_content != content:
        path.write_text(new_content, encoding="utf-8")
        print(f"Updated {path.relative_to(ROOT)}")

def main():
    for root, dirs, files in os.walk(ROOT):
        for f in files:
            process_file(Path(root) / f)

if __name__ == "__main__":
    main()
