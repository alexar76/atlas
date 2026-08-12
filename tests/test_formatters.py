"""Formatter / human-readable detail tests."""

from __future__ import annotations

from atlas.formatters import build_detail, headline, metric_rows


def test_headline_weather():
    assert headline("weather", {"temperature_c": 21.56}) == "21.6 °C"


def test_headline_air_and_quake():
    assert "PM2.5" in headline("air", {"pm2_5_ugm3": 9.6})
    assert "4.8" in headline("quake", {"magnitude": 4.8})


def test_headline_empty():
    assert "Waiting" in headline("weather", {})


def test_metric_rows_labels():
    rows = metric_rows({"temperature_c": 20.0, "humidity_pct": 40})
    labels = {r["label"] for r in rows}
    assert "Temperature" in labels
    assert "Humidity" in labels
    assert any("°C" in r["value"] for r in rows)


def test_build_detail_summary_cites_place():
    station = {
        "id": "om-wx-01",
        "layer": "weather",
        "label": "Open-Meteo Weather",
        "place": "Berlin",
        "online": True,
        "live": True,
        "mode": "live",
        "source": "https://open-meteo.com",
        "values": {"temperature_c": 22.0, "humidity_pct": 50.0},
        "headline": "22.0 °C",
    }
    detail = build_detail(station, cached=True, age_ms=3500)
    assert detail["title"] == "Open-Meteo Weather"
    assert "Berlin" in detail["summary"]
    assert "Temperature" in detail["summary"] or "22" in detail["summary"]
    assert "cached" in detail["status_line"]
    assert "LIVE" in detail["status_line"]
    assert len(detail["metrics"]) >= 2


def test_build_detail_sim_status():
    station = {
        "id": "ws-01",
        "layer": "weather",
        "label": "Weather Sim A",
        "place": "GAIA demo campus (sim)",
        "online": True,
        "live": False,
        "mode": "sim",
        "source": None,
        "values": {"temperature_c": 19.0},
        "headline": "19.0 °C",
    }
    detail = build_detail(station, cached=True, age_ms=500)
    assert "SIM" in detail["status_line"]
