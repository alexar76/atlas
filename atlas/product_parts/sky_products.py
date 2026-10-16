"""Space-weather and sky products: the geomagnetic window and the PV irradiance record."""

from __future__ import annotations

from typing import Any

from ..geo import utc_now


# ── atlas.geomag.window@v1 ────────────────────────────────────────────────────
#
# `situation.brief` deliberately excludes spacewx and geomag — a planetary Kp pin is
# not a site brief — so the two newest dense layers (401 SWPC observations, 13 of 14
# USGS observatories LIVE) had no SKU at all. The job this answers is the one desks
# actually pay for: is the field quiet enough to run the operation right now.
#
# Kp thresholds are the published NOAA planetary-K / G-scale boundaries, not ours.


def _kp_state(kp: float) -> tuple[str, str, str | None]:
    """(state, window status, NOAA G-scale label) for a planetary Kp value."""
    if kp >= 9.0:
        return "extreme_storm", "hold", "G5"
    if kp >= 8.0:
        return "severe_storm", "hold", "G4"
    if kp >= 7.0:
        return "strong_storm", "hold", "G3"
    if kp >= 6.0:
        return "moderate_storm", "hold", "G2"
    if kp >= 5.0:
        return "minor_storm", "hold", "G1"
    if kp >= 4.0:
        return "active", "caution", None
    if kp >= 3.0:
        return "unsettled", "open", None
    return "quiet", "open", None


def geomag_window(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.geomag.window@v1`` — planetary Kp window plus local corroboration.

    Fail-closed on Kp: the whole answer keys on the planetary index, so a missing SWPC
    reading is a refusal rather than a window derived from an observatory alone.
    """
    point = products._parse_query_point(data)
    if point is None:
        return {
            "ok": False,
            "capability_id": "atlas.geomag.window@v1",
            "refuse_reason": "lat/lon required (lat −90…90, lon −180…180)",
        }
    lat, lon = point
    asset_id = str(data.get("asset_id") or "").strip()[:160] or None
    try:
        max_km = float(data.get("max_km") if data.get("max_km") is not None else 1500.0)
    except (TypeError, ValueError):
        max_km = 1500.0
    max_km = max(1.0, min(max_km, 20037.0))
    query = {"lat": lat, "lon": lon, "max_km": max_km, "asset_id": asset_id}

    kp_pins = [
        s for s in stations
        if isinstance(s, dict) and s.get("layer") == "spacewx" and s.get("live")
        and isinstance(s.get("values"), dict)
        and isinstance(s["values"].get("kp_index"), (int, float))
    ]
    if not kp_pins:
        return {
            "ok": False,
            "capability_id": "atlas.geomag.window@v1",
            "refuse_reason": "no LIVE planetary Kp reading available; window refused",
            "query": query,
        }
    # Kp is planetary: every spacewx pin carries the same index, so the worst
    # reported value is the honest one if a stale pin disagrees.
    kp = max(float(s["values"]["kp_index"]) for s in kp_pins)
    kp_state, window_status, g_scale = products._kp_state(kp)
    kp_pin = next(s for s in kp_pins if float(s["values"]["kp_index"]) == kp)

    observatory, obs_km = products._nearest_candidate(stations, lat=lat, lon=lon, layers={"geomag"})
    obs_block: dict[str, Any] | None = None
    if observatory is not None and obs_km is not None and obs_km <= max_km:
        obs_values = observatory.get("values") if isinstance(observatory.get("values"), dict) else {}
        obs_block = {
            **products._citation(observatory),
            "distance_km": round(obs_km, 2),
            "field_nt": obs_values.get("field_nt"),
            "observation_age_s": obs_values.get("observation_age_s"),
            "point_invoke": products._point_handoff(observatory.get("id")),
        }
    # The USGS network is US territory only. Beyond the radius the window is Kp-only,
    # and saying so is the difference between a bounded product and an implied local
    # magnetometer the buyer does not have.
    corroboration = "observatory" if obs_block is not None else "planetary_only"

    aurora_pin, aurora_km = products._nearest_candidate(stations, lat=lat, lon=lon, layers={"spacewx"})
    aurora_block: dict[str, Any] | None = None
    if aurora_pin is not None and aurora_km is not None and aurora_km <= max_km:
        aurora_values = aurora_pin.get("values") if isinstance(aurora_pin.get("values"), dict) else {}
        pct = aurora_values.get("aurora_pct")
        if isinstance(pct, (int, float)):
            aurora_block = {
                **products._citation(aurora_pin),
                "distance_km": round(aurora_km, 2),
                "aurora_pct": float(pct),
            }

    drivers = [
        f"planetary Kp {kp:g} — {kp_state}" + (f" ({g_scale})" if g_scale else ""),
    ]
    if obs_block is not None:
        age = obs_block.get("observation_age_s")
        age_note = f", observation {float(age):.0f} s old" if isinstance(age, (int, float)) else ""
        drivers.append(
            f"nearest USGS observatory {obs_block.get('distance_km')} km away"
            f"{age_note} — total field F available for corroboration"
        )
    else:
        drivers.append(
            f"no USGS geomagnetic observatory within {max_km:g} km — window is planetary Kp only"
        )
    if aurora_block is not None:
        drivers.append(
            f"OVATION aurora probability {aurora_block['aurora_pct']:.0f}% "
            f"at {aurora_block['distance_km']} km"
        )

    actions: list[str] = []
    if window_status == "hold":
        actions.append(
            "Hold magnetic-reference-dependent work (MWD survey acceptance, magnetic "
            "compass checks) until the index falls back below Kp 5."
        )
        actions.append("Expect HF propagation degradation and elevated GNSS ionospheric error.")
    elif window_status == "caution":
        actions.append(
            "Tighten survey acceptance criteria and re-check before committing to a "
            "magnetic reference; the field is active but not in storm."
        )
    else:
        actions.append("No geomagnetic reason to defer magnetic-reference-dependent work.")
    actions.append("Recheck on the next SWPC 1-minute Kp update and retain this signed receipt.")

    payload: dict[str, Any] = {
        "ok": True,
        "capability_id": "atlas.geomag.window@v1",
        "sku": "atlas.geomag.window@v1",
        "generated_at": utc_now(),
        "query": query,
        "kp_index": kp,
        "kp_state": kp_state,
        "noaa_g_scale": g_scale,
        "window_status": window_status,
        "corroboration": corroboration,
        "summary": (
            f"Geomagnetic window {window_status} at {lat:.4f},{lon:.4f}: planetary Kp {kp:g} "
            f"({kp_state}{', ' + g_scale if g_scale else ''}), "
            + (
                f"nearest USGS observatory {obs_block['distance_km']} km"
                if obs_block is not None
                else f"no observatory within {max_km:g} km"
            )
            + ". Not a magnetic-declination correction and not a safety-of-life service."
        ),
        "drivers": drivers,
        "recommended_actions": actions,
        "kp_source": products._citation(kp_pin),
        "nearest_observatory": obs_block,
        "aurora": aurora_block,
        "limitations": [
            "Kp is a planetary 3-hour index published by NOAA SWPC; it is not a local "
            "magnetic measurement at the queried coordinate.",
            "USGS observatories report total field F only. This SKU does not compute or "
            "supply magnetic declination, and it is not an IFR-grade in-field reference.",
            "The USGS observatory network covers United States territory; elsewhere the "
            "window is planetary-only, which `corroboration` states explicitly.",
            "Operational screening, not a safety-of-life navigation or aviation service.",
        ],
        "attribution": [
            "NOAA Space Weather Prediction Center (planetary Kp, OVATION aurora)",
            "U.S. Geological Survey Geomagnetism Program (observatory total field F)",
        ],
    }
    payload["receipt"] = products.make_receipt(payload, capability_id="atlas.geomag.window@v1")
    products.remember_receipt(payload["receipt"])
    payload["receipt_url"], payload["verifier_url"] = products._receipt_links(payload["receipt"])
    return payload


# ── atlas.pv.irradiance.record@v1 ─────────────────────────────────────────────
#
# NASA POWER daily irradiation lags by days, which makes it useless as a nowcast and
# exactly right for the job this SKU sells: a retrospective, attributed record of what
# the sky and the air did over one plant coordinate, citable in a performance-ratio
# argument with an EPC or O&M contractor. It is deliberately NOT a yield model.
#
# Screening thresholds below are ours, not a standard, and the payload says so.


_AOD_ELEVATED = 0.5


_DUST_EVENT_UGM3 = 50.0


def pv_irradiance_record(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.pv.irradiance.record@v1`` — dated irradiance + aerosol record of fact."""
    point = products._parse_query_point(data)
    if point is None:
        return {
            "ok": False,
            "capability_id": "atlas.pv.irradiance.record@v1",
            "refuse_reason": "lat/lon required (lat −90…90, lon −180…180)",
        }
    lat, lon = point
    plant_id = str(data.get("plant_id") or "").strip()[:160] or None
    try:
        max_km = float(data.get("max_km") if data.get("max_km") is not None else 100.0)
    except (TypeError, ValueError):
        max_km = 100.0
    max_km = max(1.0, min(max_km, 2000.0))
    query = {"lat": lat, "lon": lon, "max_km": max_km, "plant_id": plant_id}

    solar, solar_km = products._nearest_candidate(stations, lat=lat, lon=lon, layers={"solar"})
    solar_values = (
        solar.get("values") if solar is not None and isinstance(solar.get("values"), dict) else {}
    )
    all_sky = solar_values.get("solar_irradiation_kwh_m2_day")
    if (
        solar is None
        or solar_km is None
        or solar_km > max_km
        or not isinstance(all_sky, (int, float))
    ):
        return {
            "ok": False,
            "capability_id": "atlas.pv.irradiance.record@v1",
            "refuse_reason": (
                f"no LIVE daily irradiation reading within {max_km:g} km of the plant "
                "coordinate; a record of fact cannot be issued from a distant cell"
            ),
            "query": query,
            "nearest_solar_candidate_distance_km": (
                round(solar_km, 2) if solar_km is not None else None
            ),
        }

    all_sky = float(all_sky)
    clear_raw = solar_values.get("clear_sky_irradiation_kwh_m2_day")
    clear_sky = float(clear_raw) if isinstance(clear_raw, (int, float)) else None
    cloud_loss = None
    cloud_loss_pct = None
    if clear_sky is not None and clear_sky > 0:
        cloud_loss = round(max(0.0, clear_sky - all_sky), 4)
        cloud_loss_pct = round(100.0 * cloud_loss / clear_sky, 2)

    observation_day = solar_values.get("solar_observation_yyyymmdd")
    observation_date = None
    if isinstance(observation_day, (int, float)):
        digits = f"{int(observation_day):08d}"
        if len(digits) == 8:
            observation_date = f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    elif isinstance(observation_day, str) and len(observation_day.strip()) == 8:
        digits = observation_day.strip()
        observation_date = f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"

    irradiance = {
        **products._citation(solar),
        "distance_km": round(solar_km, 2),
        "observation_date": observation_date,
        "all_sky_kwh_m2_day": round(all_sky, 4),
        "clear_sky_kwh_m2_day": round(clear_sky, 4) if clear_sky is not None else None,
        "cloud_loss_kwh_m2_day": cloud_loss,
        "cloud_loss_pct": cloud_loss_pct,
        "point_invoke": products._point_handoff(solar.get("id")),
    }

    aerosol_pin, aerosol_km = products._nearest_candidate(stations, lat=lat, lon=lon, layers={"atmosphere"})
    aerosol: dict[str, Any] | None = None
    if aerosol_pin is not None and aerosol_km is not None and aerosol_km <= max_km:
        aerosol_values = (
            aerosol_pin.get("values") if isinstance(aerosol_pin.get("values"), dict) else {}
        )
        aod = aerosol_values.get("aerosol_optical_depth")
        dust = aerosol_values.get("dust_ugm3")
        if isinstance(aod, (int, float)) or isinstance(dust, (int, float)):
            aerosol = {
                **products._citation(aerosol_pin),
                "distance_km": round(aerosol_km, 2),
                "aerosol_optical_depth": float(aod) if isinstance(aod, (int, float)) else None,
                "dust_ugm3": float(dust) if isinstance(dust, (int, float)) else None,
                "point_invoke": products._point_handoff(aerosol_pin.get("id")),
            }

    weather_pin, weather_km = products._nearest_candidate(stations, lat=lat, lon=lon, layers={"weather"})
    weather: dict[str, Any] | None = None
    if weather_pin is not None and weather_km is not None and weather_km <= max_km:
        weather = {**products._citation(weather_pin), "distance_km": round(weather_km, 2)}

    drivers: list[str] = []
    if observation_date:
        drivers.append(f"NASA POWER daily record date: {observation_date}")
    else:
        drivers.append("NASA POWER record date was not supplied with this reading")
    drivers.append(
        f"all-sky irradiation {all_sky:.3f} kWh/m²/day at {irradiance['distance_km']} km"
    )
    if cloud_loss_pct is not None:
        drivers.append(
            f"clear-sky {clear_sky:.3f} kWh/m²/day — sky delivered {cloud_loss_pct:.1f}% "
            "below clear-sky at this coordinate"
        )
    else:
        drivers.append("clear-sky reference unavailable; cloud loss not derivable")

    soiling_drivers: list[str] = []
    if aerosol is not None:
        aod = aerosol.get("aerosol_optical_depth")
        dust = aerosol.get("dust_ugm3")
        if isinstance(aod, (int, float)):
            note = "elevated" if aod >= products._AOD_ELEVATED else "background"
            soiling_drivers.append(
                f"aerosol optical depth {aod:.3f} ({note}, screening threshold "
                f"{products._AOD_ELEVATED:g})"
            )
        if isinstance(dust, (int, float)):
            note = "dust event" if dust >= products._DUST_EVENT_UGM3 else "no dust event"
            soiling_drivers.append(
                f"dust {dust:.1f} µg/m³ ({note}, screening threshold {products._DUST_EVENT_UGM3:g})"
            )
    else:
        soiling_drivers.append(
            f"no LIVE aerosol/dust reading within {max_km:g} km — soiling driver not evidenced"
        )

    payload: dict[str, Any] = {
        "ok": True,
        "capability_id": "atlas.pv.irradiance.record@v1",
        "sku": "atlas.pv.irradiance.record@v1",
        "generated_at": utc_now(),
        "query": query,
        "record_kind": "retrospective_record_of_fact",
        "summary": (
            f"{plant_id or 'Plant'} at {lat:.4f},{lon:.4f}"
            + (f", record date {observation_date}" if observation_date else "")
            + f": all-sky {all_sky:.3f} kWh/m²/day"
            + (
                f", {cloud_loss_pct:.1f}% below clear-sky"
                if cloud_loss_pct is not None else ", clear-sky reference unavailable"
            )
            + (
                f"; aerosol optical depth {aerosol['aerosol_optical_depth']:.3f}"
                if aerosol is not None
                and isinstance(aerosol.get("aerosol_optical_depth"), (int, float))
                else "; no colocated aerosol evidence"
            )
            + ". Record of fact, not a yield forecast."
        ),
        "irradiance": irradiance,
        "aerosol": aerosol,
        "weather": weather,
        "drivers": drivers,
        "soiling_drivers": soiling_drivers,
        "limitations": [
            "NASA POWER daily irradiation is satellite-derived and published with a "
            "multi-day lag. This is a retrospective record, not a nowcast.",
            "Values describe the POWER source grid cell nearest the coordinate, at the "
            "reported distance — not a pyranometer on the plant.",
            "Aerosol and dust are CAMS-derived modelled composition at the coordinate, "
            "not a measured soiling rate on the modules.",
            "Aerosol/dust screening thresholds in `soiling_drivers` are ATLAS screening "
            "labels, not an industry standard.",
            "Not a yield forecast, not a soiling-loss model, and not a bankable energy "
            "assessment: no P50/P90 and no uncertainty band is supplied.",
        ],
        "attribution": [
            "NASA POWER (daily all-sky and clear-sky surface irradiation)",
            "Contains modified Copernicus Atmosphere Monitoring Service information",
        ],
    }
    payload["receipt"] = products.make_receipt(payload, capability_id="atlas.pv.irradiance.record@v1")
    products.remember_receipt(payload["receipt"])
    payload["receipt_url"], payload["verifier_url"] = products._receipt_links(payload["receipt"])
    return payload


# Imported last on purpose: this code reads products's state, settings and helpers at
# call time (where tests patch them), and either module may load first.
from .. import products as products  # noqa: E402
