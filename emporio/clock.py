import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Campo_Grande")
WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
HOURS = {d: (time(9), time(18)) for d in range(5)} | {5: (time(9), time(13))}


def now() -> datetime:
    frozen = os.getenv("EMPORIO_NOW")
    return datetime.fromisoformat(frozen) if frozen else datetime.now(TZ).replace(tzinfo=None)


def next_opening(moment: datetime) -> datetime:
    for offset in range(8):
        day = moment + timedelta(days=offset)
        hours = HOURS.get(day.weekday())
        if hours:
            opening = datetime.combine(day.date(), hours[0])
            if opening > moment:
                return opening
    raise AssertionError("store hours define no opening within a week")


def store_context(moment: datetime) -> str:
    hours = HOURS.get(moment.weekday())
    is_open = bool(hours) and hours[0] <= moment.time() < hours[1]
    base = f"Agora: {WEEKDAYS[moment.weekday()]}, {moment:%d/%m/%Y %H:%M} (Campo Grande)."
    if is_open:
        return f"{base} Pela grade regular, a loja está aberta até {hours[1]:%H:%M}."
    opening = next_opening(moment)
    return (
        f"{base} Pela grade regular, a loja está fechada e reabre "
        f"{WEEKDAYS[opening.weekday()]}, {opening:%d/%m} às {opening:%H:%M}. "
        "Informe esse retorno se o cliente precisar da equipe."
    )
