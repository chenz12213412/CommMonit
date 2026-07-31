from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import frida
from PySide6.QtCore import QObject, Signal, Slot

from .formatters import CaptureEvent


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


@dataclass(slots=True)
class _CaptureSession:
    session: Any
    script: Any
    endpoints: dict[str, str] | None


class CaptureController(QObject):
    event_received = Signal(object)
    attached = Signal(int)
    target_detached = Signal(int, str)
    detached = Signal(str)
    port_closed = Signal(int, str, str)
    error = Signal(str)
    diagnostic = Signal(str)
    session_count_changed = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sessions: dict[int, _CaptureSession] = {}
        self.port_closed.connect(self._auto_stop_closed_port)

    @property
    def is_attached(self) -> bool:
        return bool(self._sessions)

    @property
    def pids(self) -> tuple[int, ...]:
        return tuple(self._sessions)

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def active_endpoint_count(self) -> int:
        total = 0
        for state in self._sessions.values():
            total += len(state.endpoints) if state.endpoints is not None else 1
        return total

    def attach(self, pid: int, endpoints: dict[str, str] | None = None) -> bool:
        existing = self._sessions.get(pid)
        if existing is not None:
            if endpoints:
                merged = dict(existing.endpoints or {})
                merged.update(endpoints)
                existing.script.exports_sync.setendpoints(merged)
                existing.endpoints = merged
                self.session_count_changed.emit(self.session_count)
            return True

        session: Any = None
        try:
            source = resource_path("app/frida_agent.js").read_text(encoding="utf-8")
            session = frida.get_local_device().attach(pid)
            script = session.create_script(source, name="CommMonit Serial Observer")
            script.on("message", lambda message, data, target_pid=pid: self._on_message(target_pid, message, data))
            session.on(
                "detached",
                lambda reason, crash=None, target_pid=pid: self._on_session_detached(
                    target_pid, reason, crash
                ),
            )
            self._sessions[pid] = _CaptureSession(session=session, script=script, endpoints=endpoints)
            script.load()
            if endpoints is not None:
                script.exports_sync.setendpoints(endpoints)
            self.attached.emit(pid)
            self.session_count_changed.emit(self.session_count)
            return True
        except Exception as exc:
            self._sessions.pop(pid, None)
            if session is not None:
                try:
                    session.detach()
                except Exception:
                    pass
            self.error.emit(self._friendly_error(exc, pid))
            return False

    def attach_many(self, targets: dict[int, dict[str, str]]) -> tuple[list[int], list[int]]:
        attached: list[int] = []
        failed: list[int] = []
        for pid, endpoints in targets.items():
            if self.attach(pid, endpoints):
                attached.append(pid)
            else:
                failed.append(pid)
        return attached, failed

    def detach_pid(self, pid: int, reason: str = "用户停止") -> None:
        state = self._sessions.pop(pid, None)
        if state is None:
            return
        try:
            state.session.detach()
        except Exception:
            pass
        self.target_detached.emit(pid, reason)
        self.session_count_changed.emit(self.session_count)
        if not self._sessions:
            self.detached.emit(reason)

    def detach(self, reason: str = "用户停止") -> None:
        states = list(self._sessions.items())
        self._sessions.clear()
        for pid, state in states:
            try:
                state.session.detach()
            except Exception:
                pass
            self.target_detached.emit(pid, reason)
        if states:
            self.session_count_changed.emit(0)
            self.detached.emit(reason)

    def _on_session_detached(self, pid: int, reason: str, crash: Any = None) -> None:
        state = self._sessions.pop(pid, None)
        if state is None:
            return
        message = f"PID {pid} 已分离：{reason}"
        if crash:
            message += f"（{crash}）"
        self.target_detached.emit(pid, message)
        self.session_count_changed.emit(self.session_count)
        if not self._sessions:
            self.detached.emit(message)

    def _on_message(self, pid: int, message: dict[str, Any], data: bytes | None) -> None:
        if message.get("type") == "error":
            details = message.get("description") or message.get("stack") or "注入脚本异常"
            self.error.emit(f"PID {pid}：{details}")
            return
        payload = message.get("payload")
        if not isinstance(payload, dict):
            return
        event_type = payload.get("type")
        if event_type == "diagnostic":
            self.diagnostic.emit(f"PID {pid} · {payload.get('message', '')}")
            return
        if event_type == "serial_closed":
            self.port_closed.emit(
                pid,
                str(payload.get("handle", "")),
                str(payload.get("endpoint", "串口")),
            )
            return
        if event_type != "serial":
            return
        event = CaptureEvent(
            timestamp=datetime.now(),
            direction=str(payload.get("direction", "rx")),
            endpoint=str(payload.get("endpoint", "串口句柄")),
            data=bytes(data or b""),
            baud_rate=int(payload["baudRate"]) if payload.get("baudRate") else None,
            frame=str(payload.get("frame", "")),
            process_id=pid,
        )
        self.event_received.emit(event)

    @Slot(int, str, str)
    def _auto_stop_closed_port(self, pid: int, handle: str, endpoint: str) -> None:
        state = self._sessions.get(pid)
        if state is None:
            return
        if state.endpoints is None:
            self.detach_pid(pid, f"{endpoint} 已关闭，监控已自动停止")
            return
        state.endpoints.pop(handle, None)
        self.diagnostic.emit(f"{endpoint} 已关闭，已停止该串口的监控")
        if not state.endpoints:
            self.detach_pid(pid, f"{endpoint} 已关闭，监控已自动停止")
        else:
            self.session_count_changed.emit(self.session_count)

    @staticmethod
    def _friendly_error(exc: Exception, pid: int) -> str:
        text = str(exc)
        lowered = text.lower()
        if "access-denied" in lowered or "permission" in lowered:
            return f"PID {pid} 拒绝访问。请以管理员身份运行，并避开受保护的系统进程。"
        if "process not found" in lowered:
            return f"PID {pid} 已经退出，请刷新后重试。"
        if "not supported" in lowered:
            return f"PID {pid} 不支持用户态附加，可能受到系统或安全软件保护。"
        return f"无法附加到 PID {pid}：{text}"
