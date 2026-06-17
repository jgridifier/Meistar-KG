"""Ensure Java is available for opendataloader-pdf."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _java_works() -> bool:
    java_bin = shutil.which("java")
    if not java_bin:
        return False
    result = subprocess.run(
        ["java", "-version"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _homebrew_java_homes() -> list[Path]:
    prefixes = [Path("/usr/local/opt"), Path("/opt/homebrew/opt")]
    versions = ["openjdk@21", "openjdk@17", "openjdk@11", "openjdk"]
    homes: list[Path] = []
    for prefix in prefixes:
        for version in versions:
            base = prefix / version
            candidates = [
                base / "libexec/openjdk.jdk/Contents/Home",
                base,
            ]
            for candidate in candidates:
                if (candidate / "bin" / "java").exists():
                    homes.append(candidate)
    return homes


def _bundled_java_home() -> Path | None:
    project_root = Path(__file__).resolve().parents[2]
    java_dir = project_root / ".java"
    if not java_dir.exists():
        return None
    for candidate in sorted(java_dir.glob("jdk-*/Contents/Home")):
        if (candidate / "bin" / "java").exists():
            return candidate
    return None


def _activate_java_home(java_home: Path) -> None:
    os.environ["JAVA_HOME"] = str(java_home)
    os.environ["PATH"] = f"{java_home / 'bin'}:{os.environ.get('PATH', '')}"


def ensure_java_available() -> None:
    """Set JAVA_HOME when missing but a usable JDK can be located."""
    if _java_works():
        return

    for java_home in [*_homebrew_java_homes(), _bundled_java_home()]:
        if java_home is None:
            continue
        _activate_java_home(java_home)
        if _java_works():
            return

    raise RuntimeError(
        "Java 11+ is required for opendataloader-pdf. "
        "Install with `brew install openjdk@17` or from https://adoptium.net/, "
        "then set JAVA_HOME."
    )


def java_version() -> str:
    ensure_java_available()
    result = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False)
    return result.stderr.strip().splitlines()[0] if result.stderr else "unknown"