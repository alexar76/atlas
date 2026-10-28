# Changelog

All notable changes to this project are documented in this file. Earlier releases: the git history.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.3] - 2026-10-28

### Security

- `X-Real-IP` / `X-Forwarded-For` were taken from any private, loopback or link-local peer, so a neighbour on the same docker network or LAN could name its own address and get a fresh rate-limit bucket per request. They now count only from `ATLAS_TRUSTED_PROXIES`: addresses, CIDRs, host names (looked up again every minute) and `gateway` (the container's default route, i.e. the host's nginx for a published port); the default is loopback only. The same flaw Vulnetix reported in three sibling packages (GCVE-110-VULN-PYPI-2026-000636 to 000638); the compose file trusts `gateway`.
- The `atlas` command bound `0.0.0.0` by default; it binds `127.0.0.1` unless `ATLAS_HOST` says otherwise. The image sets `ATLAS_HOST=0.0.0.0` for the container, whose port is published on the host's loopback.
