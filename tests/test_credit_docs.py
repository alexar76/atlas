"""Five-language parity for the credit-account document.

Two ways a translation of THIS document can take somebody's money:

1. It translates an identifier. An operator reads their own language and types what it says;
   a localized `ATLAS_CREDITS_DB_PATH` or `X-API-Key` is a rail that silently does not work.
2. It drops one of the honesty clauses. The rail is custody — prepaid money held by the
   operator, with no on-chain escrow and no automatic refund — and the order of the rollout
   (accounts and keys first, `ATLAS_CREDITS_ENABLED=1` second) is what stops a buyer from
   landing back on the anonymous allowance the moment it starts being charged. A translation
   that omits either reads as a friendlier product than the one that exists.

So the identifiers are asserted as invariants, and the claims are asserted per language.
The env var names and header names are read from the code, not retyped here: a rename that
did not reach the docs is exactly the failure this file exists to catch.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from atlas import credits

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
DOCS = {
    "en": DOCS_DIR / "CREDIT-ACCOUNTS.md",
    "ru": DOCS_DIR / "i18n" / "CREDIT-ACCOUNTS.ru.md",
    "es": DOCS_DIR / "i18n" / "CREDIT-ACCOUNTS.es.md",
    "fr": DOCS_DIR / "i18n" / "CREDIT-ACCOUNTS.fr.md",
    "zh": DOCS_DIR / "i18n" / "CREDIT-ACCOUNTS.zh.md",
}

#: Things a reader copies into a config file, a curl command, or a log filter.
INVARIANTS = (
    "ATLAS_PAYMENT_ENFORCED",
    "ATLAS_CREDITS_ENABLED",
    "ATLAS_CREDITS_DB_PATH",
    "ATLAS_CREDITS_LOW_BALANCE_USD",
    "ATLAS_OPERATOR_TOKEN",
    "/ai-market/v2/accounts",
    "/ai-market/v2/accounts/me",
    "/ai-market/v2/credits/stats",
    "topup",
    "reference",
    "grant_usd",
    "price_per_call_usd",
    "free_allowance",
    "quota_window",
    "max_per_caller",
    "recognized: false",
    "credits.enabled",
    "key_header",
    "account_url",
    "supply.credit",
    "hold",
    "capture",
    "ok: false",
    "data/atlas_credits.db",
)

#: Taken from the code so a rename cannot pass a green suite with stale docs.
FROM_CODE = (
    credits.KEY_HEADER,
    credits.KEY_PREFIX,
    credits.BALANCE_HEADER,
    credits.CHARGED_HEADER,
    credits.LOW_BALANCE_HEADER,
)


@pytest.mark.parametrize("lang", sorted(DOCS))
def test_every_language_exists_and_keeps_the_identifiers(lang):
    path = DOCS[lang]
    assert path.is_file(), f"{lang} documentation is missing"
    text = path.read_text(encoding="utf-8")
    for token in INVARIANTS + FROM_CODE:
        assert token in text, (lang, token)


@pytest.mark.parametrize("lang", sorted(DOCS))
def test_the_documented_defaults_are_the_real_ones(lang):
    """A default an operator reads and does not set is a default they are relying on."""
    text = DOCS[lang].read_text(encoding="utf-8")
    assert f"`{credits.low_balance_usd():.2f}`" in text, "low-balance default drifted"
    assert str(credits.HOLD_MAX_AGE_SECONDS // 60) in text, "stale-hold age drifted"


@pytest.mark.parametrize("lang", sorted(DOCS))
def test_structure_matches_english(lang):
    """Same sections, same tables, same worked examples. A dropped section is a dropped rule."""
    en = DOCS["en"].read_text(encoding="utf-8")
    text = DOCS[lang].read_text(encoding="utf-8")
    for pattern in (r"^## ", r"^\|\s*-", r"^- \*\*"):
        assert len(re.findall(pattern, text, re.M)) == len(re.findall(pattern, en, re.M)), (
            lang,
            pattern,
        )
    assert text.count("```bash") == en.count("```bash")


@pytest.mark.parametrize("lang", sorted(DOCS))
def test_the_two_rails_are_both_described(lang):
    """Naming only the paid one would read as "ATLAS is closed"; only the free one is the bug."""
    text = DOCS[lang].read_text(encoding="utf-8")
    assert "X-AIMarket-Sandbox-Visitor" in text, lang
    assert credits.KEY_PREFIX in text, lang
    assert "402" in text, lang


#: The custody sentence, in each language's glossary rendering. Asserted per language rather
#: than by a shared token because this is the one claim a translator is tempted to soften:
#: it says the money is the operator's word, not an escrow.
CUSTODY = {
    "en": ("**custody**", "escrow"),
    "ru": ("**кастодиальное хранение**", "эскроу"),
    "es": ("**custodia**", "escrow"),
    "fr": ("**garde de fonds**", "séquestre"),
    "zh": ("**资金托管**", "托管"),
}

#: The money ledger fails closed; the free meter it is contrasted with fails open. Losing the
#: contrast is what makes "we refuse when the ledger is unreadable" read as a bug report.
FAIL_OPEN = {
    "en": "fails open",
    "ru": "fail-open",
    "es": "falla abierto",
    "fr": "échoue ouvert",
    "zh": "fail-open",
}


@pytest.mark.parametrize("lang", sorted(DOCS))
def test_the_honesty_clauses_survive_translation(lang):
    """Custody, the fail-closed ledger, the unbilled refusal, and the rollout order."""
    text = DOCS[lang].read_text(encoding="utf-8")
    term, no_escrow = CUSTODY[lang]
    assert term in text, (lang, "the custody sentence was dropped or reworded")
    assert no_escrow in text, (lang, "the doc must say there is no escrow behind the balance")
    assert FAIL_OPEN[lang] in text, (lang, "the contrast with the free meter was lost")
    # Refusals are unbilled, and the rollout order is stated with the switch that enforces it.
    assert "ok: false" in text, lang
    assert "ATLAS_CREDITS_ENABLED=1" in text, lang


@pytest.mark.parametrize("lang", sorted(DOCS))
def test_no_cross_language_leakage(lang):
    """An earlier five-language pass elsewhere left Russian sentences inside the EN/ZH files."""
    text = DOCS[lang].read_text(encoding="utf-8")
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", text))
    cjk = len(re.findall(r"[一-鿿]", text))
    if lang == "ru":
        assert cyrillic > 500 and cjk == 0
    elif lang == "zh":
        assert cjk > 500 and cyrillic == 0
    else:
        assert cyrillic == 0 and cjk == 0, (lang, cyrillic, cjk)


@pytest.mark.parametrize("lang", sorted(DOCS))
def test_language_switcher_resolves(lang):
    """Each file offers all five languages, and every link points at a file that exists."""
    path = DOCS[lang]
    text = path.read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)]*CREDIT-ACCOUNTS[^)]*)\)", text)
    assert len(links) == len(DOCS), (lang, links)
    for target in links:
        assert (path.parent / target).resolve().is_file(), (lang, target)
