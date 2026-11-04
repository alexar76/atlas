# ATLAS — guide opérateur et développeur

**Langues :** [EN](../GUIDE.md) · [RU](GUIDE.ru.md) · [ES](GUIDE.es.md) · [FR](GUIDE.fr.md) · [ZH](GUIDE.zh.md)

ATLAS est la **carte de capteurs** de l’écosystème : météo, air, marées, rivières, marin, carbone du réseau britannique, séismes, **incendies**, **radiation**, **brouillage GNSS**, AIS public finlandais, alertes tsunami NWS et ADS-B/AIS edge opérateur optionnel — via les relais [GAIA](https://iot.modelmarket.dev). **Les nouveaux dispositifs open-data vivent sur GAIA ; couches carte, pins et watchboxes sont des surfaces ATLAS** (pas d’UI produit séparée côté GAIA). Nœud **ATLAS** sur [Alien Monitor](https://monitor.modelmarket.dev/) et **ATLAS Analyst** (DeepSeek par défaut). Termes : [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md).

**Add sensor:** [add-gaia-atlas-sensor](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md) (EN · RU · ES · FR · ZH). Catalogue GAIA : [LIVE-RELAYS](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md). **Cas d’usage opérateur** (carte + ATLAS Analyst) : [`OPERATOR-USE-CASES.fr.md`](OPERATOR-USE-CASES.fr.md).

## Surfaces

| URL | Rôle |
|-----|------|
| `/` | Carte MapLibre + couches + liste visible + AI |
| `/embed` | Carte compacte pour iframe Monitor |
| `/health` | Liveness |
| `/api/v1/*` | Snapshot, viewport, fiche station, SSE, **watchboxes** |
| `/api/ai/*` | Fournisseurs + chat ancré sur les données live |

## Modèle de charge

- Fond : **fleet** léger (pins) seulement.
- `POST /api/v1/viewport` — lectures du **bbox visible** ; voisins et catalogue chauffés en arrière-plan (TTL ~45 s), single-flight.
- Clic → `GET /api/v1/stations/{id}` — fiche lisible.
- **ATLAS Analyst :** LIVE SNAPSHOT de **toute** la flotte en cache + brief écosystème.
- Badges **LIVE** / **SIM** non traduits.

**Auto-apprentissage Analyst :** ATLAS SURFACES et `snapshot.capabilities` sont dérivés de `STATION_CATALOG` / `LAYER_META` / watchboxes — un nouvel appareil catalogue entre dans le prompt sans éditer le rôle.

L’acheteur **en général** ne passe pas lat/lon à GAIA invoke. Exceptions sur le même SKU : `om-aq-*` et `sc-*` (Sensor.Community). Séismes / feu / brouillage portent lat/lon dans la lecture.

## Couches

GAIA vend les **lectures** (`gaia.*.read@v1`). ATLAS = **carte** (couches/pins) + **watchboxes**.

La liste actuelle des **53 couches**, leurs couleurs exactes, leur signification
et des exemples d’appareils figure dans la [légende de la carte ATLAS](LEGEND.fr.md).
Elle est générée depuis le même catalogue d’exécution que la carte. Le catalogue
contient actuellement **970 appareils configurés** ; les flux denses et événementiels
peuvent créer des points de lecture supplémentaires à l’exécution.

| Couche | device_id typiques | Notes |
|--------|-------------------|-------|
| Météo | `om-wx-01`, `nws-01`, mesh | + sims |
| Air | `om-aq-01`, `osm-01`, `sta-01`, `sc-01`, `sc-{slug}`, mesh | SC : lat/lon acheteur ; crowd ≠ station |
| Marée | `noaa-tide-01` | |
| Rivière | `usgs-river-01`, `eccc-hydro-01`, `smhi-hydro-01` | USGS / ECCC / SMHI |
| Marin | `ndbc-01`, `om-marine-01` | |
| Réseau | `uk-grid-01` | région |
| Sismique | `usgs-quake-01` | event lat/lon |
| Énergie | `em-01` | simulateur |
| Feu | `firms-fire-01` | NASA FIRMS — citer NASA |
| Radiation | `safecast-01` + ancres | Safecast **CC0** · Hub = 30 jours ; Melbourne/Adelaide archive (grille AU 2014, `captured_at`) |
| Brouillage | `cybernews-jam-01` | CyberNews GNSS **CC BY 4.0** |
| Trafic | `feeder-adsb-01`, `feeder-ais-01` | edge opérateur (`GAIA_FEEDER_*`) |
| AIS public | `fintraffic-ais-01`, `kystverket-ais-01` | Fintraffic CC BY 4.0 (FI) · Kystverket NLOD (NO) — pas un « AIS européen » |
| ADS-B public | `adsb-lol-01` | ADSB.lol ODbL 1.0 — pas edge opérateur, pas OpenSky/ADSBx |
| Tsunami | `nws-tsunami-01`, `ptwc-01` | NWS CAP + PTWC Atom (pas un marégraphe ; vide ≠ tout va bien) |
| Cyclones tropicaux | `nhc-cyclone-01` | NHC/CPHC AL+EP+CP — pas JTWC |
| Qualité de l’eau | `usgs-wq-01` | Observations latest-continuous fraîches (48 h), paginées et jointes à USGS monitoring-locations ; seules stations aux paramètres requis, une station = un point ; Approved/Provisional + qualifiers ; historique persistant et uptime par sondages |
| Eaux souterraines | `usgs-groundwater-01` | Trois puits pilotes de l’USGS dans le Maine, l’État de New York et le Kentucky. Profondeur en mètres sous la surface locale du sol, positive vers le bas. ATLAS affiche l’heure de mesure et le statut de validation USGS. Les observations expirent au bout de 24 heures. |
| Nappes de Hub’Eau | `hubeau-groundwater-01` | Huit piézomètres pilotes français indiquent la profondeur sous le repère de mesure et l’altitude de l’eau en NGF. La fiche indique l’heure du relevé et le repère de chaque valeur. |
| Prévisions fluviales NOAA NWPS | `nwps-pttp1`, `nwps-rmdv2`, `nwps-vckm6`, `nwps-dlrt2` | La fiche indique le niveau maximal parmi les points disponibles de la prévision des prochaines 72 heures, l’heure d’émission et celle du pic. Les hauteurs se rapportent au repère local de la station. |
| Marégraphes de l’Environment Agency | `ea-tide-e70039`, `ea-tide-e72639`, `ea-tide-e70539`, `ea-tide-e70739`, `ea-tide-e73839` | Les stations côtières du Royaume-Uni mesurent le niveau moyen de la mer en mètres au-dessus du repère Ordnance Datum Newlyn (mAOD). |
| Événements routiers Fintraffic | `fintraffic-road-announcements-01`, `fintraffic-roadworks-01` | Les avis et travaux en Finlande indiquent les tronçons concernés et la période de validité publiée. |
| NOAA G-AIRMET | `awc-gairmet-01` | Les polygones et lignes des prévisions aéronautiques américaines indiquent le danger et les heures d’émission et de validité. |
| Alertes et fermetures routières NDW | `ndw-road-srti-01`, `ndw-road-closures-01` | La couche `road_events` affiche les alertes de sécurité routière et les fermetures temporaires aux Pays-Bas avec la géométrie des tronçons concernés. Chaque publication signée expire cinq minutes après sa diffusion. Chaque mesure de circulation a sa propre période de validité. [NDW · CC0 1.0](https://docs.ndw.nu/algemeen/data-gebruiksvoorwaarden/) |
| Bouées de houle du FMI en mer Baltique | `fmi-marine-103976`, `fmi-marine-108126`, `fmi-marine-108499`, `fmi-marine-134220`, `fmi-marine-134221`, `fmi-marine-134246` | Six bouées de la couche `marine` fournissent la hauteur significative des vagues. La fiche indique aussi la période de pic, la direction d’où viennent les vagues et la température de l’eau lorsque ces valeurs ont été mesurées au même moment. L’horodatage marque le début de la mesure des vagues. Les observations expirent au bout de deux heures. [FMI · CC BY 4.0](https://en.ilmatieteenlaitos.fi/download-observations-questions) |
| Enneigement USDA NRCS SNOTEL | `snotel-335`, `snotel-415` | La couche `snow` affiche les mesures horaires de l’épaisseur de neige et de son équivalent en eau en centimètres à Berthoud Summit et Copper Mountain, dans le Colorado. GAIA associe les mesures de la même heure qui ont passé le contrôle automatique de qualité et datent de six heures au plus. [USDA NRCS · domaine public américain](https://catalog.data.gov/dataset/snowpack-telemetry-network-snotel) |
| Observations marines de SMHI | `smhi-ocean-flinten16-8m`, `smhi-ocean-flinten16-2m`, `smhi-ocean-flinten7-8m`, `smhi-ocean-kalmar2-0m` | `ocean_obs` · Quatre séries à des profondeurs définies dans trois stations suédoises. La fiche affiche la salinité en PSU, l’oxygène dissous en mL/L ou la vitesse et la direction du courant selon la station et la profondeur. Les mesures datent de la même heure et restent valables trois heures. [SMHI · CC BY 4.0](https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning) |
| Prévisions de fumée d’ECCC | `eccc-smoke-seattle`, `eccc-smoke-toronto`, `eccc-smoke-calgary` | `smoke_forecast` · Trois mailles du modèle près de Seattle, Toronto et Calgary. La fiche affiche la prévision des PM₂.₅ totales près du sol dans le panache de fumée modélisé, en µg/m³, pour la prochaine heure pleine UTC. Elle indique aussi l’heure du cycle du modèle et l’heure de validité de la prévision. Le cycle peut dater de 18 heures au maximum. [ECCC · MSC End-use Licence](https://eccc-msc.github.io/open-data/licence/readme_en/) |
| NOAA SWPC D-RAP | `swpc-drap-01` | `hf_absorption` · La grille mondiale du modèle indique la fréquence maximale affectée par une absorption de 1 dB dans la région D. La vue globale affiche les maxima en MHz dans 900 mailles de 6° × 12°. En zoomant, on accède aux échantillons d’origine des 8 100 mailles de 2° × 4°. La grille expire au bout de 15 minutes. [NOAA SWPC](https://www.swpc.noaa.gov/products/d-region-absorption-predictions-d-rap) |
| Débit de dose gamma ambiant du BfS | `bfs-odl-01` | `radiation` · Les stations allemandes affichent les débits horaires validés d’équivalent de dose gamma ambiant en nSv/h. La fiche indique la fin de l’heure d’observation. Les mesures expirent au bout de deux heures. [BfS · DL-DE-BY 2.0](https://www.imis.bfs.de/geoportal/resources/sitepolicy.html) |
| Hauteur d’eau côtière de GeoNet | `geonet-coastal-auct`, `geonet-coastal-wlgt`, `geonet-coastal-taut`, `geonet-coastal-gist`, `geonet-coastal-jbtt` | `tide` · Cinq stations néo-zélandaises affichent la hauteur d’eau en mètres au-dessus du capteur de pression local. Les mesures expirent au bout de cinq minutes. [GeoNet · CC BY 3.0 NZ](https://www.geonet.org.nz/policy) |
| Observations fluviales de ČHMÚ | `chmi-river-042000`, `chmi-river-101800`, `chmi-river-200100` | `river` · Trois stations hydrométriques tchèques affichent la hauteur et le débit mesurés à titre provisoire, ainsi que la température de l’eau lorsqu’elle est relevée au même instant. Les mesures expirent au bout de deux heures. [ČHMÚ · CC BY 4.0](https://www.chmi.cz/-/kde-najdu-otev%C5%99en%C3%A1-data-%C4%8Dhm%C3%BA-) |
| Positions ferroviaires d’Entur | `entur-rail-vyg-01` | `rail` · La carte affiche les dernières positions observées des trains Vy en Norvège et leur ligne, si disponible. Les positions expirent à la fin de la validité fixée par le fournisseur ou au bout de cinq minutes, selon la première échéance. [Entur · NLOD](https://developer.entur.no/terms-of-service) |
| Coupures de courant UK Power Networks | `ukpn-live-faults-01` | `power_outages` · Pannes en cours dans la zone desservie par l’opérateur. La fiche indique la zone touchée approximative, le nombre de clients affectés et l’heure estimée de rétablissement lorsque l’opérateur la publie. L’instantané expire au bout de 30 minutes. [UK Power Networks · CC BY 4.0](https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-live-faults) |
| Tirant d’air sous les ponts de NOAA PORTS | `noaa-airgap-8726371`, `noaa-airgap-8545556`, `noaa-airgap-8575432` | `bridge_clearance` · Trois capteurs aux États-Unis indiquent la distance verticale préliminaire, en mètres, entre la surface de l’eau et un point de référence fixe du pont. La fiche affiche l’écart-type de l’échantillon et les indicateurs de la source. Les observations expirent au bout de 18 minutes. Pour décider d’un passage, consultez NOAA PORTS et les cartes marines officielles. [NOAA NOS CO-OPS](https://opendap.co-ops.nos.noaa.gov/erddap/info/IOOS_Air_Gap/index.html) |
| Bouées dérivantes de NOAA AOML | `aoml-drifters-01` | `ocean_drifters` · Les relevés mondiaux indiquent la dernière position observée et la température de surface de la mer de chaque bouée, ainsi que la pression au niveau de la mer lorsqu’elle est transmise. Les observations expirent au bout de six heures. [NOAA AOML / OSMC · CC0 1.0](https://osmc.noaa.gov/erddap/info/OSMC_flattened/index.json) |
| Bike Share Toronto | `toronto-bikeshare-01` | `bikeshare` · Les fiches indiquent les vélos disponibles, les vélos électriques lorsqu’ils sont renseignés, les bornes libres et le statut de la location et du retour. Les relevés expirent au bout de cinq minutes. [City of Toronto · OGL](https://open.toronto.ca/open-data-licence/) |
| Restrictions routières de Toronto | `toronto-road-restrictions-01` | `road_events` · Les avis municipaux indiquent le point ou le tronçon concerné pendant une restriction active, y compris les restrictions récurrentes planifiées. L’instantané de la source expire au bout de 15 minutes. Chaque avis a sa propre période d’activité. [City of Toronto · OGL](https://open.toronto.ca/open-data-licence/) |
| Observations fluviales d’ARSO | `arso-river-1060`, `arso-river-3660`, `arso-river-5078`, `arso-river-8080` | `river` · Quatre stations slovènes indiquent la hauteur provisoire en mètres au-dessus du zéro local et le débit en m³/s. La fiche inclut la température de l’eau lorsqu’elle est relevée au même moment. Les observations expirent au bout de deux heures. [ARSO](https://kazalci.arso.gov.si/en/content/legal-note) |
| Niveaux côtiers de Kartverket | `kartverket-tide-bgo`, `kartverket-tide-osl`, `kartverket-tide-svg`, `kartverket-tide-tos`, `kartverket-tide-trd` | `tide` · Cinq marégraphes norvégiens indiquent le niveau côtier observé en mètres par rapport au référentiel vertical national NN2000. Les observations expirent au bout de deux heures. [Kartverket · CC BY 4.0](https://vannstand.kartverket.no/tideapi_en.html) |
| Points potentiellement inondés | `usgs-rtfi-01` | Le niveau d’une station USGS voisine dépasse le seuil mesuré sur le terrain pour une route, un pont, un bâtiment ou un autre site. C’est un indice provisoire d’inondation possible. Un flux vide indique seulement qu’aucun point couvert ne remplit les critères. |
| DART | `noaa-dart-01`, `dart-*` | Les 43 stations actives du répertoire officiel NDBC figé |
| EPA RadNet | `radnet-*` | Les 140 coordonnées officielles des moniteurs EPA, pas trois villes de démonstration |
| État NEXRAD | `nexrad-status-01` | Chaque site WSR-88D à sa coordonnée ; état, pas réflectivité |
| Grilles/modèles par coordonnée | `imerg-01`, `cams-*`, `soil-*`, `solar-*`, `snow-*`, `nsidc-ice-01`, `lst-*` | `lat`/`lon` acheteur ; ATLAS utilise la coordonnée de cellule source/requête renvoyée |

Les données sur les restrictions routières et les vélos en libre-service de Toronto portent cette mention. « Contains information licensed under the Open Government Licence – Toronto. » [Licence](https://open.toronto.ca/open-data-licence/)

### Recharge, phénomènes dangereux et observations de terrain

| Source | GAIA | ATLAS | Données et limites | Source et conditions |
| --- | --- | --- | --- | --- |
| Recharge NDW DOT-NL | `gaia.ev.charging.read@v1` · `ndw-ev-charging-01` | `ev_charging` | Les sites publics de recharge aux Pays-Bas indiquent le nombre de connecteurs disponibles et leur nombre total, par type et puissance. La requête par défaut couvre Utrecht. Les requêtes régionales couvrent jusqu’à 4 degrés carrés. Les pages du Hub comptent jusqu’à 500 sites et utilisent le jeton de l’instantané pour la suite. Un instantané expire au bout de quatre minutes. | [NDW · CC0 1.0](https://docs.ndw.nu/algemeen/data-gebruiksvoorwaarden/) · [API GeoJSON](https://docs.ndw.nu/en/data-uitwisseling/interface-beschrijvingen/dafne-api/dafne_api_consumer_pull/) |
| Incendies et périmètres de BC Wildfire | `gaia.fire.perimeters.read@v1` · `bc-wildfire-01` | `wildfire_perimeters` | Les incendies actifs en Colombie-Britannique présentent leur état et le dernier périmètre publié lorsqu’il est disponible. L’heure de mise à jour du jeu et la date de chaque périmètre sont distinctes. L’instantané expire au bout d’une heure. | [BC Wildfire Service · OGL–BC 2.0](https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc) · [Périmètres](https://open.canada.ca/data/dataset/cdfc2d7b-c046-4bf0-90ac-4897232619e1) |
| Pollen mesuré de MétéoSuisse A7 | `gaia.pollen.read@v1` · `ch-pollen-*` | `pollen` | Quinze stations automatiques enregistrées mesurent les concentrations horaires de sept types de pollen en grains par mètre cube. Une valeur mesurée de zéro est conservée. Les observations expirent au bout de deux heures. | [Source: MeteoSwiss · CC BY 4.0](https://opendatadocs.meteoswiss.ch/general/terms-of-use) · [A7](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a7-pollen-stations) |
| Réseau irlandais de bouées météorologiques | `gaia.marine.read@v1` · `ie-buoy-m2`, `ie-buoy-m3`, `ie-buoy-m5`, `ie-buoy-m6` | `marine` | Quatre bouées pilotes mesurent la hauteur, la période et la direction des vagues, avec la température de l’eau et le vent lorsqu’ils sont disponibles. Les observations expirent au bout de deux heures. Le code qualité 0 indique une qualité inconnue et le code 1 une bonne qualité. | [Marine Institute and Met Éireann · CC BY 4.0](https://erddap.marine.ie/erddap/info/IWBNetwork/index.html) |
| Bouées houlographiques australiennes AODN/IMOS | `gaia.marine.read@v1` · `au-wave-apollo-bay`, `au-wave-wilsons-prom`, `au-wave-wooli` | `marine` | Trois bouées pilotes indiquent la hauteur significative des vagues, leur période de pic et leur direction de provenance lorsque ces données sont disponibles. GAIA accepte le code qualité 1. Les observations expirent au bout de deux heures. | [AODN / IMOS · CC BY 4.0](https://registry.opendata.aws/aodn_wave_buoy_realtime_nonqc/) |
| Volcans et caméras GeoNet | `gaia.volcano.read@v1` · `geonet-volcano-01` | `volcano` | Douze volcans néo-zélandais affichent leur niveau d’alerte actuel et leur code couleur pour l’aviation. Le statut expire 30 minutes après sa récupération. Les miniatures disponibles portent leur propre heure de prise de vue et expirent au bout de 30 minutes. | [GeoNet / Earth Sciences New Zealand and sponsors · CC BY 3.0 NZ](https://www.geonet.org.nz/policy) · [Caméras](https://doi.org/10.21420/vq6s-w222) |
| Signalements locaux d’orages NOAA SPC | `gaia.storm.reports.read@v1` · `noaa-spc-storm-reports-01` | `storm_reports` | Les signalements préliminaires de tornades, de grêle et de vents violents aux États-Unis sont affichés sur une fenêtre glissante de 24 heures. Chaque point indique l’heure du phénomène signalée par la source. | [NOAA/NWS SPC · U.S. public domain](https://www.weather.gov/disclaimer) · [CSV](https://www.spc.noaa.gov/climo/reports/today.csv) |
| Avis de cendres volcaniques du VAAC de Washington | `gaia.volcanic.ash.read@v1` · `noaa-vaac-ash-01` | `volcanic_ash` | Les polygones publiés indiquent leurs limites d’altitude, l’heure d’émission et l’heure d’observation ou de validité de la prévision. L’avis expire à l’heure du prochain avis ou sept heures après son émission si cette échéance arrive plus tôt. | [NOAA Washington VAAC](https://ospo.noaa.gov/products/atmosphere/vaac/messages.html) · [Conditions de NOAA](https://www.noaa.gov/office-education/outreach-communication/faq) |
| Points chauds de Digital Earth Australia | `gaia.fire.hotspots.read@v1` · `dea-hotspots-01` | `fire_hotspots` | Les détections thermiques par satellite en Australie, dont celles de Himawari-9, sont affichées dans la zone demandée sur les trois dernières heures. La carte charge jusqu’à 800 détections et signale une couverture incomplète. | [Geoscience Australia · CC BY 4.0](https://knowledge.dea.ga.gov.au/data/product/dea-hotspots/) · [Jeu de données DEA Hotspots](https://pid.geoscience.gov.au/dataset/ga/111881) |

Les données de Colombie-Britannique portent la mention « Contains information licensed under the Open Government Licence – British Columbia. ». Les données des bouées australiennes portent la mention « Data was sourced from Australia’s Integrated Marine Observing System (IMOS) - IMOS is enabled by the National Collaborative Research Infrastructure Strategy (NCRIS) ».

Sur la carte complète, le bouton **Imagerie radar NOAA** affiche le raster de réflectivité de base NOAA/NWS MRMS pour les États-Unis continentaux, l’Alaska, Hawaï, les Caraïbes et Guam. ATLAS affiche une fenêtre UTC de 10 minutes qui se termine à la dernière heure publiée et masque la mosaïque lorsque cette heure remonte à plus de 20 minutes. Les couleurs suivent la palette de réflectivité de la source. **État NEXRAD** est la couche distincte dédiée à l’état des stations. [Service d’images NOAA](https://mapservices.weather.noaa.gov/eventdriven/rest/services/radar/radar_base_reflectivity_time/ImageServer) · [Politique de données du NWS](https://www.weather.gov/disclaimer)

## Watchboxes (`atlas.watchbox.subscribe@v1` + `atlas.watchbox.check@v1`)

Un **watchbox** est un « cadre de veille » enregistré : bbox (west/south/east/north)
+ filtre de couches carte. Idée : « préviens-moi quand quelque chose de LIVE apparaît
dans ce rectangle sur ces couches » — ce n’est pas une lecture device GAIA.

- **Subscribe** (REST / `atlas.watchbox.subscribe@v1`) — créer/lister/supprimer le
  cadre (plumbing ; pas le SKU facturable Hub).
- **Check** (`atlas.watchbox.check@v1`) — évaluer le cadre contre le snapshot de
  flotte : matches + content receipt. Produit facturable Hub (bbox éphémère +
  couches sans id sauvé aussi possible).

Uniquement couches librement commercialisables (`ALLOWED_WATCHBOX_LAYERS`). Peer :
`/.well-known/ai-market.json`.

- `GET`/`POST /api/v1/watchboxes`
- `GET`/`DELETE /api/v1/watchboxes/{id}`
- `POST /api/v1/watchboxes/{id}/check`

Exemples curl : [EN](../GUIDE.md#watchboxes-atlaswatchboxsubscribev1--atlaswatchboxcheckv1).

## Produits composites (ATLAS > parties)

| SKU | Rôle | Convenience | Hub invoke |
|-----|------|-------------|------------|
| `atlas.situation.brief@v1` | Brief multi-couches scoré pour un bbox — couches carte par défaut (flood, EFFIS, lightning, volcano, AIS public, tsunami…) ; refuse si vide | `POST /api/v1/products/situation-brief` | `POST /ai-market/v2/invoke` |
| `atlas.fire.weather@v1` | FIRMS **et/ou** Copernicus EFFIS dans le bbox + météo LIVE proche (deux listes ; pas un pronostic) | `POST /api/v1/products/fire-weather` | same |
| `atlas.smoke.operations@v1` | `lat`/`lon` du site → **point-in-polygon** sur la géométrie de fumée NOAA HMS signée complète (anneaux **et** trous, sûr à l’antiméridien) + PM2.5/AQI au même point ; refus si l’inventaire HMS est tronqué ou l’air manquant. Analyse qualitative, ni PM2.5 mesuré ni ordre d’évacuation | `POST /api/v1/products/smoke-operations` | same |
| `atlas.nearest.read@v1` | Pin LIVE le plus proche du `lat`/`lon` acheteur (couche, `max_km`, reçu) | `POST /api/v1/products/nearest` | same |
| `atlas.watchbox.check@v1` | Évalue watchbox sauvé ou éphémère → matches + reçu | watchbox `…/check` | same |
| `atlas.mesh.sample@v1` | Échantillon Halton de pins LIVE d’un maillage in-situ licencié (`ee-wx`, `pegel`, …). Sibling `lattice.sequence@v1`. Pas ECVRF (Sortes est un hop frère), pas Open-Meteo | `POST /api/v1/products/mesh-sample` | same |
| `atlas.field.consensus@v1` | Consensus (équivalent Murmuration) de lectures LIVE in-situ (min. 3). Pas une prévision, pas Open-Meteo-comme-station | `POST /api/v1/products/field-consensus` | same |
| `atlas.field.posterior@v1` | GP RBF spatial du snapshot LIVE **courant**. Interpole maintenant ; pas une prévision. Sibling `gauss.field@v1` | `POST /api/v1/products/field-posterior` | same |
| `atlas.field.shape@v1` | Persistance H0 des pins LIVE (composantes vs rayon). Pas Betti-1, pas un AQI. Sibling `betti.homology@v1` | `POST /api/v1/products/field-shape` | same |

Fail-closed sans LIVE. FIRMS : citer NASA. **Nearest** utilise l’index carte ATLAS
(lectures GAIA restent `device_id`). Textes UI Hub :
`aimarket-hub/cap-descriptions-i18n.json` (EN · RU · ES · FR · ZH). Catalogue après
crawl fédération.

## API (court)

- `GET /api/v1/snapshot` — pins + cache
- `POST /api/v1/viewport` — `{west,south,east,north,force?}`
- `GET /api/v1/stations/{id}` — title / summary / metrics ; un pin dont le flux a tourné renvoie une fiche « cleared from the live window », pas un 404
- `POST /api/v1/refresh` — jeton opérateur requis (`X-Atlas-Token`) : un appel relit tout le catalogue
- `POST /api/ai/ask` — analyse et **rapport** (`report: true`)

Prod LLM : **`DEEPSEEK_API_KEY`**, modèle `deepseek-v4-pro`.

## Alien Monitor

`ALIEN_ATLAS_URL` / `ALIEN_PUBLIC_ATLAS_URL` (défaut `https://atlas.modelmarket.dev`). Panneau : capteurs + iframe `/embed` + « Open full map ».

## Déploiement

```bash
docker compose -f atlas/docker-compose.local.yml up -d --build
export DEEPSEEK_API_KEY=sk-...
docker compose -f atlas/docker-compose.yml up -d --build
```

Loopback seul `127.0.0.1:9330` — TLS via nginx.

## Tests

```bash
cd atlas && pip install -e ".[dev]"
pytest -q
```

Sans GAIA live (mocks). Détail env/API : [EN](../GUIDE.md).

## Honnêteté

ATLAS = carte + **ATLAS Analyst** + watchboxes sur relais GAIA. Open-Meteo : CC BY 4.0 ; NWS/USGS/NOAA : domaine public US ; FIRMS : citer NASA ; Safecast : CC0 ; CyberNews : CC BY 4.0.
