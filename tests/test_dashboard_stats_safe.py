from pathlib import Path
from mmst.plugins.media_library.dashboard_stats import build_dashboard_stats
from mmst.plugins.media_library.core import MediaFile

def test_build_dashboard_stats_empty():
    result = build_dashboard_stats([], lambda p: None, lambda p: (None, ()))
    assert result.stats['total_files'] == 0
    assert 'rating_distribution' in result.stats
    assert result.errors == 0


def test_build_dashboard_stats_basic(tmp_path: Path):
    # Create minimal fake entries
    root = tmp_path
    files = []
    for i in range(3):
        f = root / f"a_{i}.mp3"
        f.write_bytes(b'00')
        mf = MediaFile(path=f.name, size=2, mtime=0.0, kind='audio', rating=5 if i==0 else None, tags=("x",))
        files.append((mf, root))

    def md_loader(p: Path):
        class _Meta:  # minimal stub
            duration = 10
            genre = 'Rock'
            artist = 'Artist'
            rating = 4
        return _Meta()

    def attr_loader(p: Path):
        # Use rating from MediaFile already encoded above
        for mf, r in files:
            if (r / mf.path) == p:
                return (mf.rating, mf.tags)
        return (None, ())

    result = build_dashboard_stats(files, md_loader, attr_loader)
    assert result.stats['total_files'] == 3
    assert result.stats['audio_count'] == 3
    assert result.stats['rating_distribution']
    assert result.stats['top_genres']
