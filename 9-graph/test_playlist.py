"""
Tests for playlist.py.

QdrantClient is mocked — no running Qdrant instance required.
Profile and roles files are written to temp directories.
"""

import json
import os
import sys
import pathlib
import tempfile
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import playlist as pl_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _rec(file, lang, tags, sentiment_label="neutral", uploaded_by="u@org.com"):
    return {
        "file": file,
        "lang": lang,
        "uploaded_by": uploaded_by,
        "tags": tags,
        "sentiment_label": sentiment_label,
        "sentiment_score": 0.0,
        "title": os.path.basename(file),
    }


ALL_VIDEOS = [
    _rec("en/safety-intro.mp3",  "en", ["safety", "onboarding"],          "positive"),
    _rec("en/line-jam.mp3",       "en", ["equipment", "maintenance", "safety"], "negative"),
    _rec("en/quality-check.mp3",  "en", ["quality", "onboarding"],         "positive"),
    _rec("es/mantenimiento.mp3",  "es", ["equipment", "maintenance"],       "neutral"),
    _rec("en/compliance.mp3",     "en", ["compliance", "safety"],           "neutral"),
]

ENGINEER_ROLES = {
    "engineer": ["engineering", "maintenance", "equipment", "safety"],
    "production_operative": ["production", "safety", "onboarding"],
}

ENGINEER_PROFILE = {
    "user": "engineer@org.com",
    "role": "engineer",
    "language": "en",
    "watched": [],
    "personalise": True,
}


def _mock_qdrant(records):
    mock = MagicMock()
    points = []
    for r in records:
        p = MagicMock()
        p.payload = r
        points.append(p)
    mock.scroll.return_value = (points, None)
    return mock


# ---------------------------------------------------------------------------
# score_candidates
# ---------------------------------------------------------------------------

def test_score_candidates_role_match_ranks_higher():
    role_tags = {"safety", "equipment", "maintenance"}
    candidates = [
        _rec("a.mp3", "en", ["safety", "equipment"]),   # 2 role matches
        _rec("b.mp3", "en", ["cooking", "baking"]),     # 0 role matches
    ]
    scored = pl_mod.score_candidates(candidates, role_tags, set(), None)
    assert scored[0]["file"] == "a.mp3"


def test_score_candidates_history_boost():
    role_tags = set()
    history_tags = {"onboarding", "quality"}
    candidates = [
        _rec("a.mp3", "en", ["onboarding", "quality"]),  # 2 history matches
        _rec("b.mp3", "en", ["equipment"]),               # 0 history matches
    ]
    scored = pl_mod.score_candidates(candidates, role_tags, history_tags, None)
    assert scored[0]["file"] == "a.mp3"


def test_score_candidates_sentiment_bonus_applied():
    candidates = [
        _rec("pos.mp3", "en", [], "positive"),
        _rec("neu.mp3", "en", [], "neutral"),
    ]
    scored = pl_mod.score_candidates(candidates, set(), set(), preferred_sentiment="positive")
    assert scored[0]["file"] == "pos.mp3"


def test_score_candidates_no_preferred_sentiment_no_bonus():
    candidates = [
        _rec("pos.mp3", "en", [], "positive"),
        _rec("neg.mp3", "en", [], "negative"),
    ]
    scored = pl_mod.score_candidates(candidates, set(), set(), preferred_sentiment=None)
    # All scores equal — order is stable (positive comes first in input)
    assert scored[0]["_score"] == scored[1]["_score"]


def test_score_candidates_empty_list():
    result = pl_mod.score_candidates([], {"safety"}, set(), None)
    assert result == []


# ---------------------------------------------------------------------------
# build_playlist — language filter
# ---------------------------------------------------------------------------

def test_build_playlist_filters_by_language():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    profile = {**ENGINEER_PROFILE, "language": "en"}
    results = pl_mod.build_playlist(qdrant, profile, ENGINEER_ROLES, top_n=10,
                                     no_personalise=False, sentiment_filter=None)
    langs = {r["lang"] for r in results}
    assert langs == {"en"}


def test_build_playlist_no_lang_filter_returns_all_langs():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    profile = {**ENGINEER_PROFILE, "language": ""}
    results = pl_mod.build_playlist(qdrant, profile, ENGINEER_ROLES, top_n=20,
                                     no_personalise=False, sentiment_filter=None)
    langs = {r["lang"] for r in results}
    assert "en" in langs
    assert "es" in langs


# ---------------------------------------------------------------------------
# build_playlist — watched exclusion
# ---------------------------------------------------------------------------

def test_build_playlist_excludes_watched_by_basename():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    profile = {**ENGINEER_PROFILE, "watched": ["safety-intro.mp3"]}
    results = pl_mod.build_playlist(qdrant, profile, ENGINEER_ROLES, top_n=10,
                                     no_personalise=False, sentiment_filter=None)
    files = [r["file"] for r in results]
    assert not any("safety-intro" in f for f in files)


def test_build_playlist_excludes_watched_by_full_path():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    profile = {**ENGINEER_PROFILE, "watched": ["en/line-jam.mp3"]}
    results = pl_mod.build_playlist(qdrant, profile, ENGINEER_ROLES, top_n=10,
                                     no_personalise=False, sentiment_filter=None)
    files = [r["file"] for r in results]
    assert not any("line-jam" in f for f in files)


def test_build_playlist_all_watched_returns_empty():
    en_files = [v["file"] for v in ALL_VIDEOS if v["lang"] == "en"]
    qdrant = _mock_qdrant(ALL_VIDEOS)
    profile = {**ENGINEER_PROFILE, "watched": en_files}
    results = pl_mod.build_playlist(qdrant, profile, ENGINEER_ROLES, top_n=10,
                                     no_personalise=False, sentiment_filter=None)
    assert results == []


# ---------------------------------------------------------------------------
# build_playlist — top_n
# ---------------------------------------------------------------------------

def test_build_playlist_respects_top_n():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    results = pl_mod.build_playlist(qdrant, ENGINEER_PROFILE, ENGINEER_ROLES,
                                     top_n=2, no_personalise=False, sentiment_filter=None)
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# build_playlist — sentiment filter
# ---------------------------------------------------------------------------

def test_build_playlist_sentiment_filter_positive_only():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    results = pl_mod.build_playlist(qdrant, ENGINEER_PROFILE, ENGINEER_ROLES, top_n=10,
                                     no_personalise=False, sentiment_filter="positive")
    sentiments = {r["sentiment_label"] for r in results}
    assert sentiments == {"positive"}


def test_build_playlist_sentiment_filter_negative_only():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    results = pl_mod.build_playlist(qdrant, ENGINEER_PROFILE, ENGINEER_ROLES, top_n=10,
                                     no_personalise=False, sentiment_filter="negative")
    sentiments = {r["sentiment_label"] for r in results}
    assert sentiments == {"negative"}


# ---------------------------------------------------------------------------
# build_playlist — personalisation
# ---------------------------------------------------------------------------

def test_build_playlist_personalised_result_has_score():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    results = pl_mod.build_playlist(qdrant, ENGINEER_PROFILE, ENGINEER_ROLES, top_n=10,
                                     no_personalise=False, sentiment_filter=None)
    for r in results:
        assert "score" in r


def test_build_playlist_no_personalise_omits_score():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    results = pl_mod.build_playlist(qdrant, ENGINEER_PROFILE, ENGINEER_ROLES, top_n=10,
                                     no_personalise=True, sentiment_filter=None)
    for r in results:
        assert "score" not in r


def test_build_playlist_no_personalise_sorted_by_file():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    results = pl_mod.build_playlist(qdrant, ENGINEER_PROFILE, ENGINEER_ROLES, top_n=10,
                                     no_personalise=True, sentiment_filter=None)
    files = [r["file"] for r in results]
    assert files == sorted(files)


def test_build_playlist_profile_personalise_false_acts_as_no_personalise():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    profile = {**ENGINEER_PROFILE, "personalise": False}
    results = pl_mod.build_playlist(qdrant, profile, ENGINEER_ROLES, top_n=10,
                                     no_personalise=False, sentiment_filter=None)
    for r in results:
        assert "score" not in r


# ---------------------------------------------------------------------------
# build_playlist — result schema
# ---------------------------------------------------------------------------

def test_build_playlist_result_contains_required_fields():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    results = pl_mod.build_playlist(qdrant, ENGINEER_PROFILE, ENGINEER_ROLES, top_n=5,
                                     no_personalise=False, sentiment_filter=None)
    assert len(results) > 0
    for r in results:
        assert "rank" in r
        assert "file" in r
        assert "title" in r
        assert "lang" in r
        assert "tags" in r
        assert "sentiment_label" in r


def test_build_playlist_ranks_are_sequential():
    qdrant = _mock_qdrant(ALL_VIDEOS)
    results = pl_mod.build_playlist(qdrant, ENGINEER_PROFILE, ENGINEER_ROLES, top_n=10,
                                     no_personalise=False, sentiment_filter=None)
    ranks = [r["rank"] for r in results]
    assert ranks == list(range(1, len(results) + 1))


# ---------------------------------------------------------------------------
# build_playlist — empty collection
# ---------------------------------------------------------------------------

def test_build_playlist_empty_qdrant_returns_empty():
    qdrant = _mock_qdrant([])
    results = pl_mod.build_playlist(qdrant, ENGINEER_PROFILE, ENGINEER_ROLES, top_n=10,
                                     no_personalise=False, sentiment_filter=None)
    assert results == []


# ---------------------------------------------------------------------------
# load_profile
# ---------------------------------------------------------------------------

def test_load_profile_reads_json(tmp_path, monkeypatch):
    profile = {"user": "test@org.com", "role": "engineer", "language": "en", "watched": []}
    profile_file = tmp_path / "test@org.com.json"
    profile_file.write_text(json.dumps(profile))
    monkeypatch.setattr(pl_mod, "PROFILES_DIR", str(tmp_path))
    loaded = pl_mod.load_profile("test@org.com")
    assert loaded["role"] == "engineer"


def test_load_profile_missing_exits(tmp_path, monkeypatch):
    monkeypatch.setattr(pl_mod, "PROFILES_DIR", str(tmp_path))
    with pytest.raises(SystemExit):
        pl_mod.load_profile("nobody@org.com")


# ---------------------------------------------------------------------------
# load_roles
# ---------------------------------------------------------------------------

def test_load_roles_reads_yaml(tmp_path, monkeypatch):
    yaml_content = "engineer:\n  - safety\n  - maintenance\n"
    roles_file = tmp_path / "roles.yaml"
    roles_file.write_text(yaml_content)
    monkeypatch.setattr(pl_mod, "ROLES_YAML", str(roles_file))
    roles = pl_mod.load_roles()
    assert "maintenance" in roles["engineer"]


def test_load_roles_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(pl_mod, "ROLES_YAML", str(tmp_path / "nonexistent.yaml"))
    roles = pl_mod.load_roles()
    assert roles == {}
