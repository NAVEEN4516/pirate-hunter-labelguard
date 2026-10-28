"""Package repository deliverables while respecting Git's ignored local state/secrets."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "dist/Pirate_Hunter_LabelGuard_Submission.zip"
target.parent.mkdir(exist_ok=True)
result = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT)
paths = sorted(set(p.decode("utf-8") for p in result.split(b"\0") if p))
manifest = []
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
    for relative in paths:
        path = ROOT / relative
        if not path.is_file() or relative.startswith(("dist/", ".git/")):
            continue
        archive.write(path, "Pirate_Hunter_LabelGuard/" + relative)
        manifest.append({"path": relative, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    archive.writestr("Pirate_Hunter_LabelGuard/SUBMISSION_MANIFEST.json", json.dumps(manifest, indent=2))
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    names = archive.namelist()
    assert all("/.venv/" not in n and not n.endswith("/.env") and "/runtime/" not in n for n in names)
    for required in ["README.md", "compose.yaml", "docs/REPORT.md", "docs/DEMO_SESSION.md", "output/pdf/Pirate_Hunter_Final_Report.pdf", "output/presentation/Pirate_Hunter_Project_Report.pptx", "eval/scenarios.json", "labelguard/api.py"]:
        assert "Pirate_Hunter_LabelGuard/" + required in names
print(target)
print(len(manifest), "files;", target.stat().st_size, "bytes; SHA256", hashlib.sha256(target.read_bytes()).hexdigest())
