"""Build orchestration script for the MMST project.

The script wraps the typical developer workflow:

1. Optional dependency installation (editable install incl. dev extras).
2. Test execution via pytest.
3. Optional source and wheel distribution build using `python -m build`.
4. Optional creation of a portable, relocatable runtime bundle.

Usage examples:
    python scripts/build.py                    # full pipeline
    python scripts/build.py --no-install       # skip dependency installation
    python scripts/build.py --no-tests         # skip pytest
    python scripts/build.py --package-only     # only build distributions
    python scripts/build.py --portable-only    # only create portable bundle
    python scripts/build.py --portable --dist dist/releases
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import textwrap
import time
import venv
from pathlib import Path
from typing import Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StepError(RuntimeError):
    """Raised when one of the build steps fails."""


def run_command(
    command: Iterable[str | Path], *, cwd: Path | None = None, env: Optional[dict[str, str]] = None
) -> None:
    """Execute a command and raise a helpful error message on failure."""

    cmd_list: List[str] = [str(part) for part in command]
    display = " ".join(cmd_list)
    print(f"\n>> {display}")
    run_env = env if env is not None else None
    result = subprocess.run(cmd_list, cwd=str(cwd or PROJECT_ROOT), env=run_env)
    if result.returncode != 0:
        raise StepError(f"Command failed with exit code {result.returncode}: {display}")


def ensure_build_dependency() -> None:
    """Install the `build` package on demand so packaging can run."""

    try:
        __import__("build")
    except ModuleNotFoundError:
        run_command([sys.executable, "-m", "pip", "install", "build"])


def install_dependencies(editable: bool = True) -> None:
    """Install project dependencies (editable install incl. dev extras by default)."""

    install_target = ".[dev]" if editable else "."
    run_command([sys.executable, "-m", "pip", "install", "-e", install_target])


def run_tests() -> None:
    """Execute the pytest suite."""

    run_command([sys.executable, "-m", "pytest"])


def build_distributions(out_dir: Path | None = None) -> None:
    """Build sdist and wheel artifacts using python -m build."""

    ensure_build_dependency()
    command = [sys.executable, "-m", "build"]
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        command.extend(["--outdir", str(out_dir)])
    run_command(command)


def _handle_remove_readonly(func, path, exc_info) -> None:
    del exc_info  # unused
    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass
    func(path)


def robust_rmtree(path: Path, *, attempts: int = 6, delay: float = 0.6) -> None:
    """Remove a directory tree with retries to handle Windows file locking."""

    if not path.exists():
        return

    last_error: Optional[BaseException] = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            shutil.rmtree(path, onerror=_handle_remove_readonly)
            return
        except Exception as error:  # pragma: no cover - platform specific
            last_error = error
            time.sleep(delay * attempt)
    if os.name == "nt":  # pragma: no cover - Windows only
        try:
            subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(path)], check=True)
            return
        except subprocess.CalledProcessError as error:
            last_error = error
    raise StepError(f"Unable to remove directory {path}: {last_error}")


def portable_platform_slug() -> str:
    """Return a normalized platform identifier used for portable bundle naming."""

    system = platform.system().strip().lower() or "unknown"
    machine = platform.machine().strip().lower() or "unknown"

    system_aliases = {
        "darwin": "macos",
    }
    arch_aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "x86_64": "x86_64",
        "i386": "x86",
        "i686": "x86",
        "aarch64": "arm64",
        "arm64": "arm64",
    }

    system = system_aliases.get(system, system.replace(" ", "_"))
    machine = arch_aliases.get(machine, machine.replace(" ", "_"))

    return f"{system}-{machine}"


def portable_python_executable(env_dir: Path) -> Path:
    """Locate the Python interpreter inside the freshly created portable env."""

    candidates = [
        env_dir / "Scripts" / "python.exe",
        env_dir / "Scripts" / "python",
        env_dir / "Scripts" / "pythonw.exe",
        env_dir / "bin" / "python3",
        env_dir / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise StepError(f"Unable to locate Python interpreter inside {env_dir}.")


def create_portable_launchers(env_dir: Path) -> None:
    """Write small helper launchers for Windows and POSIX systems."""

    windows_python = "pythonw.exe" if (env_dir / "Scripts" / "pythonw.exe").exists() else "python.exe"
    windows_script = textwrap.dedent(
        f"""\
        @echo off
        setlocal
        set SCRIPT_DIR=%~dp0
        "%SCRIPT_DIR%Scripts\\{windows_python}" -m mmst.core.app %*
        """
    ).strip() + "\n"
    (env_dir / "run-mmst-portable.bat").write_text(windows_script, encoding="utf-8")

    posix_script = textwrap.dedent(
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        PYTHON="$DIR/bin/python3"
        if [ ! -x "$PYTHON" ]; then
            PYTHON="$DIR/bin/python"
        fi
        exec "$PYTHON" -m mmst.core.app "$@"
        """
    ).strip() + "\n"
    posix_path = env_dir / "run-mmst-portable.sh"
    posix_path.write_text(posix_script, encoding="utf-8")
    try:
        posix_path.chmod(posix_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        # Best-effort: on some systems chmod may fail (e.g. Windows-mounted FS)
        pass


def write_portable_readme(env_dir: Path, slug: str) -> None:
    """Drop a short README with usage instructions into the bundle."""

    readme_text = textwrap.dedent(
        f"""\
        MMST portable bundle ({slug})
        ==================================

        This bundle contains a self-contained Python runtime with the MMST
        application installed. Extract the archive to a writable location and
        start it using one of the helper scripts:

        * Windows: run-mmst-portable.bat
        * Linux/macOS: ./run-mmst-portable.sh

        The scripts forward any additional command line arguments to the
        application entry point. The environment is isolated and does not
        require installation of the package on the target system.
        """
    ).strip() + "\n"
    (env_dir / "PORTABLE-README.txt").write_text(readme_text, encoding="utf-8")


def build_portable_bundle(
    out_dir: Path,
    *,
    name: Optional[str] = None,
    archive_format: str = "zip",
    keep_env: bool = False,
) -> Path:
    """Create a relocatable virtual environment with the project installed and archive it."""

    slug = portable_platform_slug()
    bundle_name = name or f"mmst-portable-{slug}"
    env_dir = out_dir / bundle_name

    if env_dir.exists():
        shutil.rmtree(env_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    builder = venv.EnvBuilder(with_pip=True, clear=True, symlinks=False)
    builder.create(env_dir)

    python_exe = portable_python_executable(env_dir)
    pip_env: dict[str, str] = dict(os.environ)
    pip_env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    pip_env.setdefault("PIP_DEFAULT_TIMEOUT", "60")
    pip_env.setdefault("PIP_RETRIES", "5")

    run_command([python_exe, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], env=pip_env)
    run_command(
        [python_exe, "-m", "pip", "install", "--no-cache-dir", "--prefer-binary", str(PROJECT_ROOT)],
        env=pip_env,
    )

    create_portable_launchers(env_dir)
    write_portable_readme(env_dir, slug)

    archive_path = Path(
        shutil.make_archive(
            str(env_dir),
            archive_format,
            root_dir=env_dir.parent,
            base_dir=env_dir.name,
        )
    )

    if not keep_env:
        time.sleep(0.5)
        robust_rmtree(env_dir)

    return archive_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MMST build helper")
    parser.add_argument(
        "--no-install",
        dest="install",
        action="store_false",
        help="Skip dependency installation",
    )
    parser.add_argument(
        "--no-tests",
        dest="tests",
        action="store_false",
        help="Skip running the pytest suite",
    )
    parser.add_argument(
        "--no-package",
        dest="package",
        action="store_false",
        help="Skip building distributions",
    )
    parser.add_argument(
        "--package-only",
        dest="package_only",
        action="store_true",
        help="Only build distributions (implies --no-install --no-tests)",
    )
    parser.add_argument(
        "--dist",
        dest="dist",
        type=Path,
        help="Custom output directory for build artifacts",
    )
    parser.add_argument(
        "--portable",
        dest="portable",
        action="store_true",
        help="Create a portable runtime bundle (virtualenv + launchers + archive)",
    )
    parser.add_argument(
        "--portable-only",
        dest="portable_only",
        action="store_true",
        help="Only create portable bundle (implies --no-install --no-tests --no-package)",
    )
    parser.add_argument(
        "--portable-dir",
        dest="portable_dir",
        type=Path,
        help="Target directory for portable bundle output (default: dist/portable)",
    )
    parser.add_argument(
        "--portable-name",
        dest="portable_name",
        help="Override default portable bundle name",
    )
    parser.add_argument(
        "--portable-format",
        dest="portable_format",
        choices=("zip", "gztar", "bztar", "tar"),
        default="zip",
        help="Archive format for portable bundle (default: zip)",
    )
    parser.add_argument(
        "--portable-keep-env",
        dest="portable_keep_env",
        action="store_true",
        help="Keep unpacked portable environment alongside the archive",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    install_step = args.install
    test_step = args.tests
    package_step = args.package
    portable_step = args.portable

    if args.package_only:
        install_step = False
        test_step = False
        package_step = True
    if args.portable_only:
        install_step = False
        test_step = False
        package_step = False
        portable_step = True

    try:
        if install_step:
            install_dependencies()
        if test_step:
            run_tests()
        if package_step:
            build_distributions(args.dist)
        if portable_step:
            portable_dir = args.portable_dir or (PROJECT_ROOT / "dist" / "portable")
            archive = build_portable_bundle(
                portable_dir,
                name=args.portable_name,
                archive_format=args.portable_format,
                keep_env=args.portable_keep_env,
            )
            print(f"\nPortable bundle created at {archive}")
    except StepError as error:
        print(f"\nBuild failed: {error}")
        raise SystemExit(1) from error

    print("\nBuild pipeline completed successfully.")


if __name__ == "__main__":
    main()
