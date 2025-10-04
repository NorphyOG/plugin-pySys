import json
from pathlib import Path
from mmst.plugins.media_library.smart_playlists import (
    Rule, SmartPlaylist, evaluate_smart_playlist, save_smart_playlists, load_smart_playlists
)

class DummyMedia:
    def __init__(self, path, kind, duration=0, rating=None, title=None, tags=None, year=None):
        self.path = path
        self.kind = kind
        self.duration = duration
        self.rating = rating
        self.title = title
        self.tags = tags or []
        self.year = year

class DummyMeta:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def meta_provider(_path: Path):
    return DummyMeta()


def build_entries():
    base = Path('.')
    media = [
        DummyMedia('a.mp3','audio', duration=120, rating=5, title='Alpha Song', tags=['fav','alpha'], year=2024),
        DummyMedia('b.mp3','audio', duration=700, rating=4, title='Beta Long', tags=['long'], year=2023),
        DummyMedia('c.mp4','video', duration=400, rating=3, title='Clip C', tags=['clip'], year=2022),
        DummyMedia('d.jpg','image', duration=0, rating=None, title='Delta Image', tags=['img'], year=2020),
    ]
    return [(m, base) for m in media]


def test_rule_basic_rating_and_kind():
    entries = build_entries()
    sp = SmartPlaylist(
        name='High Audio',
    rules=[Rule(field='rating', op='>=', value=4), Rule(field='kind', op='==', value='audio')],
        match='all',
    )
    result = evaluate_smart_playlist(sp, entries, meta_provider)
    names = {m.path for m,_ in result}
    assert 'a.mp3' in names and 'b.mp3' in names and 'c.mp4' not in names


def test_contains_and_not_contains():
    entries = build_entries()
    sp = SmartPlaylist(
        name='Contains Alpha',
        rules=[Rule(field='title', op='icontains', value='alpha')],
        match='all'
    )
    result = evaluate_smart_playlist(sp, entries, meta_provider)
    assert len(result) == 1 and result[0][0].path == 'a.mp3'

    sp2 = SmartPlaylist(
        name='Not Contains Clip',
        rules=[Rule(field='title', op='not_contains', value='clip')],
        match='all'
    )
    result2 = evaluate_smart_playlist(sp2, entries, meta_provider)
    titles = {m.title for m,_ in result2}
    assert 'Clip C' not in titles


def test_between_duration():
    entries = build_entries()
    sp = SmartPlaylist(
        name='Mid Duration',
        rules=[Rule(field='duration', op='between', value=[300,800])],
        match='all'
    )
    result = evaluate_smart_playlist(sp, entries, meta_provider)
    names = {m.path for m,_ in result}
    assert 'b.mp3' in names and 'c.mp4' in names and 'a.mp3' not in names


def test_save_and_load(tmp_path: Path):
    playlists = [
        SmartPlaylist(name='Test', rules=[Rule(field='kind', op='==', value='audio')]),
        SmartPlaylist(name='Long', rules=[Rule(field='duration', op='>', value=300)])
    ]
    json_path = tmp_path / 'smart.json'
    assert save_smart_playlists(json_path, playlists)
    loaded = load_smart_playlists(json_path)
    assert len(loaded) == 2 and loaded[0].name == 'Test'
