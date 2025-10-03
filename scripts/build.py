"""Build orchestration script for the MMST project.

The script wraps the typical developer workflow:

1. Optional dependency installation (editable install incl. dev extras).
2. Test execution via pytest.
3. Optional source and wheel distribution build using `python -m build`.

Usage examples:
    python scripts/build.py                # full pipeline
    python scripts/build.py --no-install   # skip dependency installation
    python scripts/build.py --no-tests     # skip pytest
    python scripts/build.py --package-only # only build distributions
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StepError(RuntimeError):
    """Raised when one of the build steps fails."""


def run_command(command: Iterable[str], *, cwd: Path | None = None) -> None:
    """Execute a command and raise a helpful error message on failure."""

    cmd_list: List[str] = list(command)
    display = " ".join(cmd_list)
    print(f"\n>> {display}")
    result = subprocess.run(cmd_list, cwd=str(cwd or PROJECT_ROOT))
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    install_step = args.install
    test_step = args.tests
    package_step = args.package

    if args.package_only:
        install_step = False
        test_step = False
        package_step = True

    try:
        if install_step:
            install_dependencies()
        if test_step:
            run_tests()
        if package_step:
            build_distributions(args.dist)
    except StepError as error:
        print(f"\nBuild failed: {error}")
        raise SystemExit(1) from error

    print("\nBuild pipeline completed successfully.")


if __name__ == "__main__":
    main()
