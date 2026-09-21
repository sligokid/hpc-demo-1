"""
Tests for graph.py.

QdrantClient is mocked — no running Qdrant instance required.
"""

import json
import os
import sys
import pathlib
import tempfile
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import graph as graph_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_record(file, lang, uploaded_by, tags, sentiment_label="neutral", sentiment_score=0.0, title=None):
    return {
        "file": file,
        "lang": lang,
        "uploaded_by": uploaded_by,
        "tags": tags,
        "sentiment_label": sentiment_label,
        "sentiment_score": sentiment_score,
        "title": title or os.path.basename(file),
    }


RECORDS = [
    _make_record("en/safety-intro.mp3",  "en", "alice@org.com", ["safety", "onboarding"], "positive", 0.85),
    _make_record("en/line-jam.mp3",       "en", "bob@org.com",   ["equipment", "maintenance", "safety"], "negative", -0.6),
    _make_record("es/mantenimiento.mp3",  "es", "carlos@org.com",["equipment", "maintenance"], "neutral", 0.0),
    _make_record("en/quality-check.mp3",  "en", "alice@org.com", ["quality", "onboarding"], "positive", 0.7),
    _make_record("fr/solo.mp3",           "fr", "diane@org.com", ["unique-tag-xyz"], "neutral", 0.0),
]


# ---------------------------------------------------------------------------
# build_graph — nodes
# ---------------------------------------------------------------------------

def test_build_graph_node_count():
    graph = graph_mod.build_graph(RECORDS)
    assert len(graph["nodes"]) == len(RECORDS)


def test_build_graph_node_ids_are_basenames():
    graph = graph_mod.build_graph(RECORDS)
    ids = {n["id"] for n in graph["nodes"]}
    assert "safety-intro.mp3" in ids
    assert "line-jam.mp3" in ids


def test_build_graph_positive_node_colour():
    graph = graph_mod.build_graph(RECORDS)
    node = next(n for n in graph["nodes"] if n["id"] == "safety-intro.mp3")
    assert node["colour"] == graph_mod.SENTIMENT_COLOURS["positive"]


def test_build_graph_negative_node_colour():
    graph = graph_mod.build_graph(RECORDS)
    node = next(n for n in graph["nodes"] if n["id"] == "line-jam.mp3")
    assert node["colour"] == graph_mod.SENTIMENT_COLOURS["negative"]


def test_build_graph_neutral_node_colour():
    graph = graph_mod.build_graph(RECORDS)
    node = next(n for n in graph["nodes"] if n["id"] == "solo.mp3")
    assert node["colour"] == graph_mod.SENTIMENT_COLOURS["neutral"]


def test_build_graph_unknown_sentiment_uses_default_colour():
    records = [_make_record("x.mp3", "en", "u@org.com", [])]
    records[0]["sentiment_label"] = "unknown_value"
    graph = graph_mod.build_graph(records)
    assert graph["nodes"][0]["colour"] == graph_mod.DEFAULT_COLOUR


def test_build_graph_node_attributes_present():
    graph = graph_mod.build_graph(RECORDS)
    node = next(n for n in graph["nodes"] if n["id"] == "safety-intro.mp3")
    assert node["lang"] == "en"
    assert node["uploaded_by"] == "alice@org.com"
    assert "safety" in node["tags"]
    assert node["sentiment_label"] == "positive"
    assert node["sentiment_score"] == 0.85


# ---------------------------------------------------------------------------
# build_graph — edges
# ---------------------------------------------------------------------------

def test_build_graph_edge_between_shared_tag_videos():
    # safety-intro and line-jam share "safety"
    graph = graph_mod.build_graph(RECORDS)
    edge_pairs = {(e["source"], e["target"]) for e in graph["edges"]}
    edge_pairs |= {(e["target"], e["source"]) for e in graph["edges"]}
    assert ("safety-intro.mp3", "line-jam.mp3") in edge_pairs


def test_build_graph_edge_weight_equals_shared_tag_count():
    # line-jam and mantenimiento share "equipment" and "maintenance" → weight 2
    graph = graph_mod.build_graph(RECORDS)
    edge = next(
        e for e in graph["edges"]
        if set([e["source"], e["target"]]) == {"line-jam.mp3", "mantenimiento.mp3"}
    )
    assert edge["weight"] == 2
    assert set(edge["shared_tags"]) == {"equipment", "maintenance"}


def test_build_graph_no_edge_for_no_shared_tags():
    # solo.mp3 has a unique tag — no edges expected
    graph = graph_mod.build_graph(RECORDS)
    solo_edges = [
        e for e in graph["edges"]
        if "solo.mp3" in (e["source"], e["target"])
    ]
    assert solo_edges == []


def test_build_graph_empty_records():
    graph = graph_mod.build_graph([])
    assert graph == {"nodes": [], "edges": []}


# ---------------------------------------------------------------------------
# write_json
# ---------------------------------------------------------------------------

def test_write_json_produces_valid_json():
    graph = graph_mod.build_graph(RECORDS)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "graph.json")
        graph_mod.write_json(graph, path)
        with open(path) as f:
            loaded = json.load(f)
    assert "nodes" in loaded
    assert "edges" in loaded
    assert len(loaded["nodes"]) == len(RECORDS)


def test_write_json_creates_parent_dirs():
    graph = graph_mod.build_graph([])
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "deep", "nested", "graph.json")
        graph_mod.write_json(graph, path)
        assert os.path.exists(path)


# ---------------------------------------------------------------------------
# write_html
# ---------------------------------------------------------------------------

def test_write_html_produces_file():
    graph = graph_mod.build_graph(RECORDS)
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "graph.html")
        graph_mod.write_html(graph, html_path)
        assert os.path.exists(html_path)


def test_write_html_embeds_graph_json():
    graph = graph_mod.build_graph(RECORDS)
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "graph.html")
        graph_mod.write_html(graph, html_path)
        content = open(html_path).read()
    assert "RAW_GRAPH" in content
    assert "safety-intro.mp3" in content


def test_write_html_injects_lang_options():
    graph = graph_mod.build_graph(RECORDS)
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "graph.html")
        graph_mod.write_html(graph, html_path)
        content = open(html_path).read()
    assert '<option value="en">en</option>' in content
    assert '<option value="es">es</option>' in content
    assert '<option value="fr">fr</option>' in content


def test_write_html_injects_uploader_options():
    graph = graph_mod.build_graph(RECORDS)
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "graph.html")
        graph_mod.write_html(graph, html_path)
        content = open(html_path).read()
    assert "alice@org.com" in content
    assert "bob@org.com" in content


def test_write_html_no_unfilled_placeholders():
    graph = graph_mod.build_graph(RECORDS)
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "graph.html")
        graph_mod.write_html(graph, html_path)
        content = open(html_path).read()
    assert "{{GRAPH_JSON}}" not in content
    assert "{{LANG_OPTIONS}}" not in content
    assert "{{UPLOADER_OPTIONS}}" not in content


# ---------------------------------------------------------------------------
# load_metadata (mocked Qdrant)
# ---------------------------------------------------------------------------

def _make_point(payload):
    p = MagicMock()
    p.payload = payload
    return p


def test_load_metadata_returns_all_payloads():
    mock_qdrant = MagicMock()
    mock_qdrant.scroll.return_value = (
        [_make_point(r) for r in RECORDS],
        None,  # no next page
    )
    result = graph_mod.load_metadata(mock_qdrant)
    assert len(result) == len(RECORDS)
    assert result[0]["file"] == RECORDS[0]["file"]


def test_load_metadata_paginates():
    page1 = [_make_point(RECORDS[0]), _make_point(RECORDS[1])]
    page2 = [_make_point(RECORDS[2])]
    mock_qdrant = MagicMock()
    mock_qdrant.scroll.side_effect = [
        (page1, "cursor-token"),
        (page2, None),
    ]
    result = graph_mod.load_metadata(mock_qdrant)
    assert len(result) == 3
