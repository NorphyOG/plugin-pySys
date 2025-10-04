import time
from pathlib import Path
from mmst.plugins.media_library.smart_playlists import Rule, SmartPlaylist, evaluate_smart_playlist

class DummyMedia:
    def __init__(self, path, mtime):
        self.path = path
        self.kind = 'audio'
        self.mtime = mtime


def meta_provider(_p: Path):
    class M: pass
    return M()


def test_within_days_operator():
    now = time.time()
    entries = [
        (DummyMedia('recent.mp3', now - 3600), Path('.')),          # 1 Stunde alt
        (DummyMedia('old.mp3', now - 60 * 60 * 24 * 40), Path('.')) # ~40 Tage alt
    ]
    sp = SmartPlaylist(
        name='Letzte 7 Tage',
        rules=[Rule(field='mtime', op='within_days', value=7)],
        match='all'
    )
    result = evaluate_smart_playlist(sp, entries, meta_provider)
    names = {m.path for m,_ in result}
    assert 'recent.mp3' in names and 'old.mp3' not in names
