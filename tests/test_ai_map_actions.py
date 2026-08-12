"""Map action resolver for ATLAS Analyst."""

from __future__ import annotations

from atlas.ai_map_actions import map_action_station_ids, resolve_map_actions


def test_show_berlin_flies_and_opens():
    actions = resolve_map_actions("Show Berlin weather and air quality on the map")
    types = [a["type"] for a in actions]
    assert "fly_to" in types
    fly = next(a for a in actions if a["type"] == "fly_to")
    assert abs(fly["lat"] - 52.52) < 0.1
    ids = map_action_station_ids(actions)
    assert "om-wx-01" in ids
    assert "om-aq-01" in ids


def test_open_station_id():
    actions = resolve_map_actions("Open om-wx-01")
    assert any(a.get("station_id") == "om-wx-01" for a in actions)


def test_nyc_tide():
    actions = resolve_map_actions("Fly to New York and open the tide station")
    ids = map_action_station_ids(actions)
    assert "noaa-tide-01" in ids or "nws-01" in ids


def test_ecosystem_no_map():
    assert resolve_map_actions("How does the Hub relate to ARGUS?") == []


def test_ru_show_berlin():
    actions = resolve_map_actions("Покажи на карте погоду в Берлине")
    assert actions
    assert any(a["type"] == "fly_to" for a in actions)


def test_show_ottawa():
    actions = resolve_map_actions("Show Ottawa on the map")
    assert any(a["type"] == "fly_to" for a in actions)
    ids = map_action_station_ids(actions)
    assert "om-wx-ottawa" in ids


def test_short_alias_does_not_hijack_unrelated_words():
    """Regression: the 2-char "la" alias matched inside display / calidad."""
    actions = resolve_map_actions("display the grid carbon")
    ids = map_action_station_ids(actions)
    labels = [a.get("label") for a in actions if a["type"] == "fly_to"]
    assert "uk-grid-01" in ids
    assert not any(sid.endswith("losangeles") for sid in ids)
    assert "Los Angeles" not in labels


def test_spanish_article_is_not_a_place():
    for q in ("muestra la calidad del aire", "montre la qualité de l'air"):
        labels = [
            a.get("label") for a in resolve_map_actions(q) if a["type"] == "fly_to"
        ]
        assert "Los Angeles" not in labels


def test_atlas_word_is_not_los_angeles():
    assert resolve_map_actions("show me what atlas is") == []


def test_los_angeles_still_matches_by_name():
    actions = resolve_map_actions("Show Los Angeles air quality")
    ids = map_action_station_ids(actions)
    fly = next(a for a in actions if a["type"] == "fly_to")
    assert fly["label"] == "Los Angeles"
    assert "om-aq-losangeles" in ids or "om-wx-losangeles" in ids


def test_hyphenated_alias_still_matches():
    actions = resolve_map_actions("Покажи погоду в нью-дели")
    ids = map_action_station_ids(actions)
    assert any("delhi" in sid for sid in ids)


def test_show_new_delhi():
    actions = resolve_map_actions("Fly to New Delhi air quality")
    fly = next(a for a in actions if a["type"] == "fly_to")
    assert abs(fly["lat"] - 28.61) < 0.2
    ids = map_action_station_ids(actions)
    assert "om-aq-delhi" in ids or "om-wx-delhi" in ids


def test_inflected_and_localized_place_names_still_match():
    """Regression: token boundaries must not break «в Каире» / "Berna"."""
    for q, expect in (
        ("Покажи погоду в Каире", "cairo"),
        ("Muestra el clima en Berna", "demo"),
        ("Montre la météo à Berne", "demo"),
        ("Покажи датчики в Дели", "delhi"),
    ):
        actions = resolve_map_actions(q)
        ids = map_action_station_ids(actions)
        assert actions, f"no map action for {q!r}"
        if expect in ("cairo", "delhi"):
            assert any(expect in sid for sid in ids), (q, ids)
        else:
            assert any(sid in ("ws-01", "ws-02", "aq-01", "em-01") for sid in ids), (q, ids)
