"""Topic scope gate for ATLAS Analyst."""

from __future__ import annotations

from atlas.topic_scope import out_of_scope_answer, out_of_scope_reason


def test_sensor_and_ecosystem_in_scope():
    assert out_of_scope_reason("What is the air quality in Berlin?") is None
    assert out_of_scope_reason("How does GAIA relate to the Hub?") is None
    assert out_of_scope_reason("Сравни погоду Berlin vs NYC") is None


def test_off_topic_blocked():
    assert out_of_scope_reason("Write me a poem about cats please now") == "off_topic_pattern"
    assert out_of_scope_reason("Tell me a funny joke about politicians today") == "no_scope_markers"
    assert "sensor" in out_of_scope_answer("en").lower() or "ecosystem" in out_of_scope_answer("en").lower()


def test_generic_markers_are_word_bounded():
    # "Shakespeare" contains "peer", "manifesto" contains "manifest" —
    # substring matches must not open the gate.
    assert out_of_scope_reason("Tell me about Shakespeare and his best plays") == "no_scope_markers"
    assert out_of_scope_reason("Write a political manifesto for my new party") is not None
    # As whole words they are legitimate federation questions.
    assert out_of_scope_reason("Who are the peers on the hub right now?") is None
    assert out_of_scope_reason("How do I invoke a capability from the catalog?") is None
