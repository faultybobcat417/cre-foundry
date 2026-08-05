from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
checksum_file = ROOT / "CHECKSUMS.sha256"
errors = []
for line in checksum_file.read_text().splitlines():
    if not line.strip():
        continue
    expected, relative = line.split("  ", 1)
    path = ROOT / relative
    if not path.exists():
        errors.append(f"missing:{relative}")
    elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        errors.append(f"hash:{relative}")
print({"passed": not errors, "errors": errors})
sys.exit(0 if not errors else 1)
