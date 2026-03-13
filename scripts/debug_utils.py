# Purpose: structured debug logging for workflow diagnostics.
# Example: DebugConsole.log("STEP_START", "Applying Shading")
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import inspect
from pathlib import Path
import time
from typing import Any, Callable

from .settings_utils import AddonSettings


@dataclass
class DebugRuntimeSettings:
    enabled: bool = False
    use_colors: bool = True
    timestamp_format: str = "%Y-%m-%d %H:%M:%S.%f"
    label: str = "GAME-ASSET-DEBUG"


class DebugConsole:
    _ANSI_COLORS = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "reset": "\033[0m",
    }

    @classmethod
    def _load_settings(cls) -> DebugRuntimeSettings:
        config = AddonSettings.get_value("debug", {}) or {}
        return DebugRuntimeSettings(
            enabled=bool(config.get("enabled", False)),
            use_colors=bool(config.get("use_colors", True)),
            timestamp_format=str(config.get("timestamp_format", "%Y-%m-%d %H:%M:%S.%f")),
            label=str(config.get("label", "GAME-ASSET-DEBUG")),
        )

    @classmethod
    def _format_timestamp(cls, fmt: str) -> str:
        return datetime.now().strftime(fmt)[:-3]

    @classmethod
    def _colorize(cls, text: str, color_name: str, use_colors: bool) -> str:
        if not use_colors:
            return text
        color = cls._ANSI_COLORS.get(color_name, "")
        reset = cls._ANSI_COLORS["reset"] if color else ""
        return f"{color}{text}{reset}"


    @classmethod
    def _format_source_file(cls, source_filename: str) -> str:
        addon_root = Path(__file__).resolve().parent.parent
        source_path = Path(source_filename).resolve()

        try:
            return str(source_path.relative_to(addon_root)).replace("\\", "/")
        except ValueError:
            if source_path.parent == source_path:
                return source_path.name
            return f"{source_path.parent.name}/{source_path.name}"

    @classmethod
    def log(cls, event: str, detail: str = "", color: str = "cyan"):
        settings = cls._load_settings()
        if not settings.enabled:
            return

        caller_frame = inspect.currentframe().f_back
        source_file = cls._format_source_file(caller_frame.f_code.co_filename)
        source_function = caller_frame.f_code.co_name
        timestamp = cls._format_timestamp(settings.timestamp_format)
        message = (
            f"[{settings.label}] {timestamp} | {event} | "
            f"{source_file}:{source_function} | {detail}"
        )
        print(cls._colorize(message, color, settings.use_colors))

    @classmethod
    def log_step_start(cls, step_title: str, step_function: Callable[[Any], Any]):
        settings = cls._load_settings()
        if not settings.enabled:
            return None

        code = getattr(getattr(step_function, "__func__", step_function), "__code__", None)
        if code is None:
            source = "unknown"
        else:
            source = f"{cls._format_source_file(code.co_filename)}:{code.co_name}"

        started_at = time.perf_counter()
        cls.log("STEP_START", f"{step_title} -> {source}", color="blue")
        return started_at

    @classmethod
    def log_step_complete(cls, step_title: str, started_at):
        if started_at is None:
            return

        elapsed = time.perf_counter() - started_at
        cls.log("STEP_END", f"{step_title} finished in {elapsed:.3f}s", color="green")
