from __future__ import annotations

import ctypes
import os
import platform
from dataclasses import dataclass

import psutil
from serial.tools import list_ports


@dataclass(slots=True)
class ProcessInfo:
    pid: int
    name: str
    username: str
    executable: str


@dataclass(slots=True)
class PortInfo:
    device: str
    description: str
    hardware_id: str


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def list_processes() -> list[ProcessInfo]:
    current_pid = os.getpid()
    items: list[ProcessInfo] = []
    for process in psutil.process_iter(["pid", "name", "username", "exe"]):
        try:
            info = process.info
            pid = int(info["pid"])
            if pid in (0, 4, current_pid):
                continue
            name = info.get("name") or f"PID {pid}"
            items.append(
                ProcessInfo(
                    pid=pid,
                    name=name,
                    username=info.get("username") or "权限受限",
                    executable=info.get("exe") or "",
                )
            )
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    return sorted(items, key=lambda item: (item.name.lower(), item.pid))


def list_serial_ports() -> list[PortInfo]:
    return [
        PortInfo(
            device=port.device,
            description=port.description or "串口设备",
            hardware_id=port.hwid or "",
        )
        for port in sorted(list_ports.comports(), key=lambda item: item.device)
    ]


def system_summary() -> str:
    privilege = "管理员" if is_admin() else "标准权限"
    return f"Windows {platform.release()} · {platform.machine()} · {privilege}"

