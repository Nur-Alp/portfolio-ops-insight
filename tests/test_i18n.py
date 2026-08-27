from osip_dashboard.i18n import localize_dataset_issue, localize_dq_issue


def test_dataset_issue_codes_have_english_text_not_a_raw_russian_fallback():
    """Regression test for a DQ audit finding: these three codes fired
    correctly in tests but had no _DATASET_ISSUES entry, so an English-locale
    reviewer silently saw the raw Russian message instead of a translation."""
    for code, ru_message in [
        ("CLIENT-DASH-01", "Сводный лист клиентов не совпадает с итогом реестра Лист4; оба значения сохранены как источник"),
        ("ACCOUNTING-03", "Лист содержит внешних ссылок: 2"),
        ("DERIV-01", "Исключено строк ETF (не являются производными инструментами): 3."),
        ("ACCOUNTING-04", "Проверка ошибок формул и внешних ссылок недоступна для источников формата .xls; она выполняется только для .xlsx"),
    ]:
        english = localize_dataset_issue(code, ru_message, "en")
        assert english != ru_message, f"{code} still falls back to the raw Russian message for English users"
        assert localize_dataset_issue(code, ru_message, "ru") == ru_message


def test_dq_issue_with_an_interpolated_count_is_still_localized_by_code():
    """DQ-02/DQ-12 (OSIP engine) interpolate a count into the message, so the
    exact-string _MESSAGES lookup can never match them - localize_dq_issue
    must fall back to a code-keyed translation instead of leaking Russian."""
    ru_message = "Расчётная инструкция встречается 3 раза для одной сделки."
    assert localize_dq_issue("DQ-02", ru_message, "en") != ru_message
    assert localize_dq_issue("DQ-02", ru_message, "ru") == ru_message

    ru_message = "Покрытие рейтингами/листингом неполное: у 4 лотов нет классификации листинга, а у 2 отсутствуют рейтинги всех агентств."
    assert localize_dq_issue("DQ-12", ru_message, "en") != ru_message


def test_dq_static_messages_have_english_text():
    dq07 = "Текст сектора в источнике смешивает сектора GICS, классы активов и списки нескольких секторов."
    dq16 = "Заявленные размеры листа содержат большое число отформатированных пустых строк в конце."
    assert localize_dq_issue("DQ-07", dq07, "en") != dq07
    assert localize_dq_issue("DQ-16", dq16, "en") != dq16
