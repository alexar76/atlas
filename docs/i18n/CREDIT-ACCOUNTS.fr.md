# ATLAS — comptes de crédit prépayés

**Langues :** [EN](../CREDIT-ACCOUNTS.md) · [RU](CREDIT-ACCOUNTS.ru.md) · [ES](CREDIT-ACCOUNTS.es.md) · [FR](CREDIT-ACCOUNTS.fr.md) · [ZH](CREDIT-ACCOUNTS.zh.md)

ATLAS comptabilise ses capacités payantes (`ATLAS_PAYMENT_ENFORCED=1`) et publie une grille de
prix. Pendant longtemps, la boutique n'avait pas de caisse : le quota gratuit était le plafond
pour **tout le monde**, et le 402 renvoyait vers un payment channel d'un Hub — ce qui n'aide pas,
car l'appel du Hub vers ATLAS tombe sur ce même quota anonyme. Mesuré le 2026-09-12 : quatre
cite-desks vendant des abonnements mensuels étaient plafonnés à cinq exécutions par heure pour
l'ensemble de leurs clients.

Un **compte de crédit** est l'entrée payante. Il est prépayé, émis par l'opérateur, débité du prix
publié par appel, exempté du quota gratuit, et jamais facturé pour un refus.

## Deux façons d'atteindre une capacité payante

| | Quota gratuit | Compte de crédit |
|---|---|---|
| Identification | `X-AIMarket-Sandbox-Visitor` ou l'adresse de l'appelant | `X-API-Key: atls_…` |
| Plafond | `max_per_caller` par `quota_window` (5 par heure par défaut) | le solde |
| Coût | rien | le `price_per_call_usd` publié |
| Une fois épuisé | `402` avec la grille de prix | `402` nommant le solde et le montant requis |
| Destiné à | essayer ATLAS | tout ce qui revend la réponse ou en dépend |

Un `402` est écrit pour débloquer l'appelant, pas seulement pour lui dire qu'il est bloqué :
il porte `price_per_call_usd`, un bloc `free_allowance` (`max`, `used`, `quota_window`,
`renews`), un bloc `credit` quand le rail est actif, et `how_to_continue` sous forme de liste
ordonnée de ce qui marcherait.

Une clé non reconnue n'est **pas** une erreur : l'appel retombe sur le quota gratuit, le bloc
`credit` du 402 indique `recognized: false`, et l'opérateur reçoit une ligne de log. Une faute de
frappe dans la configuration d'un desk ne doit pas ressembler à une panne — mais pas non plus à
une réussite.

## Pour l'acheteur

Envoyez la clé et lisez ce que la réponse vous a coûté :

```bash
curl -sD /dev/stderr -X POST https://atlas.modelmarket.dev/ai-market/v2/invoke \
  -H 'X-API-Key: atls_…' -H 'Content-Type: application/json' \
  -d '{"capability_id":"atlas.watchbox.check@v1","input":{"west":-1.0,"south":51.3,"east":0.2,"north":51.6,"layers":["flood"]}}'
```

| En-tête de réponse | Signification |
|---|---|
| `X-Atlas-Credit-Charged-Usd` | Ce que cet appel a coûté. `0.000000` en cas de refus |
| `X-Atlas-Credit-Balance-Usd` | Ce qu'il reste après |
| `X-Atlas-Credit-Low` | `1` dès que le solde atteint `ATLAS_CREDITS_LOW_BALANCE_USD` ou moins |

Ils arrivent sur la réponse de l'appel qui a dépensé l'argent : surveiller un solde ne coûte donc
aucune requête supplémentaire. Un appel non facturé n'en porte aucun — leur absence signifie « non
débité », jamais « zéro ».

Le compte se lit aussi directement. Il répond `404` pour une clé inconnue comme pour une clé
désactivée : il ne permet donc pas de découvrir quelles clés existent :

```bash
curl -s https://atlas.modelmarket.dev/ai-market/v2/accounts/me -H 'X-API-Key: atls_…'
```

Un acheteur qui tourne sans surveillance doit traiter `X-Atlas-Credit-Low` comme le moment d'agir.
Quand un `402` arrive, le travail de son propre client a déjà échoué.

## Pour l'opérateur

```bash
# Émettre un compte. Fonctionne avant l'activation du rail, pour distribuer les clés d'abord.
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"label":"acme","grant_usd":25}'        # api_key n'est renvoyée QU'UNE fois

# Recharger. Idempotent sur `reference` : une même facture ne peut pas être créditée deux fois.
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts/<id>/topup \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"amount_usd":25,"reference":"inv-1043"}'

# Suspendre un compte sans supprimer son historique.
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts/<id>/status \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -d '{"status":"disabled"}'

# Combien d'argent d'autrui l'opérateur détient au total.
curl -s https://atlas.modelmarket.dev/ai-market/v2/credits/stats \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN"
```

Seul le hachage de la clé est conservé. Elle est affichée une seule fois, à la création, et ne peut
pas être récupérée — émettez-en une nouvelle.

| Commutateur | Défaut | Rôle |
|---|---|---|
| `ATLAS_PAYMENT_ENFORCED` | off | Active la comptabilisation des capacités payantes |
| `ATLAS_CREDITS_ENABLED` | off | Accepte les clés de crédit. Les comptes se créent avant |
| `ATLAS_CREDITS_DB_PATH` | `data/atlas_credits.db` | Le registre. Sur un volume monté |
| `ATLAS_CREDITS_LOW_BALANCE_USD` | `1.00` | Seuil de solde bas. `0` le désactive |

**L'ordre compte.** Activez `ATLAS_CREDITS_ENABLED=1` **après** que les comptes existent et que les
clés sont entre les mains des acheteurs. Dans l'autre sens, chaque acheteur dont la clé n'a pas
encore été remise retombe sur le quota anonyme au moment précis où le paiement devient attendu.

L'opérateur est également averti dans le log, au plus une fois toutes les dix minutes par compte,
lorsqu'un solde passe sous le seuil. Le compte est exprimé en appels restants, pas seulement en
dollars : ce qui dit combien de temps il reste pour réagir, c'est « environ 7 appels », pas
« 0,42 $ ».

## Ce qui arrive exactement à l'argent

- **Réservé avant le travail, réglé après.** L'appel pose un `hold`, la livraison le `capture`.
  Débiter d'abord et rembourser ensuite reviendrait à facturer un plantage.
- **Un refus n'est jamais facturé.** Une réponse `ok: false` motivée libère la réserve. Une flotte
  de capteurs froide ne coûte rien.
- **L'unité n'est pas le centime entier.** Les soldes sont tenus en millicentimes : 0,02 $ publiés
  sont débités exactement comme 0,02 $, sans arrondi en faveur de quiconque.
- **Une requête plantée ne gèle pas d'argent.** Une réserve de plus de dix minutes est libérée par
  un balayage : un processus tué ne coûte rien à son propriétaire.
- **Un registre illisible refuse l'appel.** C'est l'inverse du compteur du quota gratuit, qui
  échoue ouvert à dessein : servir un essai en trop est une erreur d'arrondi, tandis que servir un
  produit payant sans l'enregistrer, c'est l'argent d'autrui.
- **Un registre éphémère empêche le démarrage.** Si `ATLAS_CREDITS_DB_PATH` ne survit pas à un
  redéploiement, ATLAS s'arrête plutôt que d'accepter du prépayé dans un fichier qu'il va effacer.

Un solde prépayé, c'est de la **garde de fonds** : l'argent d'autrui détenu par l'opérateur, et
qui vaut ce que vaut sa parole. Il n'y a derrière ni séquestre on-chain ni remboursement
automatique — c'est la limite honnête de ce rail, et c'est pourquoi les règles du registre
ci-dessus ne se négocient pas.

## Qui lit quoi

Le manifest et le 402 annoncent tous deux le rail (`credits.enabled`, `key_header`,
`account_url`) : un acheteur peut donc le découvrir seul. Les desks de la famille cite-desk lisent
les en-têtes de réponse et les republient dans leur propre `/api/public/health` sous
`supply.credit`, avec le vendeur auquel le solde appartient : un desk achète à plusieurs, et un
compte sain chez ATLAS ne prouve pas que l'autre est approvisionné.
