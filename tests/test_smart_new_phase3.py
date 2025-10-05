import time
from pathlib import Path
from mmst.plugins.media_library.smart_playlists import Rule, RuleGroup, SmartPlaylist, evaluate_smart_playlist

class Media:
    def __init__(self, path, kind='audio', mtime=None, size=0, rating=None):
        self.path = path
        self.kind = kind
        self.mtime = mtime if mtime is not None else time.time()
        self.size = size
        self.rating = rating


def meta_provider(_p: Path):
    class M: ...
    return M()


def build_entries(now):
    return [
        (Media('recent.mp3', mtime=now - 1800, size=5_000_000, rating=5), Path('.')),   # 0.5h old ~5MB
        (Media('yesterday.mp3', mtime=now - 26*3600, size=25_000_000, rating=4), Path('.')), # ~1 day + 2h old ~25MB
        (Media('old.mp3', mtime=now - 40*86400, size=100_000_000, rating=1), Path('.')),     # 40 days old ~100MB
    ]


def test_rule_level_negate():
    now = time.time()
    entries = build_entries(now)
    # rating >=4 but NOT kind==video (rule-level negate on kind)
    sp = SmartPlaylist(
        name='neg-rule',
        group=RuleGroup(match='all', rules=[
            Rule(field='rating', op='>=', value=4),
            Rule(field='kind', op='==', value='video', negate=True)
        ])
    )
    result = evaluate_smart_playlist(sp, entries, meta_provider)
    names = {m.path for m,_ in result}
    assert 'recent.mp3' in names and 'yesterday.mp3' in names and 'old.mp3' not in names


def test_within_hours_and_weeks():
    now = time.time()
    entries = build_entries(now)
    sp_hours = SmartPlaylist(name='last2h', rules=[Rule('mtime','within_hours',2)], match='all')
    names_hours = {m.path for m,_ in evaluate_smart_playlist(sp_hours, entries, meta_provider)}
    assert 'recent.mp3' in names_hours and 'yesterday.mp3' not in names_hours

    sp_weeks = SmartPlaylist(name='last3w', rules=[Rule('mtime','within_weeks',3)], match='all')
    names_weeks = {m.path for m,_ in evaluate_smart_playlist(sp_weeks, entries, meta_provider)}
    assert 'recent.mp3' in names_weeks and 'yesterday.mp3' in names_weeks and 'old.mp3' not in names_weeks


def test_within_months_and_derived_age():
    now = time.time()
    entries = build_entries(now)
    sp_months = SmartPlaylist(name='last2m', rules=[Rule('mtime','within_months',2)], match='all')
    names_months = {m.path for m,_ in evaluate_smart_playlist(sp_months, entries, meta_provider)}
    # 40 days is within approx 2 months window (~61 days), so should be included
    assert 'old.mp3' in names_months

    # derived age_days > 30 should include old only
    sp_age = SmartPlaylist(name='age_gt30', rules=[Rule('age_days','>',30)], match='all')
    names_age = {m.path for m,_ in evaluate_smart_playlist(sp_age, entries, meta_provider)}
    assert 'old.mp3' in names_age and 'recent.mp3' not in names_age


def test_filesize_mb_between():
    now = time.time()
    entries = build_entries(now)
    # 5MB, 25MB, 100MB ~ approximate conversions
    sp_size_mid = SmartPlaylist(name='size_mid', rules=[Rule('filesize_mb','between',[4,50])], match='all')
    names_mid = {m.path for m,_ in evaluate_smart_playlist(sp_size_mid, entries, meta_provider)}
    assert 'recent.mp3' in names_mid and 'yesterday.mp3' in names_mid and 'old.mp3' not in names_mid
