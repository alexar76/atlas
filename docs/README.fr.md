# ATLAS

> 🌐 [English](../README.md) · [Русский](README.ru.md) · [Español](README.es.md) · **Français** · [中文](README.zh.md) · [Glossaire](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)


<p align="center">
  <strong>ATLAS</strong> — <strong>carte de capteurs</strong> planétaire sur les relais <a href="https://iot.modelmarket.dev/">GAIA</a><br/>
  Pins honnêtes <strong>LIVE</strong> vs <strong>SIM</strong> · <strong>globe 3D</strong> optionnel · économie d’agents <a href="https://github.com/alexar76">alexar76</a>
</p>

<p align="center">
  <strong><a href="https://atlas.modelmarket.dev/">Carte live</a></strong>
  ·
  <strong><a href="https://alexar76.github.io/atlas/">Landing</a></strong>
  ·
  <strong><a href="https://iot.modelmarket.dev/">GAIA</a></strong>
  ·
  <strong><a href="https://monitor.modelmarket.dev/">Alien Monitor</a></strong>
</p>

**Docs :** [EN](GUIDE.md) · [RU](i18n/GUIDE.ru.md) · [ES](i18n/GUIDE.es.md) · [FR](i18n/GUIDE.fr.md) · [ZH](i18n/GUIDE.zh.md) · **[Légende de la carte](i18n/LEGEND.fr.md)**
**Ajouter un capteur :** [add-gaia-atlas-sensor](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md)

ATLAS est la **carte de capteurs physiques** de l’écosystème : météo, air, marées, rivières, marine, carbone du réseau UK, séismes, **feux**, **radiation**, stations d’**intégrité GNSS**, rapports de **brouillage GNSS**, **AIS finlandais public**, **NWS tsunami CAP**, **ADS-B/AIS** edge optionnel et énergie — depuis les relais [GAIA](https://iot.modelmarket.dev/). Chaque station GNSS est un `point_id` stable ; les agents interrogent via `atlas.point.read@v1` ou un champ signé via `atlas.gnss.degradation.read@v1`. **Les nouveaux appareils open-data s’enregistrent sur GAIA ; couches, pins et watchboxes sont ATLAS**. Pins **LIVE** seulement si GAIA expose une URL de provenance `source` ; sinon **SIM**. Inclut **ATLAS Analyst** (DeepSeek `deepseek-v4-pro` par défaut) avec pare-feu anti prompt-injection et un **brief de l’écosystème** AICOM / AIMarket.

## Galerie

<p align="center"><img src="../docs/screenshots/readme/map.png" alt="ATLAS" width="820"></p>

## Surfaces

| Surface | URL / path |
|---------|------------|
| **Carte publique** | https://atlas.modelmarket.dev/ |
| Landing | https://alexar76.github.io/atlas/ |
| Embed Alien Monitor | `/embed` |
| Health | `/health` |
| Snapshot / viewport / station / watchboxes | `/api/v1/*` |
| Analyst chat | `/api/ai/ask` |

## Démarrage rapide

```bash
pip install aimarket-atlas
export ATLAS_GAIA_URL=https://iot.modelmarket.dev
atlas --host 127.0.0.1 --port 9330
```

## Production

```bash
./scripts/deploy_atlas.sh --remote root@<host>
```

## Comment on paie

Les capacités payantes sont comptabilisées (`ATLAS_PAYMENT_ENFORCED=1`) et il y a deux façons de
les atteindre. Un appelant anonyme dispose d'un quota gratuit — cinq invokes par heure, selon
`X-AIMarket-Sandbox-Visitor` ou son adresse. Qui a besoin de plus détient un **compte de crédit
prépayé** et envoie sa clé dans `X-API-Key` : le prix publié est débité par appel, le quota ne
s'applique plus, et un refus n'est jamais facturé. La réponse payante porte
`X-Atlas-Credit-Charged-Usd` / `-Balance-Usd`, et `-Low: 1` dès que le solde atteint
`ATLAS_CREDITS_LOW_BALANCE_USD` (seuil par défaut 1,00 $) ou moins.

En entier, en cinq langues : [**CREDIT-ACCOUNTS**](i18n/CREDIT-ACCOUNTS.fr.md) ·
[EN](CREDIT-ACCOUNTS.md) · [RU](i18n/CREDIT-ACCOUNTS.ru.md) · [ES](i18n/CREDIT-ACCOUNTS.es.md) ·
[ZH](i18n/CREDIT-ACCOUNTS.zh.md).

## Modèle de charge

| Mécanisme | Rôle |
|-----------|------|
| Cheap fleet poll | Pins seulement |
| Lectures viewport | Capteurs **dans le bbox visible** |
| LIVE vs SIM | `source` présent ⇒ LIVE ; sinon SIM |
| Analyst | Snapshot + pare-feu + retries ; langue = question ∥ UI locale |

Les acheteurs **ne** peuvent **pas** passer lat/lon à l’invoke GAIA.

## Tests

```bash
pip install -e ".[dev]" && pytest -q
```

**624** tests.

## Licence

MIT — [LICENSE](../LICENSE).
