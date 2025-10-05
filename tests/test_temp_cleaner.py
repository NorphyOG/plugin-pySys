import sys
from pathlib import Path
import time

from mmst.plugins.system_tools.temp_cleaner import TempCleaner

def test_temp_cleaner_scan_and_delete(tmp_path: Path):
    # Create fake temp structure
    cat_dir = tmp_path / "cat"
    cat_dir.mkdir()
    files = []
    for i in range(3):
        p = cat_dir / f"f{i}.txt"
        data = ("x" * (i + 1) * 10).encode()
        p.write_bytes(data)
        files.append(p)
    # Custom categories override
    cleaner = TempCleaner(extra_categories={"custom": ("Custom", [cat_dir])})
    result = cleaner.scan(selected_categories=["custom"])  # only custom
    assert "custom" in result.categories
    cat_res = result.categories["custom"]
    assert len(cat_res.files) == 3
    total_size = sum(f.stat().st_size for f in files)
    assert cat_res.total_size == total_size
    # Dry run delete
    report = cleaner.delete(result, dry_run=True, categories=["custom"])
    assert report["custom"]["files"] == 3
    assert report["custom"]["size"] == total_size
    for f in files:
        assert f.exists()
    # Real delete with age threshold too high -> nothing
    report2 = cleaner.delete(result, dry_run=False, categories=["custom"], min_age_seconds=999999)
    assert report2["custom"]["files"] == 0
    for f in files:
        assert f.exists()
    # Real delete without threshold
    report3 = cleaner.delete(result, dry_run=False, categories=["custom"], min_age_seconds=0)
    assert report3["custom"]["files"] == 3
    for f in files:
        assert not f.exists()
