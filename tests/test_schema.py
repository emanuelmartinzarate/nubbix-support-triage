import json

import pytest

from triage.schema import ParseError, blocked_response, parse_response

VALID = {"answer": "Hola", "confidence": 0.9, "category": "billing", "actions": ["Revisar cobro"]}


def test_parse_plain_json():
    assert parse_response(json.dumps(VALID)).category == "billing"


def test_parse_fenced_json():
    assert parse_response(f"```json\n{json.dumps(VALID)}\n```").confidence == 0.9


def test_parse_json_with_surrounding_text():
    assert parse_response(f"Claro: {json.dumps(VALID)} listo").answer == "Hola"


def test_confidence_string_is_coerced():
    assert parse_response(json.dumps({**VALID, "confidence": "0.8"})).confidence == 0.8


@pytest.mark.parametrize(
    "bad",
    [
        {**VALID, "confidence": 1.5},
        {**VALID, "category": "Facturación"},
        {**VALID, "category": "BILLING"},
        {**VALID, "actions": []},
        {**VALID, "actions": ["a"] * 6},
        {**VALID, "actions": [" "]},
        {**VALID, "answer": "   "},
        {**VALID, "extra": 1},
        {k: v for k, v in VALID.items() if k != "actions"},
    ],
)
def test_invalid_contract_raises_parse_error(bad):
    with pytest.raises(ParseError):
        parse_response(json.dumps(bad))


def test_not_json_raises_parse_error():
    with pytest.raises(ParseError):
        parse_response("no tengo idea")


def test_blocked_response_is_valid_contract():
    r = blocked_response("injection")
    assert r.category == "other" and r.confidence == 0.0 and "injection" in r.actions[0]
