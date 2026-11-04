# Légende de la carte ATLAS

**Langues:** [EN](../LEGEND.md) · [RU](LEGEND.ru.md) · [ES](LEGEND.es.md) · [FR](LEGEND.fr.md) · [ZH](LEGEND.zh.md)

Cette légende est générée depuis `atlas.stations.LAYER_META` et `STATION_CATALOG` ; ne pas la modifier à la main. Régénération : `python3 scripts/atlas_legend.py --write`.

**Contrat de coordonnées :** un point visible sur la carte correspond à une coordonnée de lecture. Une station fixe utilise sa coordonnée officielle ; une lecture de grille à la demande utilise la cellule source/requête renvoyée. Les flux denses et événementiels sont développés en points enfants à la coordonnée de lecture ou au centre de cellule ; l’objet parent n’est pas tracé comme point en double.

La couleur identifie la couche, pas la gravité ni l’état du capteur. Certaines couches liées partagent volontairement une couleur ; la clé et le filtre de couche les distinguent. Les états LIVE/SIM et la disponibilité sont affichés séparément.

Le catalogue définit actuellement 66 couches et 1042 appareils configurés. Les flux denses et événementiels peuvent créer des points de lecture supplémentaires à l’exécution.

La carte complète propose aussi **Imagerie radar NOAA**, un raster de réflectivité NOAA/NWS MRMS hors du décompte des couches de données. La ligne `radar` indique l’état des stations NEXRAD.

Dans `flood`, `usgs-rtfi-01` indique les sites relevés où le dépassement d’un seuil est provisoire. La couche `groundwater` indique la profondeur sous la surface locale du sol pour trois puits pilotes USGS. Hub’Eau ajoute huit piézomètres français avec leur repère de mesure et des cotes NGF.

| Couleur | Clé de couche | Signification | Exemples de device_id |
|---|---|---|---|
| <span style="color:#bef264">●</span> `#bef264` | `ev_charging` | Recharge électrique | `ndw-ev-charging-01` |
| <span style="color:#f97316">●</span> `#f97316` | `wildfire_perimeters` | Périmètres des feux | `bc-wildfire-01` |
| <span style="color:#fde047">●</span> `#fde047` | `pollen` | Mesures du pollen | `ch-pollen-pbe`, `ch-pollen-pbs`, `ch-pollen-pbu`, `ch-pollen-pcf` +11 |
| <span style="color:#7dd3fc">●</span> `#7dd3fc` | `storm_reports` | Signalements d’orages | `noaa-spc-storm-reports-01` |
| <span style="color:#c4b5fd">●</span> `#c4b5fd` | `volcanic_ash` | Cendres volcaniques | `noaa-vaac-ash-01` |
| <span style="color:#fb923c">●</span> `#fb923c` | `fire_hotspots` | Points chauds d’Australie | `dea-hotspots-01` |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `power_outages` | Coupures de courant | `ukpn-live-faults-01` |
| <span style="color:#67e8f9">●</span> `#67e8f9` | `bridge_clearance` | Tirant d’air sous les ponts | `noaa-airgap-8726371`, `noaa-airgap-8545556`, `noaa-airgap-8575432` |
| <span style="color:#06b6d4">●</span> `#06b6d4` | `ocean_drifters` | Bouées dérivantes | `aoml-drifters-01` |
| <span style="color:#a3e635">●</span> `#a3e635` | `bikeshare` | Vélos en libre-service | `toronto-bikeshare-01` |
| <span style="color:#2dd4bf">●</span> `#2dd4bf` | `ocean_obs` | Observations océaniques | `smhi-ocean-flinten16-8m`, `smhi-ocean-flinten16-2m`, `smhi-ocean-flinten7-8m`, `smhi-ocean-kalmar2-0m` |
| <span style="color:#c084fc">●</span> `#c084fc` | `smoke_forecast` | Prévision de fumée | `eccc-smoke-seattle`, `eccc-smoke-toronto`, `eccc-smoke-calgary` |
| <span style="color:#f472b6">●</span> `#f472b6` | `hf_absorption` | Absorption radio HF | `swpc-drap-01` |
| <span style="color:#3dd6c6">●</span> `#3dd6c6` | `weather` | Météo | `at-wx-wien-01`, `lt-wx-vilnius-01`, `lv-wx-riga-01`, `jp-wx-tokyo-01`, `cz-wx-praha-01`, `kr-wx-seoul-01` +265 |
| <span style="color:#7ec8ff">●</span> `#7ec8ff` | `air` | Air | `hk-aqhi-centralwestern-01`, `sg-psi-central-01`, `be-aq-brussels-01`, `aurn-01` +122 |
| <span style="color:#4ea8de">●</span> `#4ea8de` | `tide` | Marée | `kartverket-tide-bgo`, `geonet-coastal-auct`, `ea-tide-e70039`, `uhslc-01` +29 |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `river` | Rivières | `arso-river-1060`, `chmi-river-042000`, `lt-hydro-kaunas-01`, `lv-hydro-riga-01`, `ie-river-athlone-01` +169 |
| <span style="color:#22d3ee">●</span> `#22d3ee` | `river_forecast` | Prévisions fluviales | `nwps-pttp1`, `nwps-rmdv2`, `nwps-vckm6`, `nwps-dlrt2` |
| <span style="color:#2563eb">●</span> `#2563eb` | `marine` | Marin | `ie-buoy-m2`, `au-wave-apollo-bay`, `fmi-marine-103976`, `cdip-pointreyes-01`, `ndbc-01`, `om-marine-01` +31 |
| <span style="color:#84cc16">●</span> `#84cc16` | `ghg` | GES | `icos-htm-01`, `icos-zsf-01`, `icos-lin-01` |
| <span style="color:#c4a35a">●</span> `#c4a35a` | `grid` | Réseau (carbone) | `rte-grid-01`, `uk-grid-01`, `eia-01` |
| <span style="color:#ff6b4a">●</span> `#ff6b4a` | `quake` | Séismes | `jma-quake-01`, `usgs-quake-01`, `emsc-01`, `geonet-01` +2 |
| <span style="color:#e8b86d">●</span> `#e8b86d` | `energy` | Énergie | `em-01` |
| <span style="color:#f97316">●</span> `#f97316` | `fire` | Incendies | `firms-fire-01` |
| <span style="color:#a3e635">●</span> `#a3e635` | `radiation` | Radiation | `bfs-odl-01`, `safecast-01`, `safecast-tokyo`, `safecast-sf` +11 |
| <span style="color:#e879f9">●</span> `#e879f9` | `jamming` | Brouillage GNSS | `cybernews-jam-01` |
| <span style="color:#34d399">●</span> `#34d399` | `gnss` | Intégrité GNSS | `gnss-euref-01`, `gnss-ga-01` |
| <span style="color:#94a3b8">●</span> `#94a3b8` | `traffic` | Trafic edge | `feeder-adsb-01`, `feeder-ais-01` |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `events` | Événements naturels | `eonet-01` |
| <span style="color:#818cf8">●</span> `#818cf8` | `spacewx` | Météo spatiale | `swpc-01`, `swpc-solarwind-01`, `swpc-xray-01`, `donki-01` |
| <span style="color:#fde047">●</span> `#fde047` | `lightning` | Foudre | `glm-01` |
| <span style="color:#fb7185">●</span> `#fb7185` | `alerts` | Alertes | `nws-alerts-01`, `naad-01` |
| <span style="color:#22d3ee">●</span> `#22d3ee` | `argo` | Flotteurs Argo | `argo-01` |
| <span style="color:#c084fc">●</span> `#c084fc` | `geomag` | Géomagnétisme | `usgs-geomag-01`, `usgs-geomag-brw`, `usgs-geomag-bsl`, `usgs-geomag-cmo` +10 |
| <span style="color:#2dd4bf">●</span> `#2dd4bf` | `iot` | IoT edge | `feeder-iot-01` |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `flood` | Crue | `vic-meuse-01`, `gfm-flood-01`, `nws-flood-01`, `ea-flood-01` +19 |
| <span style="color:#ea580c">●</span> `#ea580c` | `effis` | Feux EFFIS | `effis-01` |
| <span style="color:#ef4444">●</span> `#ef4444` | `volcano` | Volcans | `geonet-volcano-01`, `usgs-volcano-01` |
| <span style="color:#0891b2">●</span> `#0891b2` | `ais` | AIS public | `fintraffic-ais-01`, `kystverket-ais-01` |
| <span style="color:#e11d48">●</span> `#e11d48` | `tsunami` | Alertes tsunami | `nws-tsunami-01`, `ptwc-01` |
| <span style="color:#7c3aed">●</span> `#7c3aed` | `cyclone` | Cyclones tropicaux | `jma-typhoon-01`, `nhc-cyclone-01` |
| <span style="color:#0ea5e9">●</span> `#0ea5e9` | `adsb` | ADS-B public | `adsb-lol-01` |
| <span style="color:#94a3b8">●</span> `#94a3b8` | `smoke` | Fumée | `hms-smoke-01` |
| <span style="color:#06b6d4">●</span> `#06b6d4` | `water_quality` | Qualité de l’eau | `usgs-wq-01` |
| <span style="color:#0d9488">●</span> `#0d9488` | `groundwater` | Eaux souterraines | `usgs-groundwater-01`, `hubeau-groundwater-01` |
| <span style="color:#1d4ed8">●</span> `#1d4ed8` | `dart` | Bouées DART | `dart-21414`, `dart-21415`, `dart-21416`, `dart-21418` +39 |
| <span style="color:#0ea5e9">●</span> `#0ea5e9` | `precipitation` | Précipitations | `imerg-01` |
| <span style="color:#22c55e">●</span> `#22c55e` | `radar` | État NEXRAD | `nexrad-status-01` |
| <span style="color:#a78bfa">●</span> `#a78bfa` | `atmosphere` | Atmosphère | `cams-ottawa`, `cams-berlin`, `cams-delhi`, `cams-tokyo` +2 |
| <span style="color:#84cc16">●</span> `#84cc16` | `radnet` | EPA RadNet | `radnet-ak-anchorage`, `radnet-ak-fairbanks`, `radnet-ak-juneau`, `radnet-birmingham` +136 |
| <span style="color:#a16207">●</span> `#a16207` | `soil` | Humidité du sol | `soil-ottawa`, `soil-berlin`, `soil-delhi`, `soil-tokyo` +2 |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `solar` | Irradiation solaire | `solar-ottawa`, `solar-berlin`, `solar-delhi`, `solar-tokyo` +2 |
| <span style="color:#bae6fd">●</span> `#bae6fd` | `snow` | Manteau neigeux | `snotel-335`, `snow-rainier`, `snow-tahoe`, `snow-mammoth` +4 |
| <span style="color:#67e8f9">●</span> `#67e8f9` | `sea_ice` | Glace de mer | `nsidc-ice-01` |
| <span style="color:#ef4444">●</span> `#ef4444` | `land_temperature` | Température terrestre | `lst-ottawa`, `lst-berlin`, `lst-delhi`, `lst-tokyo` +2 |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `aviation` | METAR aviation | `metar-kjfk-01`, `metar-klga-01`, `metar-kbos-01`, `metar-kord-01` +10 |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `road` | Météo routière | `fintraffic-road-01` |
| <span style="color:#64748b">●</span> `#64748b` | `rail` | Trafic ferroviaire | `entur-rail-vyg-01`, `fintraffic-rail-01` |
| <span style="color:#d97706">●</span> `#d97706` | `drought` | Sécheresse | `usdm-01` |
| <span style="color:#0284c7">●</span> `#0284c7` | `reservoir` | Reservoirs | `usace-keys-01`, `usace-pine-01`, `usace-deni-01`, `usace-huds-01` |
| <span style="color:#facc15">●</span> `#facc15` | `uv` | UV forecast | `epa-uv-01` |
| <span style="color:#fb923c">●</span> `#fb923c` | `road_events` | Avis routiers | `toronto-road-restrictions-01`, `ndw-road-srti-01`, `fintraffic-road-announcements-01`, `fintraffic-roadworks-01` +1 |
| <span style="color:#a78bfa">●</span> `#a78bfa` | `aviation_hazards` | Prévisions de risques aéronautiques | `awc-gairmet-01` |
| <span style="color:#eab308">●</span> `#eab308` | `power_price` | Prix de l'électricité | `smard-price-de-lu`, `smard-price-at`, `smard-price-be`, `smard-price-no2` +11 |
| <span style="color:#10b981">●</span> `#10b981` | `imagery` | Imagerie satellite | `s2-tempelhof`, `s2-wannsee`, `s2-grandcanyon`, `s2-amazon` +1 |
| <span style="color:#f43f5e">●</span> `#f43f5e` | `actuator` | Actionneurs | `plug-sim-01` |
