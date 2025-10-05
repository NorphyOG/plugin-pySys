from pathlib import Path
from mmst.plugins.media_library.smart_playlists import SmartPlaylist, Rule, RuleGroup, save_smart_playlists, load_smart_playlists


def test_order_and_negate_persistence(tmp_path: Path):
    # Build a playlist with deliberate ordering and mixed negations
    g = RuleGroup(match='all', negate=False, rules=[
        Rule(field='rating', op='>=', value=4),
        Rule(field='kind', op='==', value='audio', negate=True),
        Rule(field='duration', op='between', value=[100,500])
    ], groups=[])
    sp = SmartPlaylist(name='order-test', group=g)

    p = tmp_path / 'smart.json'
    assert save_smart_playlists(p, [sp])
    loaded = load_smart_playlists(p)
    assert len(loaded) == 1
    lg = loaded[0].group
    assert lg is not None
    assert len(lg.rules) == 3
    # Order should be identical by field sequence
    fields = [r.field for r in lg.rules]
    assert fields == ['rating', 'kind', 'duration']
    # Negation should persist only on the second rule
    negs = [getattr(r, 'negate', False) for r in lg.rules]
    assert negs == [False, True, False]
