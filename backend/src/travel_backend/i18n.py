MESSAGES = {
    "ru-RU": {
        "validation_error": "Проверьте корректность переданных данных.",
        "unauthorized": "Требуется авторизация.",
        "token_expired": "Срок действия токена истёк.",
        "forbidden": "Недостаточно прав для выполнения операции.",
        "not_found": "Запрошенный ресурс не найден.",
        "conflict": "Операция конфликтует с текущим состоянием ресурса.",
        "plan_not_ready": "План ещё не готов для этой операции.",
        "rate_limited": "Слишком много запросов. Повторите попытку позже.",
        "internal": "Произошла внутренняя ошибка сервиса.",
        "agent_unavailable": "Сервис планирования временно недоступен.",
        "timeout": "Сервис планирования не ответил вовремя.",
        "invalid_credentials": "Неверный адрес электронной почты или пароль.",
        "email_exists": "Пользователь с таким адресом уже зарегистрирован.",
        "invalid_refresh": "Refresh-токен недействителен или уже использован.",
        "invalid_service_token": "Недействительный сервисный токен.",
        "missing_correlation": "Не указан X-Correlation-ID.",
        "plan_invalid": "Предложенный план не прошёл проверку.",
        "constraints_conflict": "Не удалось подобрать вариант без нарушения ограничений.",
        "escalation": "Для продолжения требуется дополнительная проверка специалистом.",
        "clarifying_answer_summary": "Ответ на уточняющий вопрос",
        "ready_plan_summary": "Готовый план поездки",
        "plan_ready": "План поездки готов.",
    },
    "en-US": {
        "validation_error": "Check the submitted data.",
        "unauthorized": "Authentication is required.",
        "token_expired": "The token has expired.",
        "forbidden": "You do not have permission for this operation.",
        "not_found": "The requested resource was not found.",
        "conflict": "The operation conflicts with the current resource state.",
        "plan_not_ready": "The plan is not ready for this operation.",
        "rate_limited": "Too many requests. Try again later.",
        "internal": "An internal service error occurred.",
        "agent_unavailable": "The planning service is temporarily unavailable.",
        "timeout": "The planning service did not respond in time.",
        "invalid_credentials": "Invalid email address or password.",
        "email_exists": "A user with this email already exists.",
        "invalid_refresh": "The refresh token is invalid or already used.",
        "invalid_service_token": "Invalid service token.",
        "missing_correlation": "X-Correlation-ID is required.",
        "plan_invalid": "The proposed plan failed validation.",
        "constraints_conflict": "No option satisfies all constraints.",
        "escalation": "Additional specialist review is required.",
        "clarifying_answer_summary": "Clarifying-question answer",
        "ready_plan_summary": "Ready travel plan",
        "plan_ready": "The travel plan is ready.",
    },
}


def choose_locale(accept_language: str | None, supported: list[str], default: str) -> str:
    if not accept_language:
        return default
    requested = [item.split(";")[0].strip() for item in accept_language.split(",")]
    for locale in requested:
        if locale in supported:
            return locale
        language = locale.split("-")[0].lower()
        match = next((item for item in supported if item.lower().startswith(language)), None)
        if match:
            return match
    return default


def message(key: str, locale: str = "ru-RU") -> str:
    catalog = MESSAGES.get(locale, MESSAGES["ru-RU"])
    return catalog.get(key, MESSAGES["ru-RU"].get(key, key))
