from datetime import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import FlightOffer, HotelOffer, TourOffer, TravelGroup
from ..schemas import PlanSelectionForValidation


def violation(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


async def validate_selection(
    db: AsyncSession,
    group: TravelGroup | None,
    selection: PlanSelectionForValidation,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    constraints = constraints or {}
    hard: list[dict[str, str]] = []
    warnings: list[str] = []
    flight = await db.get(FlightOffer, selection.flight_id) if selection.flight_id else None
    hotel = await db.get(HotelOffer, selection.hotel_id) if selection.hotel_id else None
    tour = await db.get(TourOffer, selection.tour_id) if selection.tour_id else None

    if selection.flight_id and flight is None:
        hard.append(violation("unknown_flight", "Указанный перелёт не найден."))
    if selection.hotel_id and hotel is None:
        hard.append(violation("unknown_hotel", "Указанный отель не найден."))
    if selection.tour_id and tour is None:
        hard.append(violation("unknown_tour", "Указанный пакетный тур не найден."))

    destination = group.destination if group else None
    for kind, offer_destination in (
        ("flight", flight.destination if flight else None),
        ("hotel", hotel.destination if hotel else None),
        ("tour", tour.destination if tour else None),
    ):
        if destination and offer_destination and offer_destination != destination:
            hard.append(
                violation(
                    f"{kind}_destination_mismatch",
                    "Предложение не соответствует направлению поездки.",
                )
            )

    nights = 1
    if group and group.start_date and group.end_date:
        nights = max((group.end_date - group.start_date).days, 1)

    if tour:
        total = tour.total_price_rub
        if flight and not tour.includes_flight:
            total += flight.price_rub
        if hotel and hotel.hotel_id != tour.hotel_id:
            total += hotel.price_per_night_rub * nights
    else:
        total = (flight.price_rub if flight else 0) + (
            hotel.price_per_night_rub * nights if hotel else 0
        )

    submitted_total = selection.total_cost_rub
    if submitted_total is not None and submitted_total != total:
        warnings.append(
            f"Переданная стоимость {submitted_total} руб. заменена расчётной: {total} руб."
        )

    budget = constraints.get("budget_rub")
    if budget is None and group:
        budget = group.budget_rub
    if budget is not None and total > int(budget):
        hard.append(violation("budget_exceeded", "Стоимость плана превышает бюджет."))

    required_baggage = constraints.get("required_baggage")
    if required_baggage and flight and not flight.baggage_included:
        hard.append(violation("baggage_required", "В выбранный тариф не включён багаж."))

    max_stops = constraints.get("max_stops")
    if max_stops is not None and flight and flight.stops > int(max_stops):
        hard.append(violation("too_many_stops", "Количество пересадок превышает допустимое."))

    avoid_night = constraints.get("avoid_night_flights")
    if avoid_night and flight:
        arrival = time.fromisoformat(flight.arrival_time)
        if arrival >= time(23, 0) or arrival < time(5, 0):
            hard.append(violation("night_arrival", "Выбран ночной прилёт."))

    min_stars = constraints.get("min_stars")
    if min_stars is not None and hotel and hotel.stars < int(min_stars):
        hard.append(violation("hotel_class", "Категория отеля ниже требуемой."))

    if group:
        pref_pairs = {
            (pref.type, pref.value) for member in group.members for pref in member.preferences
        }
        if ("baggage", "included") in pref_pairs and flight and not flight.baggage_included:
            hard.append(violation("baggage_required", "Группе требуется включённый багаж."))
        if ("meal", "breakfast") in pref_pairs and hotel and not hotel.breakfast_included:
            hard.append(violation("breakfast_required", "Группе требуется завтрак."))
        if ("cancellation", "free") in pref_pairs and hotel and not hotel.free_cancellation:
            hard.append(violation("free_cancellation_required", "Требуется бесплатная отмена."))
        if any(member.age is not None and member.age < 7 for member in group.members):
            if flight:
                arrival = time.fromisoformat(flight.arrival_time)
                if arrival >= time(23, 0) or arrival < time(5, 0):
                    hard.append(
                        violation(
                            "child_night_arrival",
                            "Для группы с ребёнком запрещён ночной прилёт.",
                        )
                    )
            warnings.append("Размещение ребёнка необходимо подтвердить у поставщика.")
        if ("restriction", "visa_check") in pref_pairs:
            warnings.append("Необходима дополнительная проверка визовых ограничений.")

    if constraints.get("layover_duration") is not None:
        warnings.append("Длительность пересадки отсутствует в наборе данных и не проверена.")
    if constraints.get("capacity") is not None:
        warnings.append("Вместимость предложений отсутствует в наборе данных и не проверена.")

    return {
        "valid": not hard,
        "hard_violations": hard,
        "soft_warnings": list(dict.fromkeys(warnings)),
        "budget_left_rub": int(budget) - total if budget is not None else None,
        "calculated_total_rub": total,
    }
