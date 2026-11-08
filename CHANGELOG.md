# Changelog

All notable changes to this project are documented in this file. Earlier releases: the git history.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-11-08

### Added

- Map layers and station lists for the open data sources GAIA added on 2026-11-04 (see GAIA 0.3.0): rivers,
  groundwater, coastal water and tides, waves and drifting buoys, snow, gamma dose, smoke, HF absorption, road and
  rail notices, power faults, charge points and wildfire observations. The ecosystem context and layer counts list
  them.
- Irish buoy measurements carry their labels.
- DEA brightness temperature is credited to its source.

### Changed

- Viewports whose stations moved were refreshed, and VAAC ash-advisory altitudes say what they measure.

### Fixed

- **`import atlas.main` works from a pip install.** The mesh and extra-sensor modules read
  `atlas/config/*.yaml` from the repository layout only. An installed package has no such folder, so the import
  failed (aimarket-atlas 0.3.5 and earlier). The wheel now carries the three catalogs in `atlas/_config/`, and
  the modules read that copy when the repository's is absent.
  `./scripts/sync_physical_sensor_catalogs.sh` and `scripts/add_gaia_atlas_sensor.py` keep the copy equal to
  `gaia/config/`, and `tests/test_packaged_sensor_catalogs.py` checks it.

## [0.3.5] - 2026-11-03

### Changed

- The ecosystem context lists SYMMARTYS as published (aimarket-symmartys 0.5.0 on PyPI since 2026-10-29) instead of "local source; GitHub publication pending".

## [0.3.4] - 2026-10-29

### Changed

- The ecosystem context names SYMMARTYS, formerly EMPORION (public-record facts for agents that trade), with its source marked local until the GitHub publication.

## [0.3.3] - 2026-10-28

### Security

- `X-Real-IP` / `X-Forwarded-For` were taken from any private, loopback or link-local peer, so a neighbour on the same docker network or LAN could name its own address and get a fresh rate-limit bucket per request. They now count only from `ATLAS_TRUSTED_PROXIES`: addresses, CIDRs, host names (looked up again every minute) and `gateway` (the container's default route, i.e. the host's nginx for a published port); the default is loopback only. The same flaw Vulnetix reported in three sibling packages (GCVE-110-VULN-PYPI-2026-000636 to 000638); the compose file trusts `gateway`.
- The `atlas` command bound `0.0.0.0` by default; it binds `127.0.0.1` unless `ATLAS_HOST` says otherwise. The image sets `ATLAS_HOST=0.0.0.0` for the container, whose port is published on the host's loopback.
