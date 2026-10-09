# ATLAS — cas d’usage opérateur

**Langues :** [EN](../OPERATOR-USE-CASES.md) · [RU](OPERATOR-USE-CASES.ru.md) · [ES](OPERATOR-USE-CASES.es.md) · [FR](OPERATOR-USE-CASES.fr.md) · [ZH](OPERATOR-USE-CASES.zh.md)

ATLAS est la **carte de capteurs** opérateur plus **ATLAS Analyst**. GAIA atteste des **lectures** de **relais** LIVE ; le Hub vend des `capability_id`. Cette page dit comment un opérateur (ou un **agent** ancré sur Analyst) pose une question sur le monde physique sans remplacer un **source** par un modèle.

Termes : [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md). Carte/API : [`GUIDE.fr.md`](GUIDE.fr.md). Relais et licences : [`gaia/docs/LIVE-RELAYS.md`](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md). Ajouter un **pin** : [`docs/add-gaia-atlas-sensor.md`](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md).

Date d’audit : **2026-08-14**. Statuts :

| Statut | Sens |
|--------|------|
| **Live now** | Déjà sur la carte. Interrogez Analyst sur ces **couches**. |
| **Proposed — sell** | Licence + HTTPS + géographie épinglées ; pas encore de code. Vendable comme SKU Hub après Recipe B. |
| **Hold** | Ne pas vendre ni afficher en LIVE tant que le trou ci-dessous n’est pas fermé. |

---

## Comment poser une question

1. N’activez que les **couches** qui peuvent y répondre (wildfire n’est pas un **cyclone tropical**).
2. Placez le **viewport** dans la géographie licenciée (l’**AIS** finlandais n’est pas la mer du Nord).
3. Cliquez un **pin**. Lisez `source`, `LIVE`/`SIM` et `captured_at` / heure CAP s’il y en a.
4. Demandez à **ATLAS Analyst** en nommant la **couche**. Le prompt s’appuie sur l’instantané de flotte — il doit citer des pins, pas inventer une prévision.
5. Pour un contrôle permanent : un **watchbox** (`atlas.watchbox.subscribe@v1`) sur cette couche + bbox.

L’**invoke** GAIA est en général `device_id` seul pour les dispositifs à **ancre** opérateur. Exceptions avec `latitude`/`longitude` acheteur sur le même SKU : Open-Meteo AQ (`om-aq-*`) et Sensor.Community (`sc-01` / `sc-{slug}`). Les flux d’événements (FIRMS, séismes, CAP) portent les coordonnées dans la **lecture**.

---

## Règles pour vendre et intégrer

Même filtre commercial que LIVE-RELAYS. Un cas qui échoue une ligne est **Hold**.

| Porte | Passe |
|-------|-------|
| Licence | CC0 / CC BY / OGL / NLOD / PD États-Unis / Copernicus CC BY déjà utilisés dans le dépôt. Pas NC, pas « indicatif seulement », pas un ToS helpdesk. |
| Intégration | Hôte HTTPS dans l’**allowlist** GAIA ; pas d’URL client ; fail-closed → 503, le Hub ne débite pas. |
| Sens | Répond à une question absente du catalogue, **ou** à une géographie que le SKU actuel ne couvre pas. Ne pas dupliquer USGS mondial sous un autre nom. |
| Honnêteté | **Produit d’alerte** ≠ capteur **in situ**. **AIS** public ≠ AIS edge opérateur. **Hotspot VIIRS** ≠ périmètre d’incendie ≠ « catastrophe ». |

**ATLAS Analyst** peut flyTo et ouvrir des fiches. Il ne doit pas : ordonner une évacuation, traiter GDACS comme classifieur FIRMS, lire un CAP tsunami vide comme « tout va bien », ni présenter Open-Meteo comme in situ.

---

## Live now — poser ces questions aujourd’hui

| Question opérateur / agent | Couches | Qu’est-ce que la **lecture** LIVE | Ne pas affirmer |
|----------------------------|---------|-----------------------------------|-----------------|
| Où sont les détections thermiques maintenant ? | Wildfire `firms-fire-01` | Cluster de **hotspot VIIRS** NASA FIRMS. Citer NASA FIRMS. | Périmètre, surface brûlée ou « c’est une catastrophe ». |
| Quels feux européens sont dans la liste EFFIS courante ? | EFFIS `effis-01` | Feux courants Copernicus EMS / JRC, **CC BY 4.0**. | Substitut VIIRS mondial ; ce n’est pas FIRMS. |
| Y a-t-il un événement naturel ouvert NASA (volcan, tempête, glace, …) ? | Natural events `eonet-01` | Événement catalogue EONET. Citer NASA EONET. | Trajectoire NHC ; pas un avis de **cyclone tropical**. |
| Les États-Unis sont-ils sous CAP crue / flash-flood ? | Flood `nws-flood-01` | **CAP** NWS, **alerte inondation** (PD États-Unis). | Angleterre / modèle de crue mondial. GloFAS n’est pas scrapé. |
| Quel est le niveau/débit à cette **ancre** rivière ? | Rivers | **Lecture** **in situ** USGS / ECCC / SMHI. | Une **alerte inondation**. Gage height n’est pas la **qualité de l’eau**. |
| Quelle est la chimie continue de l’eau dans ce bbox américain ? | Water quality `usgs-wq-01` | Tous les sites USGS actuels du bbox ; pH, température, oxygène dissous et conductivité ; métadonnées provisoires/qualité conservées. | Niveau de rivière, prélèvement labo ou couverture hors USA. |
| Quelle est la référence nationale de radiation EPA et où se trouve une déviation ? | EPA RadNet `radnet-*` | Les 140 coordonnées officielles avec lectures gamma horaires approuvées. | Prévision de dose ou déclaration d’urgence. |
| Quelle jauge DART active est la plus proche de l’événement océanique ? | DART `noaa-dart-01`, `dart-*` | Les 43 stations actives du répertoire NDBC figé, chacune à sa coordonnée officielle. | Alerte tsunami ou ordre d’évacuation. |
| **Ce site nord-américain** est-il dans un polygone de fumée en ce moment ? | `atlas.smoke.operations@v1` | Point-in-polygon exact sur l’inventaire HMS signé complet pour l’**Amérique du Nord** (trous et antiméridien gérés) + PM2.5/AQI au même point. Refus si l’inventaire est tronqué ou hors géographie HMS. | Un ordre d’évacuation, un avis sanitaire, un moniteur réglementaire ou une couverture fumée mondiale. |
| Y a-t-il un **produit d’alerte** tsunami US ? | Tsunami `nws-tsunami-01` | NWS CAP warning/watch/advisory. Souvent **vide → offline**. | Un marégraphe. Vide ≠ « pas de tsunami sur Terre ». |
| Quel est le niveau à cette **ancre** de marée ? | Tide | **In situ** NOAA CO-OPS / UHSLC. | Un **produit d’alerte** tsunami. |
| Quels navires dans les **eaux finlandaises** ? | Public AIS `fintraffic-ais-01` | Instantané Fintraffic Digitraffic, **CC BY 4.0**. | AIS mondial, GFW, AISStream ou `gaia.ais.read@v1` opérateur. |
| Quels aéronefs a vus **notre** récepteur ? | Edge traffic `feeder-adsb-01` | Ingest dump1090 opérateur. Offline tant qu’il n’y a pas de push. | ADSBx / OpenSky / agrégateur public. |
| Quel est le PM crowd près de ce point (ou n’importe quel lat/lon) ? | Air `sc-01` / `sc-{slug}` | Requête d’aire Sensor.Community, **ODbL** — citer. L’acheteur peut passer `latitude`/`longitude` sur `gaia.air.read@v1`. Les pins mesh sont des ancres ville. Zone vide → offline. | Station AQ de référence ; chaque nœud SDS011 sur Terre ; AQ modèle Open-Meteo. |
| USGS a-t-il publié un séisme (typiquement M≥2.5) ? | Earthquakes `usgs-quake-01` | Événement GeoJSON USGS, lat/lon. | Densité euro-méditerranéenne ou catalogue local australien. |
| Séismes locaux en Nouvelle-Zélande ? | Earthquakes `geonet-01` | GeoNet, **CC BY 3.0 NZ**. | Un catalogue mondial. |
| Quel est le débit/niveau du Rhin (clic sur une jauge) ? | Rivers `pegel-*-01` mesh | **PEGELONLINE** WSV in situ (DL-DE-Zero). Un **pin** cliquable par jauge fédérale. | Une **alerte inondation** ; jauges NL/FR. |
| Quel est le **METAR** de cet aéroport (clic sur l’aéroport) ? | Aviation `metar-*-01` mesh | METAR AviationWeather.gov (PD États-Unis). Un **pin** par ICAO. | ASOS terrestre NWS ; prévision **TAF**. |
| Quelle est la **météo routière** sur les routes finlandaises (clic sur une station) ? | Road `fintraffic-road-01` → `road-st-*` | Digitraffic road weather, **CC BY 4.0**. Le parent de cluster déploie des **pins** dans le viewport. | AIS, trafic UE ou NWS. |
| Où sont les trains en Finlande maintenant (clic sur un train) ? | Rail `fintraffic-rail-01` → `rail-tr-*` | Digitraffic train locations, **CC BY 4.0**. | Rail UE ou TMS routier. |
| Où la **sécheresse** est-elle la pire aux É.-U. cette semaine (clic sur un État) ? | Drought `usdm-01` → `drought-st-*` | Stats hebdomadaires d’État du **USDM** — attribuer NDMC / USDA / NOAA / NASA. | Humidité du sol ou alertes NWS. |
| Quels États américains sont en sécheresse cette semaine ? | Drought `usdm-01` | U.S. Drought Monitor — attribuer NDMC / USDA / NOAA / NASA. | Pin d’humidité du sol ; CAP crue. |
| GeoShake a-t-il signalé un événement communautaire ? | Earthquakes `geoshake-01` | Catalogue GeoShake **CC BY 4.0** (vide → offline). | Remplaçant USGS/EMSC. |
| Y a-t-il une alerte CAP publique canadienne ? | Alerts `naad-01` | **NAAD** Atom **CAP-CP** — citer l’émetteur (p. ex. Environnement Canada). Vide ≠ « tout va bien ». | CAP NWS. |
| Comment sont le vent solaire / rayons X GOES / DONKI maintenant ? | Space weather `swpc-*` / `donki-01` | NOAA **SWPC** PD + NASA **DONKI** ouvert. | Évacuation ; substituer par le seul Kp sans nommer la source. |
| Quel est le débit/niveau sur cette jauge d’**Angleterre** (clic sur le pin) ? | Rivers `ea-*-01` mesh | EA Hydrology **in situ** (OGL v3). Préférer les pins avec Q et niveau. | **Alerte** EA (`ea-flood-01`) ; SEPA/NRW ; PEGELONLINE. |
| Quel est le débit/niveau sur le **Rhin/Waal/IJssel NL** (clic Lobith ou Tiel) ? | Rivers `rws-*-01` mesh | Rijkswaterstaat WaterWebservices **in situ** (**CC0**). Lobith/Tiel = Q+niveau ; certains pins niveau seul. | PEGELONLINE DE ; EA Angleterre ; CAP crue. |
| Quelles sont cote et stock de ce réservoir USACE (clic sur le lac) ? | Reservoir `usace-*-01` mesh | USACE CWMS Elev + Stor (PD États-Unis). Deux champs commerciaux par pin. | Un **produit d’alerte** inondation ; le seul stage USGS. |
| Quelle est la météo synoptique en direct en **Irlande** (clic sur une station) ? | Weather `met-ie-01` → `wx-ie-*` | Observations Met Éireann (**CC BY 4.0** — attribution complète). T/RH/vent/pluie/pression. | Open-Meteo comme in situ ; stations UK/NL. |
| Quel est le débit/niveau sur cette jauge de **France** (clic sur le pin) ? | Rivers `hubeau-*-01` mesh | Hub'Eau hydrométrie **in situ** (**Etalab OL 2.0**). Q + niveau quand publié. | **Vigicrues** ; PEGELONLINE DE ; eHYD AT. |
| Quel est le débit/niveau sur cette jauge d’**Autriche** (clic sur le pin) ? | Rivers `ehyd-*-01` mesh | eHYD / BMLUK `pegel_aktuell` **in situ** (**CC BY 4.0** — « Datenquelle: ehyd.gv.at »). | PEGELONLINE DE ; Hub'Eau FR ; CAP crue. |
| Quelle est la météo in situ en **Suède** ? | Weather `smhi-wx-*-01` | SMHI MetObs (**CC BY 4.0**). T/RH/pression/vent. | `smhi-hydro-01` ; Open-Meteo comme in situ. |
| Quelle est la météo in situ à **Singapour** ? | Weather `sg-wx-*-01` | Singapore NEA / data.gov.sg (**Open Data Licence**). Vent (+ T/RH/pluie). | Open-Meteo comme in situ ; PSI comme station. |
| Quel est le **PSI / PM2.5** régional de Singapour ? | Air `sg-psi-*-01` | NEA PSI (**Open Data Licence**). Indice régional 24h. | Moniteur de référence ; OpenAQ. |
| Quelle est la météo in situ à **Hong Kong** ? | Weather `hko-wx-*-01` | HKO `rhrread` (**DATA.GOV.HK**). Température par lieu (+ RH à l’Observatory). | Open-Meteo comme in situ. |
| Quel est le **PM2.5** in situ en **Belgique** ? | Air `be-aq-*-01` | IRCELINE SOS (**CC BY 4.0**). | OpenAQ ; Sensor.Community. |
| Quelle est la météo in situ en **Espagne** ? | Weather `aemet-wx-*-01` | AEMET OpenData (**Fuente: AEMET**). Clé `GAIA_AEMET_API_KEY`. | Open-Meteo comme in situ. |
| Quelle est la météo in situ en **Suisse** ? | Weather `ch-wx-*-01` | MeteoSwiss OGD (**CC BY 4.0**). | Open-Meteo comme in situ. |
| Quel est le débit / niveau géodésique de ce jaugeage **suisse** ? | Rivers `bafu-*-01` | BAFU/FOEN LINDAS (**OGD-CH Open-Use**). Q + m s.n.m. | dangerLevel ; PEGELONLINE ; eHYD ; Hub'Eau. |
| Quelle est la météo in situ à **Taïwan** ? | Weather `cwa-wx-*-01` | CWA OpenData (**OGDL 1.0**). Clé `GAIA_CWA_API_KEY`. | Open-Meteo comme in situ. |
| Quelle est la météo in situ en **France** (station) ? | Weather `mf-wx-*-01` | Météo-France DPObs (**Etalab OL 2.0**). Clé `GAIA_METEOFRANCE_APPLICATION_ID`. | Hub'Eau ; Open-Meteo comme in situ. |
| Quelle est la météo in situ en **Estonie** ? | Weather `ee-wx-*-01` | Estonian Weather Service XML (**CC BY 4.0**). | Open-Meteo comme in situ. |
| Quelle est la météo in situ en **Islande** ? | Weather `is-wx-*-01` | IMO AWS (**ODC-By**). | Open-Meteo comme in situ. |
| Quel est l’**AQHI de Hong Kong** (clic sur le site) ? | Air `hk-aqhi-*-01` | EPD AQHI (**DATA.GOV.HK**). 1–10 / 10+. | PM2.5 ; météo HKO ; IRCELINE. |

### P12 — nouveaux pins LIVE et SKU de terrain

| Question | Pin / SKU | Source et limite de l’affirmation |
|---|---|---|
| Quelle est la météo in situ en **Autriche** ? | `at-wx-*-01` | GeoSphere Austria TAWES, **CC BY 4.0** ; observations, pas une prévision payante. |
| Quelle est la météo in situ en **Lituanie** ? | `lt-wx-*-01` | LHMT Meteo.lt, **CC BY-SA 4.0** ; ne pas utiliser `/forecasts`. |
| Quel est le niveau du Nemunas ou de la Neris ? | `lt-hydro-*-01` | Hydrologie mesurée LHMT, **CC BY-SA 4.0** ; les centimètres sont fournis en mètres. |
| Quelle est la météo in situ en **Lettonie** ? | `lv-wx-*-01` | CSV HVD LVGMC, **CC0-1.0** ; plus de 6 h → offline. |
| Quel est le niveau de la Daugava ou de la Lielupe ? | `lv-hydro-*-01` | Hydrologie LVGMC, **CC0-1.0** ; ce n’est pas une alerte inondation. |
| Y a-t-il une alerte Vigicrues dans ce bassin français ? | `vic-*-01` | VIC WARNING, **Etalab OL 2.0** ; vert/vide ne veut pas dire « tout va bien » et ce n’est pas Hub'Eau. |
| Quelle est l’intensité carbone nationale française de production ? | `rte-grid-01` | RTE éCO2mix, **Etalab OL 2.0** ; production seule, sans importations ni cycle de vie. |
| Quel est le niveau de cette jauge OPW irlandaise ? | `ie-river-*-01` | waterlevel.ie, **CC BY 4.0** ; niveau, pas CAP inondation. |
| Quelle est la météo in situ au **Japon** ? | `jp-wx-*-01` | JMA AMeDAS, Public Data License ; citer JMA, pas une licence de prévision. |
| JMA a-t-il signalé un séisme ? | `jma-quake-01` | `list.json` officiel JMA ; pas p2pquake ni remplacement USGS/EMSC. |
| Quel typhon est actif dans le Pacifique Nord-Ouest ? | `jma-typhoon-01` | JMA targetTc, Public Data License ; saison vide → offline, pas NHC/JTWC. |
| Quelle est la météo in situ en **Tchéquie** ? | `cz-wx-*-01` | ČHMÚ climate-now, **CC BY 4.0** ; pas Open-Meteo comme station. |
| Quelle est la météo in situ en **Corée** ? | `kr-wx-*-01` | KMA ASOS, Public Nuri Type 1 ; requiert `GAIA_KMA_SERVICE_KEY`, pas AirKorea. |
| Y a-t-il une inondation observée par Copernicus ? | `gfm-flood-01` | Copernicus GFM, **CC BY 4.0** ; requiert `GAIA_GFM_TOKEN`, pas la prévision GloFAS. |
| Quel est le consensus robuste des températures Estonia EWS maintenant ? | `atlas.field.consensus@v1`, maillage `ee-wx` | Médiane / biweight de lectures LIVE in situ avec reçu ; ni prévision ni chiffre national officiel. |
| Où est le postérieur GP spatial de l’instantané Estonia EWS actuel ? | `atlas.field.posterior@v1`, maillage `ee-wx` | Le GP RBF interpole les données actuelles avec variance ; ni prévision ni nowcast national. |
| Quelles jauges du Rhin interroger sans choisir celles qui arrangent ? | `atlas.mesh.sample@v1`, maillage `pegel` | Sous-ensemble Halton de PEGELONLINE LIVE ; rejouer avec le même `skip`, ce n’est pas Sortes ECVRF. |
| Le réseau AQ belge s’est-il séparé en grappes ? | `atlas.field.shape@v1`, maillage `be-aq` | Composantes H0 par rayon d’IRCELINE LIVE ; ni AQI ni boucles Betti-1. |

**Amorces Analyst (live now)**

- « Coupe les autres **couches**. Quel est le **hotspot VIIRS** FIRMS le plus lumineux dans ce **viewport** ? Cite NASA FIRMS. »
- « `nws-flood-01` est-il online ? Si oui, cite le titre CAP. Si offline, dis que le **produit d’alerte** est vide — n’infère pas la sécurité. »
- « **Pin** rivière LIVE le plus proche de ce clic — la **lecture** seulement, pas une **alerte inondation**. »
- « AIS public finlandais : combien de navires en vue ? Crédit Fintraffic. Ne l’appelle pas AIS mondial. »

Exemples de **watchbox** : couche `fire` + bbox ; `flood` + bbox US ; `ais` + Baltique.

---

## Proposed — sell (audit 2026-08-14)

Les six SKU audités (NHC, EMSC, EA flood, PTWC, Kystverket AIS, ADSB.lol) **sont câblés** — voir **Live now**. Sur la carte après redéploiement **GAIA, puis ATLAS**.

### 1. « Quel **cyclone tropical** est actif dans l’Atlantique / Pacifique Est ? »

| | |
|--|--|
| **Statut** | Proposed — sell |
| **SKU** | nouveau `gaia.cyclone.read@v1` (ne pas surcharger EONET) |
| **Upstream** | NOAA NHC `CurrentStorms.json` — PD États-Unis |
| **Géographie** | Atlantique + Pacifique Est. Pas le Pacifique Nord-Ouest (typhon / 台风). Bassin NHC : ouragan. |
| **Vendre / intégrer** | Oui. Saison vide → offline / pas de débit, comme le CAP tsunami. |
| **Analyst** | « Liste les tempêtes NHC actives avec lat/lon et intensité. Ce n’est ni EONET ni un flux cyclone mondial. » |
| **Ne pas** | Répondre « typhon près du Japon » depuis NHC. |

### 2. « L’Europe tremble-t-elle plus dense que USGS M≥2.5 ? »

| | |
|--|--|
| **Statut** | Proposed — sell |
| **SKU** | `gaia.quake.read@v1` existant, nouveau `device_id` `emsc-01` |
| **Upstream** | EMSC FDSN `seismicportal.eu` — **CC BY 4.0** ([page du service](https://www.seismicportal.eu/fdsn-wsevent.html)) |
| **Géographie** | Euro-Méditerranée dense ; mondial M≥4.5. Citer EMSC. Paramètres préliminaires. |
| **Vendre / intégrer** | Oui. **Pin** distinct de `usgs-quake-01`. |
| **Analyst** | « Compare EMSC et USGS dans ce **viewport**. Ne désigne pas un vainqueur ; cite les deux `source`. » |
| **Ne pas** | Remplacer USGS au niveau mondial. |

### 3. « Y a-t-il une **alerte inondation** en Angleterre ? »

| | |
|--|--|
| **Statut** | Proposed — sell |
| **SKU** | `gaia.flood.read@v1` existant, nouveau `ea-flood-01` (**ancres** rivière optionnelles sur `gaia.river.read@v1`) |
| **Upstream** | API temps réel Environment Agency — **OGL**, sans clé. Attribution : données EA crue et niveau des rivières. |
| **Géographie** | **Angleterre**, pas le Royaume-Uni (Écosse SEPA / pays de Galles NRW à part). |
| **Vendre / intégrer** | Oui. Complète le CAP NWS US-only. |
| **Analyst** | « **Produit d’alerte** EA pour l’Angleterre. Ce n’est pas un niveau **in situ** de la Tamise sauf si le **pin** rivière est online. » |
| **Ne pas** | Dire « crue UK » ni scraper GloFAS. |

### 4. « Y a-t-il un **produit d’alerte** tsunami Pacifique ? »

| | |
|--|--|
| **Statut** | Proposed — sell |
| **SKU** | `gaia.tsunami.read@v1` existant, nouveau `ptwc-01` |
| **Upstream** | PTWC / Atom ou CAP `tsunami.gov` — PD États-Unis |
| **Géographie** | Pacifique (bassins PTWC). Complète le CAP NWS centré US. |
| **Vendre / intégrer** | Oui. Flux vide → offline. **Produit d’alerte**, pas un marégraphe. |
| **Analyst** | « Cite séparément les pins PTWC et NWS tsunami. Vide ≠ tout va bien. » |
| **Ne pas** | Ordonner une évacuation ; Analyst n’est pas une autorité nationale d’alerte. |

### 5. « Quels navires au large de la Norvège ? »

| | |
|--|--|
| **Statut** | Proposed — sell |
| **SKU** | `gaia.ais.public.read@v1` existant, nouveau `kystverket-ais-01` (ou équivalent) |
| **Upstream** | Kystverket via BarentsWatch — **NLOD**, usage commercial avec attribution. Inscription OpenID gratuite (même classe que `GAIA_KNMI_API_KEY`). |
| **Géographie** | Eaux norvégiennes, pas finlandaises, pas mondiales. |
| **Vendre / intégrer** | Oui, une fois l’hôte REST + jeton épinglés dans l’**allowlist**. |
| **Analyst** | « **AIS** public norvégien. Crédit Kystverket / BarentsWatch. Pas Fintraffic, pas l’AIS edge opérateur. » |
| **Ne pas** | Fusionner avec `fintraffic-ais-01` en un « AIS Europe ». |

### 6. « Quel aéronef au-dessus de ce point — sans notre récepteur ? »

| | |
|--|--|
| **Statut** | Proposed — sell |
| **SKU** | nouveau `gaia.adsb.public.read@v1` (parallèle à l’AIS public ; **pas** `gaia.adsb.read@v1`) |
| **Upstream** | [ADSB.lol](https://www.adsb.lol/docs/open-data/api/) `api.adsb.lol` — **ODbL 1.0** |
| **Géographie** | Couverture du flux, pas un mandat national. |
| **Vendre / intégrer** | Oui, même honnêteté que Sensor.Community : **lecture** commerciale OK ; une base dérivée publique est **ODbL share-alike**. Isoler la BD dérivée ADS-B. Épingler uniquement `api.adsb.lol`. |
| **Analyst** | « ADS-B public via ADSB.lol (ODbL). Pas notre dump1090. Pas OpenSky / ADSBx. » |
| **Ne pas** | Enchaîner en silence les agrégateurs aviation. |

---

## Hold — ne pas vendre encore

### EPA UV comme « desk ops » payant

**Hold du copy use-case** (le relais peut rester LIVE sur la carte).

- Le titre du pin est un seul `uv_index` (max de prévision par ZIP). Échoue la barre : un scalaire ≠ desk multi-signaux.
- C’est une **prévision** horaire EPA, pas un pyranomètre in situ.
- Débloquer quand le pin/cluster vend ≥2 champs utiles sans inventer d’instruments.

**Substitut live now :** météo Met Éireann / NWS / Open-Meteo ; ne pas vendre l’UV seul comme « sécurité de site ».

### GDACS comme « catastrophe, pas un point VIIRS »

**Hold.** La question opérateur a du sens ; la source n’est pas encore vendable selon nos règles.

- Les [GDACS Terms of use (mars 2025)](https://www.gdacs.org/documents/2025/GDACS_Terms_of_use_Mar_25.pdf) officiels **n’accordent pas** CC BY 4.0. Ils décrivent des estimations d’impact par modèle, « as is », et disent que les alertes **ne doivent pas** servir à décider sans confirmation des autorités mandatées.
- GDACS **ne** classe **pas** un **hotspot VIIRS** FIRMS. C’est un **produit d’alerte** multi-aléas / score modèle ONU/CE sur l’aide internationale — une autre classe d’affirmation que les détections thermiques et EFFIS.
- Les pages tierces « CC BY 4.0 » ne sont pas un pin. Même barre qui a laissé EMSC hors code jusqu’à ce que la page FDSN déclare CC BY 4.0.

**Substitut live now :** FIRMS (détections) + EFFIS (feux UE courants) + EONET (événements NASA). Analyst tient ces trois `source` séparés.

### Séismes Geoscience Australia comme « l’Australie tremble-t-elle ? »

**Hold** du **relais** HTTPS live, pas de l’idée.

- « Recent Earthquakes » sur data.gov.au est **CC BY 3.0 Australia**, mais la fiche catalogue ≠ un GeoJSON/WFS allowlisté et testé en fraîcheur.
- USGS signale déjà les événements australiens au-dessus de son seuil de magnitude. C’est la réponse honnête **Live now**.
- Débloquer quand un endpoint GA NEAC est épinglé comme GeoNet (`api.geonet.org.nz`).

### **Qualité de l’eau** USGS — réseau LIVE

La collection OGC courante de mesures continues est connectée : le bbox acheteur renvoie tous les sites correspondants et chacun devient une coordonnée de lecture. Heure, provisional/approval et qualifier sont conservés ; `gage_height_m` reste distinct de la qualité de l’eau. Géographie : États-Unis.

---

## Ce qu’Analyst doit refuser

| Prompt | Pourquoi |
|--------|----------|
| « Déclare l’évacuation / la fin d’alerte sur cette côte. » | ATLAS n’est pas une autorité d’alerte. Citer le **produit d’alerte** ou dire offline. |
| « Ce pixel FIRMS est-il une catastrophe GDACS ? » | Classes d’affirmation distinctes ; GDACS est **Hold**. |
| « AIS mondial / foudre mondiale / météo officielle BoM AU. » | Pas de licence pour un SKU payant (GFW NC, Blitzortung NC, FTP BoM non commercial). |
| « Qualité de l’eau de cette rivière anglaise via USGS. » | Mauvaise géographie : le réseau continu USGS connecté couvre les États-Unis, pas l’Angleterre. |
| « Typhon depuis NHC. » | Mauvais bassin. |

---

## Liens

- Carte opérateur : [`GUIDE.fr.md`](GUIDE.fr.md)
- Licences relais : [`gaia/docs/i18n/LIVE-RELAYS.fr.md`](https://github.com/alexar76/gaia/blob/main/docs/i18n/LIVE-RELAYS.fr.md)
- Glossaire (**watchbox**, **produit d’alerte**, **AIS**, **ADS-B**, **cyclone tropical**) : [`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)
