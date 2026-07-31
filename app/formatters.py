from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


def format_hex(data: bytes, limit: int | None = None) -> str:
    shown = data if limit is None else data[:limit]
    text = " ".join(f"{value:02X}" for value in shown)
    if limit is not None and len(data) > limit:
        text += " …"
    return text


def format_ascii(data: bytes, limit: int | None = None) -> str:
    shown = data if limit is None else data[:limit]
    text = "".join(chr(value) if 32 <= value <= 126 else "·" for value in shown)
    if limit is not None and len(data) > limit:
        text += "…"
    return text


def format_size(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"


@dataclass(slots=True)
class CaptureEvent:
    timestamp: datetime
    direction: str
    endpoint: str
    data: bytes
    baud_rate: int | None = None
    frame: str = ""
    process_id: int | None = None

    @property
    def direction_label(self) -> str:
        return "接收 RX" if self.direction == "rx" else "发送 TX"

    def searchable_text(self) -> str:
        return " ".join(
            (
                self.timestamp.isoformat(timespec="milliseconds"),
                self.direction,
                self.direction_label,
                self.endpoint,
                str(self.process_id or ""),
                format_hex(self.data),
                format_ascii(self.data),
            )
        ).lower()

    def to_record(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp.isoformat(timespec="milliseconds"),
            "direction": self.direction.upper(),
            "endpoint": self.endpoint,
            "process_id": self.process_id,
            "baud_rate": self.baud_rate,
            "frame": self.frame,
            "size": len(self.data),
            "hex": format_hex(self.data),
            "ascii": format_ascii(self.data),
        }


def export_csv(path: str | Path, events: Iterable[CaptureEvent]) -> None:
    records = [event.to_record() for event in events]
    fields = [
        "timestamp",
        "direction",
        "endpoint",
        "process_id",
        "baud_rate",
        "frame",
        "size",
        "hex",
        "ascii",
    ]
    with Path(path).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def export_json(path: str | Path, events: Iterable[CaptureEvent]) -> None:
    records = [event.to_record() for event in events]
    with Path(path).open("w", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False, indent=2)
