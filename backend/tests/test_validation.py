import json

import pytest

from app.simulation.validation import ReactionError, extract_json, parse_reaction, verify_evidence

SEG = 'The lighthouse had been dark for eleven years.\n\n"Nobody goes up there," said Mara.'

GOOD = {
    "engagement_score": 7,
    "emotion": "curious",
    "inner_thought": "Why did it go dark?",
    "would_continue": True,
    "evidence": "The lighthouse had been dark for eleven years.",
    "reason": "A concrete mystery opens the story.",
}


def test_valid_reaction_parses_and_evidence_verified():
    p = parse_reaction(json.dumps(GOOD), SEG)
    assert p.reaction.engagement_score == 7
    assert p.evidence_verified


def test_code_fenced_and_chatty_json_is_accepted():
    raw = "Sure!\n```json\n" + json.dumps(GOOD) + "\n```"
    assert parse_reaction(raw, SEG).reaction.emotion == "curious"


@pytest.mark.parametrize("val,expected", [("7/10", 7), ("8", 8), (6.6, 7), (6.0, 6)])
def test_score_coercion(val, expected):
    assert parse_reaction({**GOOD, "score": 1, "engagement_score": val}, SEG).reaction.engagement_score == expected


@pytest.mark.parametrize("val", [11, -1, "great", None, True])
def test_bad_score_rejected(val):
    with pytest.raises(ReactionError):
        parse_reaction({**GOOD, "engagement_score": val}, SEG)


def test_unknown_emotion_rejected():
    with pytest.raises(ReactionError, match="emotion"):
        parse_reaction({**GOOD, "emotion": "hangry"}, SEG)


def test_emotion_is_normalised():
    assert parse_reaction({**GOOD, "emotion": " Curious "}, SEG).reaction.emotion == "curious"


def test_yes_no_coerced():
    assert parse_reaction({**GOOD, "would_continue": "No"}, SEG).reaction.would_continue is False


def test_missing_field_rejected():
    bad = {k: v for k, v in GOOD.items() if k != "reason"}
    with pytest.raises(ReactionError, match="reason"):
        parse_reaction(bad, SEG)


@pytest.mark.parametrize("raw", ["", "not json at all", "[1, 2]", "{broken"])
def test_garbage_rejected(raw):
    with pytest.raises(ReactionError):
        extract_json(raw)


def test_fabricated_evidence_flagged():
    p = parse_reaction({**GOOD, "evidence": "The tower crumbled into the sea."}, SEG)
    assert not p.evidence_verified


def test_evidence_from_other_text_flagged():
    assert not verify_evidence("a sentence that is nowhere in the segment", SEG)


def test_evidence_tolerates_quotes_case_whitespace():
    seg = "She said “don’t go” and left."
    assert verify_evidence('"Don\'t   go"', seg)
    assert verify_evidence("THE LIGHTHOUSE HAD BEEN DARK", SEG)
    assert verify_evidence("dark for eleven years.\n\n\"Nobody goes up there,\"", SEG)


def test_evidence_with_ellipsis_fragments():
    assert verify_evidence("The lighthouse had been dark ... said Mara.", SEG)
    assert not verify_evidence("The lighthouse had been dark ... and then it exploded.", SEG)


def test_trivial_evidence_rejected():
    assert not verify_evidence("a", SEG)
    assert not verify_evidence("...", SEG)
