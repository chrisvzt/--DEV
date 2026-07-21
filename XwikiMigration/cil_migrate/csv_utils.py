from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: Iterable[dict],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))
