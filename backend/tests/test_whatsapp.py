import re
from pathlib import Path

import pytest

from app import whatsapp
from app.config import settings


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("+27 82 123 4567", "27821234567"),
        ("082 123 4567", "27821234567"),
        ("0027821234567", "27821234567"),
        ("27821234567", "27821234567"),
        ("(082) 123-4567", "27821234567"),
        ("+1 415 555 2671", "14155552671"),
        ("", None),
        ("abc", None),
        ("123", None),
        ("+" + "1" * 16, None),
    ],
)
def test_normalize_phone(raw, expected, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_default_country_code", "27")
    assert whatsapp.normalize_phone(raw) == expected


def test_template_variables_cannot_hold_line_breaks_or_be_empty():
    assert whatsapp.clean_param("a\nb\t c    d") == "a b c d"
    assert whatsapp.clean_param("") == "-"
    assert whatsapp.clean_param(None) == "-"
    assert whatsapp.clean_param(55) == "55"


def test_every_template_is_valid_for_meta():
    for name, (category, body) in whatsapp.TEMPLATES.items():
        numbers = [int(n) for n in re.findall(r"\{\{(\d+)\}\}", body)]
        assert numbers and sorted(set(numbers)) == list(range(1, max(numbers) + 1)), name
        assert not body.startswith("{{") and not body.rstrip().endswith("}}"), f"{name} starts/ends with a variable"
        assert category in {"UTILITY", "MARKETING", "AUTHENTICATION"}
        assert re.fullmatch(r"[a-z0-9_]+", name)


def test_the_setup_guide_lists_every_template_body_exactly():
    guide = (Path(__file__).resolve().parents[2] / "docs" / "WHATSAPP_SETUP.md").read_text(encoding="utf-8")
    for name, (_, body) in whatsapp.TEMPLATES.items():
        assert name in guide
        assert body in guide, f"docs/WHATSAPP_SETUP.md is out of date for {name}"


def test_render_fills_the_same_text_meta_will_send():
    text = whatsapp.render("booking_pending", ["Jane", "Training Hall", "Sat 3 Oct", "14:00"])
    assert text.startswith("Hi Jane, we've received your request to book Training Hall on Sat 3 Oct at 14:00.")
    assert "{{" not in text


class _Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = str(self._body)

    def json(self):
        return self._body


class _Client:
    calls = []
    response = _Resp(200, {"messages": [{"id": "wamid.1"}]})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None, timeout=None):
        _Client.calls.append((url, json, headers))
        return _Client.response


@pytest.fixture
def configured(monkeypatch):
    _Client.calls = []
    _Client.response = _Resp(200, {"messages": [{"id": "wamid.1"}]})
    monkeypatch.setattr(whatsapp.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", " 12345 ")
    monkeypatch.setattr(settings, "whatsapp_access_token", "TOKEN\n")
    monkeypatch.setattr(settings, "whatsapp_template_language", "en")
    monkeypatch.setattr(settings, "whatsapp_default_country_code", "27")


async def test_sends_an_approved_template_to_a_normalised_number(configured, capsys):
    await whatsapp.send_template("082 123 4567", "booking_pending", ["Jane", "Hall", "Sat", "14:00"])

    url, payload, headers = _Client.calls[0]
    assert url.endswith("/12345/messages")
    assert headers == {"Authorization": "Bearer TOKEN"}
    assert payload["to"] == "27821234567"
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "booking_pending"
    assert payload["template"]["language"] == {"code": "en"}
    assert [p["text"] for p in payload["template"]["components"][0]["parameters"]] == ["Jane", "Hall", "Sat", "14:00"]
    out = capsys.readouterr().out
    assert "[whatsapp sent] to=27821234567" in out
    assert "TOKEN" not in out


async def test_a_meta_error_is_logged_with_its_reason_and_never_raised(configured, capsys):
    _Client.response = _Resp(
        400, {"error": {"code": 132001, "message": "Template name does not exist", "error_data": {"details": "booking_pending/en"}}}
    )
    await whatsapp.send_template("+27821234567", "booking_pending", ["a", "b", "c", "d"])
    out = capsys.readouterr().out
    assert "[whatsapp error]" in out and "132001" in out and "Template name does not exist" in out
    assert "TOKEN" not in out


async def test_a_network_failure_is_logged_and_never_raised(configured, capsys, monkeypatch):
    class _Boom(_Client):
        async def post(self, *a, **k):
            raise OSError("network is unreachable")

    monkeypatch.setattr(whatsapp.httpx, "AsyncClient", _Boom)
    await whatsapp.send_template("+27821234567", "booking_pending", ["a", "b", "c", "d"])
    assert "[whatsapp error]" in capsys.readouterr().out


async def test_skipped_without_credentials_or_with_an_unusable_number(monkeypatch, configured, capsys):
    await whatsapp.send_template("abc", "booking_pending", ["a", "b", "c", "d"])
    assert _Client.calls == []
    assert "not a valid phone number" in capsys.readouterr().out

    monkeypatch.setattr(settings, "whatsapp_access_token", "")
    await whatsapp.send_template("+27821234567", "booking_pending", ["a", "b", "c", "d"])
    assert _Client.calls == []
    assert "no credentials" in capsys.readouterr().out
