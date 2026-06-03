from pathlib import Path

src_dir = Path("frontend/src")

# Rename files first
files_to_rename = {
    "BankDashboard.tsx": "BankDashboard.tsx",
    "bankState.ts": "bankState.ts"
}

for old, new in files_to_rename.items():
    old_path = src_dir / old
    new_path = src_dir / new
    if old_path.exists():
        old_path.rename(new_path)

# Replace content in all TS/TSX files
for file_path in src_dir.rglob("*.*"):
    if file_path.suffix in (".ts", ".tsx", ".css"):
        content = file_path.read_text(encoding="utf-8")
        
        # Replace Bank -> Bank
        content = content.replace("Bank", "Bank")
        # Replace bank -> bank
        content = content.replace("bank", "bank")
        
        file_path.write_text(content, encoding="utf-8")

print("Frontend refactor complete")
