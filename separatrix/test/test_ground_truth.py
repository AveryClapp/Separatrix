#!/usr/bin/env python3
"""Unit tests for Phase-4 ground-truth mapping (eval/ground_truth.py).

Maps Magma canary sites (file, line) onto behavioral-graph nodes at two
granularities: a tight line-band (node-level) and the enclosing function
(region-level, the roadmap's "bug-containing region"). File matching is by
basename (graph stores 'repo/foo.c', patches say 'foo.c').
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eval"))
import ground_truth as gt  # noqa: E402

GRAPH = {"nodes": [
    {"id": 1, "function": "bar", "file": "repo/foo.c", "line": 100},
    {"id": 2, "function": "bar", "file": "repo/foo.c", "line": 104},
    {"id": 3, "function": "baz", "file": "repo/foo.c", "line": 200},
    {"id": 4, "function": "qux", "file": "repo/other.c", "line": 50},
]}


def test_matches_function_by_nearest_node_basename():
    m = gt.map_sites(GRAPH, [{"bug_id": "B1", "file": "foo.c", "line": 104}], window=3)
    assert m[0]["function"] == "bar"
    assert m[0]["node"] == 2


def test_node_band_includes_only_nodes_within_window():
    m = gt.map_sites(GRAPH, [{"bug_id": "B1", "file": "foo.c", "line": 104}], window=3)
    assert m[0]["node_band"] == {2}          # id1 at line 100 is 4 lines away (>3)


def test_region_is_whole_enclosing_function():
    m = gt.map_sites(GRAPH, [{"bug_id": "B1", "file": "foo.c", "line": 104}], window=3)
    assert m[0]["region_nodes"] == {1, 2}    # both 'bar' nodes, not 'baz'


def test_labels_over_universe_node_level():
    m = gt.map_sites(GRAPH, [{"bug_id": "B1", "file": "foo.c", "line": 104}], window=3)
    assert gt.labels_over([1, 2, 3, 4], m, level="node") == [0, 1, 0, 0]


def test_labels_over_universe_region_level():
    m = gt.map_sites(GRAPH, [{"bug_id": "B1", "file": "foo.c", "line": 104}], window=3)
    assert gt.labels_over([1, 2, 3, 4], m, level="region") == [1, 1, 0, 0]


def test_multiple_sites_union_their_regions():
    sites = [{"bug_id": "B1", "file": "foo.c", "line": 100},
             {"bug_id": "B2", "file": "other.c", "line": 50}]
    m = gt.map_sites(GRAPH, sites, window=3)
    assert gt.labels_over([1, 2, 3, 4], m, level="region") == [1, 1, 0, 1]


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); passed += 1
        except AssertionError:
            print(f"  [FAIL] {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            print(f"  [ERR ] {fn.__name__}: {e}")
    print(f"ground_truth: {passed}/{len(fns)} passed")
    return 0 if passed == len(fns) else 1


if __name__ == "__main__":
    sys.exit(_run())
