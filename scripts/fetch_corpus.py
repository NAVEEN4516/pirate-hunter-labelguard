"""Fetch pinned public FSSAI reference documents; never follows document instructions."""

from pathlib import Path
import hashlib
import json
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "labelling": {
        "url": "https://www.fssai.gov.in/upload/uploadfiles/files/Comp_Labelling%20Display_Version%20VIII_09_09_2025.pdf",
        "title": "Food Safety and Standards (Labelling and Display) Regulations, 2020",
        "version": "VIII, 2025-09-09",
    },
    "claims": {
        "url": "https://www.fssai.gov.in/upload/uploadfiles/files/Compendium_Advertising_Claims_Regulations_14_12_2022.pdf",
        "title": "Food Safety and Standards (Advertising and Claims) Regulations, 2018",
        "version": "IV, 2022-12-14",
    },
    "amendment_2026": {
        "url": "https://www.fssai.gov.in/docs/food-law/regulations/amendments/labelling-display/Notification%20dt%2024_03_2026_NRC.pdf",
        "title": "Food Safety and Standards (Labelling and Display) First Amendment Regulations, 2026",
        "version": "2026-03-24; commencement 2027-07-01",
    },
}


def main():
    target = ROOT / "data" / "raw"
    target.mkdir(parents=True, exist_ok=True)
    for key, record in SOURCES.items():
        path = target / f"{key}.pdf"
        if not path.exists():
            for attempt in range(4):
                try:
                    req = urllib.request.Request(
                        record["url"], headers={"User-Agent": "LabelGuard-Academic/1.0"}
                    )
                    with urllib.request.urlopen(req, timeout=40) as response:
                        content = response.read()
                    if not content.startswith(b"%PDF"):
                        raise ValueError("Source did not return a PDF")
                    path.write_bytes(content)
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    time.sleep(2**attempt)
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        record["file"] = str(path.relative_to(ROOT)).replace("\\", "/")
        print(key, path.stat().st_size, record["sha256"])
    (ROOT / "data" / "sources.json").write_text(json.dumps(SOURCES, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
