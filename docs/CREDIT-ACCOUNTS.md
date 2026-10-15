# ATLAS — prepaid credit accounts

**Languages:** [EN](CREDIT-ACCOUNTS.md) · [RU](i18n/CREDIT-ACCOUNTS.ru.md) · [ES](i18n/CREDIT-ACCOUNTS.es.md) · [FR](i18n/CREDIT-ACCOUNTS.fr.md) · [ZH](i18n/CREDIT-ACCOUNTS.zh.md)

ATLAS meters its priced capabilities (`ATLAS_PAYMENT_ENFORCED=1`) and publishes a price list.
For a long time that was only half a shop: the free allowance was the ceiling for **everyone**,
and the 402 pointed at a payment channel on a hub — which does not help, because the hub's own
call to ATLAS lands on the same anonymous allowance. Measured 2026-09-12: four cite-desks
selling monthly plans were capped at five runs an hour between all of their customers.

A **credit account** is the paid entrance. It is prepaid, issued by the operator, charged the
published price per call, exempt from the allowance, and never billed for a refusal.

## Two ways to reach a priced capability

| | Free allowance | Credit account |
|---|---|---|
| Identified by | `X-AIMarket-Sandbox-Visitor`, or the caller's address | `X-API-Key: atls_…` |
| Ceiling | `max_per_caller` per `quota_window` (default 5 per hour) | the balance |
| Cost | nothing | the published `price_per_call_usd` |
| When it is empty | `402` with the price list | `402` naming the balance and what was needed |
| Meant for | trying ATLAS out | anything that resells or depends on the answer |

A `402` is written to get a caller unstuck rather than to say it is stuck: it carries
`price_per_call_usd`, a `free_allowance` block (`max`, `used`, `quota_window`, `renews`), a
`credit` block once the rail is on, and `how_to_continue` as an ordered list of what would work.

An unrecognised key is **not** an error: the call falls back to the free allowance, the 402's
`credit` block says `recognized: false`, and the operator gets a log line. A typo in a desk's
configuration must not look like an outage — but it must not look like success either.

## For a buyer

Send the key, read what the answer costs you:

```bash
curl -sD /dev/stderr -X POST https://atlas.modelmarket.dev/ai-market/v2/invoke \
  -H 'X-API-Key: atls_…' -H 'Content-Type: application/json' \
  -d '{"capability_id":"atlas.watchbox.check@v1","input":{"west":-1.0,"south":51.3,"east":0.2,"north":51.6,"layers":["flood"]}}'
```

| Response header | Meaning |
|---|---|
| `X-Atlas-Credit-Charged-Usd` | What this call cost. `0.000000` on a refusal |
| `X-Atlas-Credit-Balance-Usd` | What is left after it |
| `X-Atlas-Credit-Low` | `1` once the balance is at or under `ATLAS_CREDITS_LOW_BALANCE_USD` |

They are on the response of the call that spent the money, so watching a balance costs no
extra request. An unpaid call carries none of them — absent means "not charged", never "zero".

The account can also be read directly. It answers `404` both for an unknown key and for a
disabled one, so it cannot be used to find out which keys exist:

```bash
curl -s https://atlas.modelmarket.dev/ai-market/v2/accounts/me -H 'X-API-Key: atls_…'
```

A buyer that runs unattended should treat `X-Atlas-Credit-Low` as the moment to act. By the
time a `402` arrives, its own customer's work has already failed.

## For the operator

```bash
# Issue an account. Works before the rail is switched on, so keys can be handed out first.
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"label":"acme","grant_usd":25}'        # api_key is returned ONCE

# Top up. Replay-safe on `reference`: the same invoice cannot be credited twice.
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts/<id>/topup \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"amount_usd":25,"reference":"inv-1043"}'

# Suspend one without deleting its history.
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts/<id>/status \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -d '{"status":"disabled"}'

# What is held for other people, in total.
curl -s https://atlas.modelmarket.dev/ai-market/v2/credits/stats \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN"
```

Only the hash of a key is stored. It is shown once, at creation, and cannot be recovered —
reissue instead.

| Switch | Default | What it does |
|---|---|---|
| `ATLAS_PAYMENT_ENFORCED` | off | Meters priced capabilities at all |
| `ATLAS_CREDITS_ENABLED` | off | Accepts credit keys. Accounts can be created before this |
| `ATLAS_CREDITS_DB_PATH` | `data/atlas_credits.db` | The ledger. Must be on a mounted volume |
| `ATLAS_CREDITS_LOW_BALANCE_USD` | `1.00` | Low-balance threshold. `0` silences it |

**Order matters.** Turn `ATLAS_CREDITS_ENABLED=1` on **after** the accounts exist and the keys
are in the buyers' hands. Enabling it first puts every buyer holding a not-yet-issued key back
on the anonymous allowance at the moment it starts expecting to be charged.

The operator is also warned in the log, once per account per ten minutes, when a balance goes
low — counted in remaining calls rather than only in dollars, because the number that says how
long there is to act is "about 7 more calls", not "$0.42".

## What the money does, exactly

- **Reserved before the work, settled after it.** A call places a `hold`, and delivery
  `capture`s it. Charging first and refunding later would bill a caller for a crash.
- **A refusal is never billed.** An `ok: false` answer with a reason releases the hold. A cold
  sensor fleet costs nothing.
- **Whole cents are not the unit.** Balances are kept in millicents, so a published $0.02 is
  charged as exactly $0.02 rather than rounded up into somebody's favour.
- **A crashed request does not freeze money.** A hold older than ten minutes is released by a
  sweep, so a killed process costs its owner nothing.
- **A ledger that cannot be read refuses the call.** This is the opposite of the free-allowance
  meter, which deliberately fails open: over-serving a trial is a rounding error, while serving
  a paid product that was never recorded is somebody else's money.
- **An ephemeral ledger refuses to boot.** If `ATLAS_CREDITS_DB_PATH` would not survive a
  redeploy, ATLAS stops instead of taking prepaid money into a file it is about to delete.

A prepaid balance is **custody**: it is somebody else's money, held by the operator, and worth
what the operator's word is worth. There is no on-chain escrow behind it and no automatic
refund — that is the honest limit of this rail, and it is why the ledger rules above are not
negotiable.

## Who reads what

The manifest and the 402 both advertise the rail (`credits.enabled`, `key_header`,
`account_url`), so a buyer can discover it without being told. Desks in the cite-desk family
read the response headers and republish them at their own `/api/public/health` under
`supply.credit`, together with the seller the balance belongs to — a desk buys from more than
one, and a healthy account at ATLAS is not evidence that the other one is funded.
