from travel_backend.i18n import choose_locale, message


def test_default_messages_are_russian_and_codes_stay_english():
    assert choose_locale(None, ["ru-RU", "en-US"], "ru-RU") == "ru-RU"
    assert "авториза" in message("unauthorized", "ru-RU").lower()
    assert "Authentication" in message("unauthorized", "en-US")
    assert "unauthorized".isascii()

