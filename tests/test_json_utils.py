from app.agent.json_utils import parse_json_array, parse_json_object


def test_parse_json_object_accepts_plain_json():
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_json_object_strips_code_fence():
    text = '```json\n{"a": 1}\n```'
    assert parse_json_object(text) == {"a": 1}


def test_parse_json_object_returns_none_for_invalid():
    assert parse_json_object("not json") is None
    assert parse_json_object("") is None


def test_parse_json_array_accepts_plain_json():
    assert parse_json_array('[{"a": 1}]') == [{"a": 1}]


def test_parse_json_array_strips_code_fence():
    text = '```json\n[{"a": 1}]\n```'
    assert parse_json_array(text) == [{"a": 1}]


def test_parse_json_array_returns_none_for_invalid():
    assert parse_json_array("not json") is None
    assert parse_json_array('{"a": 1}') is None
