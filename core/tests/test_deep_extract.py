import pytest

from app.deep import extract


def form(*inputs, action="https://pay.example.net/charge"):
    return {"action": action, "inputs": [{"type": kind, "name": name} for kind, name in inputs]}


@pytest.mark.parametrize(
    "inputs",
    [[("password", "")], [("text", "otp")], [("tel", "pin_code")], [("text", "CVV")], [("text", "card_number")], [("text", "cardnumber")]],
)
def test_credential_form_is_detected(inputs):
    assert extract.credential_form([form(*inputs)])


@pytest.mark.parametrize("inputs", [[("text", "shipping_address"), ("email", "email")], [("search", "q")], []])
def test_ordinary_form_is_not_a_credential_form(inputs):
    assert not extract.credential_form([form(*inputs)])


def test_phones_come_from_text_and_tel_links_as_e164_without_duplicates():
    text = "Call us on 050 123 4567 or +971 4 223 4567."
    links = ["tel:+971501234567", "tel:not-a-number"]
    assert extract.phones(text, links) == ["+971501234567", "+97142234567"]


def test_whatsapp_numbers_come_from_both_link_shapes():
    links = [
        "https://wa.me/971501234567",
        "https://api.whatsapp.com/send?phone=971509876543&text=hi",
        "https://wa.me/971501234567",
        "https://wa.me/12",
    ]
    assert extract.whatsapp(links) == ["+971501234567", "+971509876543"]


def test_payment_hosts_are_form_action_hosts_other_than_the_page():
    forms = [
        form(action="https://pay.example.net/charge"),
        form(action="https://shop.example.com/own"),
        form(action="https://pay.example.net/other"),
        form(action=""),
    ]
    assert extract.payment_hosts(forms, "shop.example.com") == ["pay.example.net"]


def test_malformed_forms_and_links_are_skipped():
    forms = ["x", None, {"action": 5, "inputs": []}, {"action": "http://[bad", "inputs": [{"type": 1, "name": "pw"}]}, form(("password", "pw"))]
    assert extract.credential_form(forms)
    assert extract.payment_hosts(forms, "shop.example.com") == ["pay.example.net"]
    assert extract.phones("", [None, 5, "tel:+971501234567"]) == ["+971501234567"]
    assert extract.whatsapp([None, {"a": 1}, "https://wa.me/971501234567"]) == ["+971501234567"]
