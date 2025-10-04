from pathlib import Path
from mmst.plugins.media_library.smart_playlists import Rule, RuleGroup, SmartPlaylist, evaluate_smart_playlist

class DummyMedia:
    def __init__(self, path, kind, rating=None, duration=0):
        self.path = path
        self.kind = kind
        self.rating = rating
        self.duration = duration


def meta_provider(_p: Path):
    class M: pass
    return M()


def entries():
    base = Path('.')
    return [
        (DummyMedia('a.mp3','audio', rating=5, duration=120), base),
        (DummyMedia('b.mp3','audio', rating=3, duration=800), base),
        (DummyMedia('c.mp4','video', rating=4, duration=400), base),
        (DummyMedia('d.mp3','audio', rating=1, duration=50), base),
    ]


def test_nested_and_or():
    # (rating >=4 AND kind==audio) OR (duration > 500)
    g_left = RuleGroup(match='all', rules=[Rule('rating','>=',4), Rule('kind','==','audio')])
    g_right = RuleGroup(match='all', rules=[Rule('duration','>',500)])
    root = RuleGroup(match='any', groups=[g_left, g_right])
    sp = SmartPlaylist(name='complex', group=root)
    result = evaluate_smart_playlist(sp, entries(), meta_provider)
    names = {m.path for m,_ in result}
    assert 'a.mp3' in names  # rating>=4 & audio
    assert 'b.mp3' in names  # duration>500
    assert 'c.mp4' not in names  # video rating4 but not audio and duration not >500
    assert 'd.mp3' not in names


def test_negated_group():
    # audio AND NOT (rating <=2)
    inner = RuleGroup(match='all', rules=[Rule('rating','<=',2)])
    root = RuleGroup(match='all', rules=[Rule('kind','==','audio')], groups=[RuleGroup(match='all', negate=True, groups=[inner])])
    sp = SmartPlaylist(name='neg', group=root)
    result = evaluate_smart_playlist(sp, entries(), meta_provider)
    names = {m.path for m,_ in result}
    assert 'd.mp3' not in names  # filtered out by NOT
    assert 'a.mp3' in names and 'b.mp3' in names

