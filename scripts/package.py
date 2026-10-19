"""Build a deterministic source archive from an explicit allowlist; no upload."""

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist"
OUTPUT.mkdir(exist_ok=True)
names = ["pyproject.toml", "README.md", ".env.example", ".gitignore", "policy.example.json"]
names.append("policy.algen-runtime.json")
for folder in ("config", "src", "tests", "docs", "scripts", ".github"):
    names.extend(
        str(p.relative_to(ROOT))
        for p in (ROOT / folder).rglob("*")
        if p.is_file()
        and p.suffix in {".py", ".yaml", ".yml", ".md", ".json"}
        and "__pycache__" not in p.parts
    )
if (ROOT / "requirements.lock").exists():
    names.append("requirements.lock")
archive = OUTPUT / "algen-release-guard-0.2.0.algen"
with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
    for name in sorted(set(names)):
        path = ROOT / name
        if path.is_symlink():
            raise ValueError("symlinks are not allowed in release archives")
        info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        bundle.writestr(info, path.read_bytes())
data = archive.read_bytes()
metadata = {
    "file": archive.name,
    "sha256": hashlib.sha256(data).hexdigest(),
    "size_bytes": len(data),
    "entrypoint": "algen_release_guard.cli:main",
    "published": False,
}
(OUTPUT / "package-info.json").write_text(json.dumps(metadata, indent=2) + "\n")
print(json.dumps(metadata))
