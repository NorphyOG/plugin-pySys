"""Diagnostic helpers for the MediaLibrary plugin.

This script provides two entry points:

1. ``generate`` – Create a synthetic MediaLibrary dataset with tens of thousands
   of files, including on-disk placeholders and a pre-populated SQLite index.
2. ``benchmark`` – Run timing probes against a dataset to capture baseline
   latencies for critical data retrieval paths.

Examples (PowerShell):

```powershell
# Generate a 50k item dataset for local benchmarking (overwrites target).
python -m scripts.diag_media_library_plugin generate --output ./benchmarks/ml-50k --count 50000 --force

# Run the default benchmark suite against the dataset.
python -m scripts.diag_media_library_plugin benchmark --library ./benchmarks/ml-50k
```
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sqlite3
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from mmst.plugins.media_library.core import LibraryIndex, infer_kind


DEFAULT_FILE_SIZE = 2048  # bytes
DEFAULT_TAG_POOL = 64
DEFAULT_TAGS_PER_FILE = (0, 3)  # inclusive range
DEFAULT_RATING_RANGE = (0, 5)
DEFAULT_SOURCE_COUNT = 3
DEFAULT_FILE_COUNT = 50_000


FILE_KIND_TABLE: Sequence[Tuple[str, Sequence[str]]] = (
	("audio", (".mp3", ".flac", ".wav", ".aac")),
	("video", (".mp4", ".mkv", ".avi")),
	("image", (".jpg", ".png", ".webp")),
	("doc", (".pdf", ".epub")),
)


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="MediaLibrary diagnostic helpers")
	sub = parser.add_subparsers(dest="command", required=True)

	gen = sub.add_parser(
		"generate",
		help="Generate a synthetic MediaLibrary dataset (files + SQLite index)",
	)
	gen.add_argument("--output", type=Path, required=True, help="Target directory for dataset")
	gen.add_argument("--count", type=int, default=DEFAULT_FILE_COUNT, help="Total number of files to create")
	gen.add_argument(
		"--sources",
		type=int,
		default=DEFAULT_SOURCE_COUNT,
		help="Number of library sources to distribute files across",
	)
	gen.add_argument("--seed", type=int, default=None, help="Deterministic RNG seed")
	gen.add_argument("--file-size", type=int, default=DEFAULT_FILE_SIZE, help="Size in bytes for generated files")
	gen.add_argument(
		"--tags-per-file",
		type=int,
		nargs=2,
		metavar=("MIN", "MAX"),
		default=DEFAULT_TAGS_PER_FILE,
		help="Inclusive range for how many tags each file receives",
	)
	gen.add_argument(
		"--tag-pool",
		type=int,
		default=DEFAULT_TAG_POOL,
		help="Number of unique tags to sample from when generating metadata",
	)
	gen.add_argument(
		"--rating-range",
		type=int,
		nargs=2,
		metavar=("MIN", "MAX"),
		default=DEFAULT_RATING_RANGE,
		help="Inclusive rating range. Negative minimum disables ratings entirely.",
	)
	gen.add_argument(
		"--force",
		action="store_true",
		help="Remove the output directory if it already exists",
	)
	gen.add_argument(
		"--skip-files",
		action="store_true",
		help="Populate the SQLite index without creating placeholder files on disk",
	)

	bench = sub.add_parser(
		"benchmark",
		help="Run timing measurements against a MediaLibrary dataset",
	)
	bench.add_argument(
		"--library",
		type=Path,
		required=True,
		help="Directory containing the generated dataset (expects library.db)",
	)
	bench.add_argument(
		"--iterations",
		type=int,
		default=3,
		help="Number of timing iterations per operation",
	)
	bench.add_argument(
		"--csv",
		type=Path,
		default=None,
		help="Optional CSV output capturing benchmark results",
	)

	return parser


@dataclass
class GenerationSummary:
	output_dir: Path
	db_path: Path
	sources: int
	files: int
	tag_pool: int
	file_size: int


def main(argv: Optional[Sequence[str]] = None) -> int:
	args = _build_parser().parse_args(argv)
	if args.command == "generate":
		summary = generate_dataset(
			output_dir=args.output,
			total_files=args.count,
			source_count=args.sources,
			seed=args.seed,
			file_size=args.file_size,
			tags_per_file=tuple(args.tags_per_file),
			tag_pool_size=args.tag_pool,
			rating_range=tuple(args.rating_range),
			force=args.force,
			skip_files=args.skip_files,
		)
		_print_generation_summary(summary)
		return 0
	if args.command == "benchmark":
		results = run_benchmark(
			dataset_dir=args.library,
			iterations=max(1, args.iterations),
		)
		_print_benchmark_results(results)
		if args.csv is not None:
			write_benchmark_csv(args.csv, results)
		return 0
	return 1


def generate_dataset(
	output_dir: Path,
	total_files: int,
	source_count: int,
	seed: Optional[int],
	file_size: int,
	tags_per_file: Tuple[int, int],
	tag_pool_size: int,
	rating_range: Tuple[int, int],
	force: bool,
	skip_files: bool,
) -> GenerationSummary:
	if total_files <= 0:
		raise ValueError("total_files must be positive")
	if source_count <= 0:
		raise ValueError("source_count must be positive")
	if file_size <= 0:
		raise ValueError("file_size must be positive")

	rng = random.Random(seed)
	normalized_output = output_dir.resolve()
	db_path = normalized_output / "library.db"
	sources_root = normalized_output / "sources"

	if normalized_output.exists():
		if not force:
			raise FileExistsError(
				f"Output directory '{normalized_output}' already exists. Use --force to overwrite."
			)
		shutil.rmtree(normalized_output)
	normalized_output.mkdir(parents=True, exist_ok=True)
	sources_root.mkdir(parents=True, exist_ok=True)

	# Prepare tag pool and rating distribution.
	tag_pool = [f"tag_{i:03d}" for i in range(tag_pool_size)]
	min_tags, max_tags = tags_per_file
	if min_tags < 0 or max_tags < 0 or min_tags > max_tags:
		raise ValueError("Invalid --tags-per-file range")

	rating_min, rating_max = rating_range
	ratings_enabled = rating_min >= 0 and rating_max >= rating_min

	# Initialise the database schema using the production LibraryIndex helper.
	index = LibraryIndex(db_path)
	source_ids: List[int] = []
	for idx in range(source_count):
		source_path = (sources_root / f"source_{idx:02d}").resolve()
		source_path.mkdir(parents=True, exist_ok=True)
		source_id = index.add_source(source_path)
		source_ids.append(source_id)
	index.close()

	rows: List[Tuple[int, str, int, float, str, Optional[int], Optional[str]]] = []
	now = time.time()

	for i in range(total_files):
		source_idx = i % source_count
		source_path = sources_root / f"source_{source_idx:02d}"

		kind_label, extensions = rng.choice(FILE_KIND_TABLE)
		extension = rng.choice(tuple(extensions))

		# Build nested directory structure to mimic real-world libraries.
		bucket = max(1, total_files // 500)
		album_bucket = i // bucket
		rel_dir = Path(kind_label) / f"collection_{album_bucket:04d}"
		filename = f"item_{i:06d}{extension}"
		rel_path = rel_dir / filename
		abs_dir = source_path / rel_dir
		abs_dir.mkdir(parents=True, exist_ok=True)
		abs_path = abs_dir / filename

		if not skip_files:
			content = _build_file_payload(i, file_size)
			abs_path.write_bytes(content)
			os.utime(abs_path, (now, now - rng.uniform(0, 60 * 60 * 24 * 365)))

		size = file_size if not skip_files else rng.randint(max(1, file_size // 2), file_size * 2)
		mtime = now - rng.uniform(0, 60 * 60 * 24 * 365)
		if ratings_enabled:
			rating = rng.randint(rating_min, rating_max)
			if rng.random() < 0.15:
				rating = None
		else:
			rating = None

		tag_count = rng.randint(min_tags, max_tags) if tag_pool else 0
		if tag_count > 0:
			tags = json.dumps(sorted(rng.sample(tag_pool, k=tag_count)))
		else:
			tags = None

		rows.append(
			(
				source_ids[source_idx],
				str(rel_path).replace(os.sep, "/"),
				size,
				mtime,
				infer_kind(abs_path if not skip_files else rel_path),
				rating,
				tags,
			)
		)

		if (i + 1) % 5000 == 0:
			print(f"[generate] created metadata for {i + 1:,} files", file=sys.stderr)

	# Bulk insert rows into the SQLite database in a single transaction.
	connection = sqlite3.connect(str(db_path))
	try:
		connection.execute("PRAGMA foreign_keys = ON")
		connection.execute("PRAGMA journal_mode = WAL")
		with connection:
			connection.executemany(
				"""
				INSERT INTO files(source_id, path, size, mtime, kind, rating, tags)
				VALUES (?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT(source_id, path) DO UPDATE SET
					size=excluded.size,
					mtime=excluded.mtime,
					kind=excluded.kind,
					rating=excluded.rating,
					tags=excluded.tags
				""",
				rows,
			)
	finally:
		connection.close()

	print(f"[generate] complete – inserted {len(rows):,} records", file=sys.stderr)
	return GenerationSummary(
		output_dir=normalized_output,
		db_path=db_path,
		sources=source_count,
		files=total_files,
		tag_pool=tag_pool_size,
		file_size=file_size,
	)


def run_benchmark(dataset_dir: Path, iterations: int) -> List[Tuple[str, List[float], int]]:
	dataset_dir = dataset_dir.resolve()
	db_path = dataset_dir / "library.db"
	if not db_path.exists():
		raise FileNotFoundError(f"Expected '{db_path}' to exist")

	# Warm-up: ensure database is accessible and gather total count once.
	index = LibraryIndex(db_path)
	try:
		total_files = _count_files(index)
	finally:
		index.close()

	operations: List[Tuple[str, Callable[[LibraryIndex], Tuple[int, float]]]] = [
		(
			"list_files_1000",
			lambda idx: _timed_count(lambda: idx.list_files(limit=1000)),
		),
		(
			"list_files_5000",
			lambda idx: _timed_count(lambda: idx.list_files(limit=5000)),
		),
		(
			"list_files_all",
			lambda idx: _timed_count(idx.list_files),
		),
		(
			"list_playlists",
			lambda idx: _timed_count(idx.list_playlists),
		),
	]

	results: List[Tuple[str, List[float], int]] = []
	for label, operation in operations:
		durations: List[float] = []
		last_count = 0
		for _ in range(iterations):
			idx = LibraryIndex(db_path)
			try:
				count, duration = operation(idx)
				last_count = count
				durations.append(duration)
			finally:
				idx.close()
		results.append((label, durations, last_count))

	results.append(("total_files", [0.0], total_files))
	return results


def write_benchmark_csv(target: Path, results: List[Tuple[str, List[float], int]]) -> None:
	target.parent.mkdir(parents=True, exist_ok=True)
	with target.open("w", encoding="utf-8", newline="") as handle:
		handle.write("metric,iteration,value,count\n")
		for label, durations, count in results:
			if not durations:
				handle.write(f"{label},1,0,{count}\n")
				continue
			for idx, duration in enumerate(durations, start=1):
				handle.write(f"{label},{idx},{duration:.6f},{count}\n")


def _print_generation_summary(summary: GenerationSummary) -> None:
	print("MediaLibrary dataset generated:")
	print(f"  Output dir : {summary.output_dir}")
	print(f"  Database   : {summary.db_path}")
	print(f"  Sources    : {summary.sources}")
	print(f"  Files      : {summary.files:,}")
	print(f"  Tag pool   : {summary.tag_pool}")
	print(f"  File size  : ~{summary.file_size} bytes")


def _print_benchmark_results(results: List[Tuple[str, List[float], int]]) -> None:
	print("Benchmark results:")
	for label, durations, count in results:
		if label == "total_files":
			print(f"  Total files: {count:,}")
			continue
		if not durations:
			print(f"  {label:<20} – no samples")
			continue
		avg = statistics.mean(durations)
		p95 = statistics.quantiles(durations, n=20)[-1] if len(durations) > 1 else durations[0]
		print(
			f"  {label:<20} – avg {avg:.4f}s | samples={len(durations)} | count={count:,} | p95={p95:.4f}s"
		)


def _build_file_payload(index: int, size: int) -> bytes:
	pattern = (f"MediaLibrarySynthetic-{index:06d}-".encode("utf-8"))
	repetitions = (size // len(pattern)) + 1
	payload = (pattern * repetitions)[:size]
	return payload


def _timed_count(producer: Callable[[], Iterable]) -> Tuple[int, float]:
	start = time.perf_counter()
	data = list(producer())
	duration = time.perf_counter() - start
	count = len(data)
	return count, duration


def _count_files(index: LibraryIndex) -> int:
	with sqlite3.connect(str(index._db_path)) as connection:  # type: ignore[attr-defined]
		cursor = connection.execute("SELECT COUNT(*) FROM files")
		row = cursor.fetchone()
		return int(row[0]) if row and row[0] is not None else 0


if __name__ == "__main__":
	raise SystemExit(main())
