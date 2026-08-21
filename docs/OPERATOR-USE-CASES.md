# ATLAS — operator use cases

**Languages:** [EN](OPERATOR-USE-CASES.md) · [RU](i18n/OPERATOR-USE-CASES.ru.md) · [ES](i18n/OPERATOR-USE-CASES.es.md) · [FR](i18n/OPERATOR-USE-CASES.fr.md) · [ZH](i18n/OPERATOR-USE-CASES.zh.md)

ATLAS is the operator **sensor map** plus **ATLAS Analyst**. GAIA attests **readings** from LIVE **relays**; the Hub sells `capability_id`s. This page is how an operator (or an **agent** with a grounded Analyst) asks a physical-world question without substituting a model for a **source**.

Terms: [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md) (EN · RU · ES · FR · ZH). Map/API: [`GUIDE.md`](GUIDE.md). Relays and licences: [`gaia/docs/LIVE-RELAYS.md`](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md). Add a **pin**: [`docs/add-gaia-atlas-sensor.md`](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md).

Audit date: **2026-08-14**. Status labels:

| Status | Meaning |
|--------|---------|
| **Live now** | On the map today. Ask Analyst against these layers. |
| **Proposed — sell** | Licence + HTTPS + geography pinned. The 2026-08-14 six are now **Live now** (need GAIA then ATLAS redeploy). |
| **Hold** | Do **not** sell or show as LIVE until the gap below is closed. |

---

## How to run a question

1. Toggle only the **layers** that can answer it (wildfire is not a **tropical cyclone**).
2. Fly the **viewport** to the licensed geography (Finnish **AIS** is not the North Sea).
3. Click a **pin**. Read `source`, `LIVE`/`SIM`, and `captured_at` / CAP time when present.
4. Ask **ATLAS Analyst** a question that names the layer. The prompt is grounded on the cached fleet snapshot — it must cite pins, not invent a forecast.
5. If you need a standing check, set a **watchbox** (`atlas.watchbox.subscribe@v1`) on that layer + bbox.

GAIA **invoke** never takes buyer lat/lon for operator-anchored devices. Event feeds (FIRMS, quake, CAP) carry coordinates in the **reading**.

---

## Rules for selling and embedding

These are the same commercial filter as LIVE-RELAYS. A use case that fails one row is **Hold**.

| Gate | Pass |
|------|------|
| Licence | CC0 / CC BY / OGL / NLOD / U.S. PD / Copernicus CC BY already used in-repo. Not NC, not “indicative only”, not a helpdesk-only ToS. |
| Embed | HTTPS host on the GAIA **allowlist**; no client URLs; fail-closed → 503, Hub must not debit. |
| Meaning | Answers a question the existing catalog cannot, **or** a geography the existing SKU does not cover. Does not duplicate USGS-as-global under a new name. |
| Honesty | **Warning product** ≠ **in-situ** gauge. Public **AIS** ≠ own-edge AIS. **VIIRS hotspot** ≠ fire perimeter ≠ “disaster”. |

**ATLAS Analyst** may flyTo and open station panels. It must not: order evacuation, call GDACS a FIRMS classifier, treat an empty tsunami CAP as “all clear”, or present Open-Meteo as in-situ.

---

## Live now — ask these today

| Operator / agent question | Layers | What the LIVE **reading** is | Must not claim |
|---------------------------|--------|------------------------------|----------------|
| Where are thermal detections right now? | Wildfire `firms-fire-01` | NASA FIRMS **VIIRS hotspot** cluster. Cite NASA FIRMS. | Fire perimeter, burned area, or “this is a disaster”. |
| Which European fires are in the EFFIS current list? | EFFIS `effis-01` | Copernicus EMS / JRC current fires, **CC BY 4.0**. | A global VIIRS substitute; not FIRMS. |
| Is there a NASA open natural event (volcano, storm, ice, …)? | Natural events `eonet-01` | EONET catalog event. Cite NASA EONET. | NHC storm track; not a **tropical cyclone** advisory. |
| Is the US in a flood / flash-flood CAP? | Flood `nws-flood-01` | NWS **CAP** **flood warning** (U.S. PD). | England / global flood model. GloFAS is not scraped. |
| What is stage/discharge at this river **anchor**? | Rivers | USGS / ECCC / SMHI **in-situ** **reading**. | A **flood warning**. Gage height is not **water quality**. |
| Is there a US tsunami **warning product**? | Tsunami `nws-tsunami-01` | NWS CAP tsunami warning/watch/advisory. Often **empty → offline**. | A tide gauge. Empty is not “no tsunami on Earth”. |
| Is there a Pacific tsunami **warning product**? | Tsunami `ptwc-01` | PTWC Atom. Information-only quake statements are not sold. Empty → offline. | A tide gauge. Empty ≠ all-clear. Analyst must not order evacuation. |
| What is water level at this tide **anchor**? | Tide | NOAA CO-OPS / UHSLC **in-situ**. | A tsunami **warning product**. |
| What ships are in **Finnish waters**? | Public AIS `fintraffic-ais-01` | Fintraffic Digitraffic snapshot, **CC BY 4.0**. | Global AIS, GFW, AISStream, or own-edge `gaia.ais.read@v1`. |
| What ships are off **Norway**? | Public AIS `kystverket-ais-01` | Kystverket via BarentsWatch, **NLOD 2.0**. Needs operator token. | Finnish AIS, global AIS, or merging with Fintraffic into one Europe blob. |
| What aircraft did **our** receiver see? | Edge traffic `feeder-adsb-01` | Own dump1090 ingest. Offline until push. | ADSBx / OpenSky / a public aggregator. |
| What aircraft are over this **anchor** without our receiver? | Public ADS-B `adsb-lol-01` | ADSB.lol **ODbL 1.0** area query (default LHR). Isolate any derived DB. | Own-edge `gaia.adsb.read@v1`. No OpenSky/ADSBx fallback. |
| Did USGS report a quake (typically M≥2.5)? | Earthquakes `usgs-quake-01` | USGS GeoJSON event lat/lon. | Euro-Med density, or a local Australian catalogue. |
| Is Europe denser than USGS M≥2.5? | Earthquakes `emsc-01` | EMSC FDSN, **CC BY 4.0** — cite EMSC. Preliminary. | A USGS replacement. |
| New Zealand local quakes? | Earthquakes `geonet-01` | GeoNet, **CC BY 3.0 NZ**. | A global catalog. |
| Which **tropical cyclone** is active in the Atlantic / East Pacific? | Tropical cyclones `nhc-cyclone-01` | NHC/CPHC CurrentStorms, U.S. PD. Empty season → offline. | JTWC / NW-Pacific typhoon / EONET. |
| Is there a **flood warning** in England? | Flood `ea-flood-01` | EA **OGL** warning product. England only. | “UK flood”, SEPA/NRW, GloFAS, or a Thames **in-situ** stage. |

**Analyst starters (live now)**

- “Toggle Wildfire off everything else. What is the brightest FIRMS **VIIRS hotspot** in this **viewport**? Cite NASA FIRMS.”
- “Is `nws-flood-01` online? If yes, quote the CAP headline. If offline, say the **warning product** is empty — do not infer safety.”
- “Nearest LIVE river **pin** to this click — **reading** only, not a **flood warning**.”
- “Finnish Public AIS: how many vessels in view? Credit Fintraffic. Do not call it global AIS.”
- “NHC active storms in this **viewport** — intensity and lat/lon. Not EONET, not JTWC.”
- “Compare `emsc-01` vs `usgs-quake-01` here. Cite both `source`s; do not pick a winner.”
- “EA flood **warning product** for England. Not a Thames in-situ stage unless the river **pin** is online.”

**watchbox** examples: layer `fire` + bbox; layer `flood` + US or England bbox; layer `ais` + Baltic or Norwegian bbox; layer `cyclone` + Atlantic bbox.

---

## Proposed — sell

The six audited SKUs from 2026-08-14 (NHC cyclone, EMSC, EA flood, PTWC, Kystverket AIS, ADSB.lol) are **wired** — see **Live now** above. They appear on the map after **GAIA then ATLAS** redeploy.

---

## Hold — do not sell yet

### GDACS as “disaster, not a VIIRS point”

**Hold.** The operator question is meaningful, the source is not sellable under our rules yet.

- Official [GDACS Terms of use (March 2025)](https://www.gdacs.org/documents/2025/GDACS_Terms_of_use_Mar_25.pdf) do **not** grant CC BY 4.0. They describe model-based impact estimates, “as is”, and say alerts **must not** be used for decision-making without confirmation from mandated authorities.
- GDACS does **not** classify a FIRMS **VIIRS hotspot**. It is a UN/EC multi-hazard **warning product** / model score for international assistance — a different claim class from thermal detections and from EFFIS.
- Third-party pages that say “CC BY 4.0” are not a pin. Same bar that wired EMSC only after the FDSN page stated CC BY 4.0.

**Live now substitute:** FIRMS (detections) + EFFIS (EU current fires) + EONET (NASA events). Ask Analyst to keep those three `source`s separate.

### Geoscience Australia earthquakes as “is Australia shaking?”

**Hold** for the live HTTPS **relay**, not for the idea.

- data.gov.au “Recent Earthquakes” is **CC BY 3.0 Australia**, but the catalog record is not the same as a pinned, allowlisted GeoJSON/WFS that we have freshness-tested.
- USGS already reports Australian events that meet its magnitude cutoff. That is the honest **Live now** answer.
- Unlock when a GA NEAC machine endpoint is pinned like GeoNet (`api.geonet.org.nz`).

### USGS **water quality** as a separate LIVE SKU

**Hold.** Licence is fine (U.S. PD). Meaning and freshness are not.

- `gage_height_m` on `gaia.river.read@v1` is **not** **water quality**. That distinction stays.
- The modern [USGS Water Data OGC API](https://api.waterdata.usgs.gov/docs/ogcapi/) was documented as **alpha** / not for production workloads at audit time. Legacy IV series at previously tried sites were stale — that is why P2 did not wire WQ.
- Discrete lab samples are not a “now” **reading**.

Unlock only with one operator-anchored site whose continuous parameter (e.g. temperature, dissolved oxygen) is proven fresh, fail-closed when stale.

---

## What Analyst must refuse

| Prompt | Why |
|--------|-----|
| “Declare evacuation / all-clear for this coast.” | ATLAS is not a warning authority. Quote the **warning product** or say offline. |
| “Is this FIRMS pixel a GDACS disaster?” | Different claim classes; GDACS is **Hold**. |
| “Global AIS / global lightning / BoM official AU weather.” | Not licensed for a paid SKU (GFW NC, Blitzortung NC, BoM FTP non-commercial). |
| “Water quality of this English river from USGS.” | Wrong geography and, today, no WQ SKU. |
| “Typhoon from NHC.” | Wrong basin. |

---

## Related

- Operator map: [`GUIDE.md`](GUIDE.md)
- Relay licences: [`gaia/docs/LIVE-RELAYS.md`](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md)
- Glossary (including **watchbox**, **warning product**, **AIS**, **ADS-B**, **tropical cyclone**): [`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)
