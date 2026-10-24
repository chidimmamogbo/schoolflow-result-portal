"""Download the report card fonts while the container is built (D-064; CHANGE 2026-10-24).

Inter, Merriweather and Nunito (SIL Open Font License) come from the Google
Fonts repository at one pinned commit, and each file must match its SHA-256
or the build stops. The fonts and their licences go into the folder named on
the command line; the container copies it into /usr/share/fonts so Pango
finds the fonts by name and nothing is fetched while a PDF is made.
Checked 2026-10-24.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

COMMIT = "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0"
BASE = f"https://raw.githubusercontent.com/google/fonts/{COMMIT}/ofl"
FILES = (
    ("inter/Inter%5Bopsz,wght%5D.ttf", "Inter.ttf",
     "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031"),
    ("inter/OFL.txt", "Inter-OFL.txt",
     "5b9321a4298cfeb6b34354164a1c3afc3db114569984c502b9b35d988fd58c57"),
    ("merriweather/Merriweather%5Bopsz,wdth,wght%5D.ttf", "Merriweather.ttf",
     "d0ed0e359e396af7ad05e73dffd11a3a4c326ea0d0283c56bd9361cb2cc86a96"),
    ("merriweather/OFL.txt", "Merriweather-OFL.txt",
     "715bd349bfa6116f99e351e1548321dcfa25b91df65502d22ca8d624557697d2"),
    ("nunito/Nunito%5Bwght%5D.ttf", "Nunito.ttf",
     "bb55a5ca5c2042335b3991af27c4d0705d0ef41cac6164ac737fd8f2a1e85207"),
    ("nunito/OFL.txt", "Nunito-OFL.txt",
     "580df76c95a1ec5ab878ceb25bb3d85c6a076804e9c970c8c6972aea775fdf65"),
)  # fmt: skip


def main(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for path, name, expected in FILES:
        with urllib.request.urlopen(f"{BASE}/{path}", timeout=60) as response:  # noqa: S310
            data = response.read()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise SystemExit(f"{name}: SHA-256 {actual} does not match {expected}")
        (target / name).write_bytes(data)
        print(f"{name}: {len(data)} bytes, checked")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
