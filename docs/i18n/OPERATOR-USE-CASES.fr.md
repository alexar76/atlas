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

L’**invoke** GAIA n’accepte pas de lat/lon acheteur pour les dispositifs à **ancre** opérateur. Les flux d’événements (FIRMS, séismes, CAP) portent les coordonnées dans la **lecture**.

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
| Y a-t-il un **produit d’alerte** tsunami US ? | Tsunami `nws-tsunami-01` | NWS CAP warning/watch/advisory. Souvent **vide → offline**. | Un marégraphe. Vide ≠ « pas de tsunami sur Terre ». |
| Quel est le niveau à cette **ancre** de marée ? | Tide | **In situ** NOAA CO-OPS / UHSLC. | Un **produit d’alerte** tsunami. |
| Quels navires dans les **eaux finlandaises** ? | Public AIS `fintraffic-ais-01` | Instantané Fintraffic Digitraffic, **CC BY 4.0**. | AIS mondial, GFW, AISStream ou `gaia.ais.read@v1` opérateur. |
| Quels aéronefs a vus **notre** récepteur ? | Edge traffic `feeder-adsb-01` | Ingest dump1090 opérateur. Offline tant qu’il n’y a pas de push. | ADSBx / OpenSky / agrégateur public. |
| USGS a-t-il publié un séisme (typiquement M≥2.5) ? | Earthquakes `usgs-quake-01` | Événement GeoJSON USGS, lat/lon. | Densité euro-méditerranéenne ou catalogue local australien. |
| Séismes locaux en Nouvelle-Zélande ? | Earthquakes `geonet-01` | GeoNet, **CC BY 3.0 NZ**. | Un catalogue mondial. |

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

### **Qualité de l’eau** USGS comme SKU LIVE distinct

**Hold.** Licence OK (PD États-Unis). Sens et fraîcheur, non.

- `gage_height_m` sur `gaia.river.read@v1` **n’est pas** la **qualité de l’eau**. Cette distinction reste.
- L’[USGS Water Data OGC API](https://api.waterdata.usgs.gov/docs/ogcapi/) moderne était documentée **alpha** / pas pour la production à l’audit. Les séries IV héritées sur des sites d’essai étaient périmées — d’où l’absence de WQ en P2.
- Les prélèvements labo discrets ne sont pas une **lecture** « maintenant ».

Débloquer seulement avec une **ancre** opérateur dont un paramètre continu (température, oxygène dissous) est prouvé frais ; fail-closed s’il est périmé.

---

## Ce qu’Analyst doit refuser

| Prompt | Pourquoi |
|--------|----------|
| « Déclare l’évacuation / la fin d’alerte sur cette côte. » | ATLAS n’est pas une autorité d’alerte. Citer le **produit d’alerte** ou dire offline. |
| « Ce pixel FIRMS est-il une catastrophe GDACS ? » | Classes d’affirmation distinctes ; GDACS est **Hold**. |
| « AIS mondial / foudre mondiale / météo officielle BoM AU. » | Pas de licence pour un SKU payant (GFW NC, Blitzortung NC, FTP BoM non commercial). |
| « Qualité de l’eau de cette rivière anglaise via USGS. » | Mauvaise géographie et, aujourd’hui, pas de SKU WQ. |
| « Typhon depuis NHC. » | Mauvais bassin. |

---

## Liens

- Carte opérateur : [`GUIDE.fr.md`](GUIDE.fr.md)
- Licences relais : [`gaia/docs/i18n/LIVE-RELAYS.fr.md`](https://github.com/alexar76/gaia/blob/main/docs/i18n/LIVE-RELAYS.fr.md)
- Glossaire (**watchbox**, **produit d’alerte**, **AIS**, **ADS-B**, **cyclone tropical**) : [`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)
