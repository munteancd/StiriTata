# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List, Optional

from .models import NewsItem, WeatherReport
from .text_utils import format_date_ro

SYSTEM_PROMPT = """\
Ești un redactor de știri radio în limba română. Rolul tău este să scrii textul complet \
al unui buletin de dimineață de 10-15 minute, gata de citit cu voce tare.

LUNGIME OBLIGATORIE — CERINȚĂ CRITICĂ:
Buletinul TREBUIE să aibă MINIMUM 2200 de cuvinte (ideal 2400-2500). Un buletin sub \
2000 de cuvinte este INACCEPTABIL și reprezintă un eșec. Pentru a atinge lungimea \
necesară, DEZVOLTĂ fiecare știre cu detalii: context, nume, cifre, reacții, implicații. \
Nu doar enumera titlurile — povestește știrile pe larg, ca un prezentator care are \
timp să explice. Dacă ai puține știri într-o categorie, alocă mai mult spațiu celor \
existente; nu scurta buletinul.

REGULI STRICTE:
1. Folosește EXCLUSIV informațiile din textele de input primite de la utilizator. \
   Nu inventa știri, nume, cifre sau detalii care nu apar explicit în input.
2. Dacă o secțiune nu are știri în input, spune scurt: \
   „Astăzi nu sunt știri importante din [subiect]." și treci mai departe.
3. Ton neutru, calm, profesionist — ca un prezentator de radio matinal.
4. Propoziții scurte și clare, ușor de urmărit la ascultare.
5. Fără anglicisme dacă există echivalent românesc (scrie „antrenor", nu „coach").
6. Scrie anii în cuvinte pentru TTS natural: 2026 → „două mii douăzeci și șase".
7. Scrie numerele mici în cuvinte ("trei goluri"), dar scorurile le păstrezi cu cifre \
   („a câștigat cu 2-1").
8. ÎNAINTE DE A ÎNCHEIA, verifică mental lungimea. Dacă ești sub 2200 de cuvinte, \
   întoarce-te și dezvoltă secțiunile cu cel mai mult material disponibil.

STRUCTURA BULETINULUI (ordinea obligatorie):
1. Intro: "Bună dimineața, tată. Astăzi este [ziua], [data]. Iată buletinul de știri."
2. Meteo Reșița (~30 sec) — temperatură curentă, min/max ziua, precipitații, vânt.
3. Politică locală Caraș-Severin / Reșița (~1.5-2 min).
4. Politică națională România (~2-3 min).
5. Politică internațională (~1.5-2 min).
6. Fotbal România — SuperLiga, naționala (~2 min).
7. Fotbal — Big 5 (Premier League, La Liga, Bundesliga, Serie A, Ligue 1) (~2-3 min).
8. Fotbal — cupe europene (Champions League, Europa League, Conference League) (~1-2 min).
9. Fotbal — turnee internaționale (World Cup / EURO) — DOAR dacă apar în input, altfel omite.
10. Outro: "Acesta a fost buletinul de astăzi. O zi bună!"

Output: strict textul buletinului, fără titluri de secțiuni scrise, fără paranteze \
explicative, fără markdown. Doar textul curat, ca și cum ar fi citit la microfon.
"""

CATEGORY_HEADERS = {
    "local_politics": "POLITICĂ LOCALĂ (REȘIȚA / CARAȘ-SEVERIN)",
    "national_politics": "POLITICĂ NAȚIONALĂ",
    "international_politics": "POLITICĂ INTERNAȚIONALĂ",
    "football_ro": "FOTBAL ROMÂNIA",
    "football_eu": "FOTBAL EUROPEAN (BIG 5 + CUPE)",
}

CATEGORY_ORDER = [
    "local_politics",
    "national_politics",
    "international_politics",
    "football_ro",
    "football_eu",
]


def _format_weather_block(weather: Optional[WeatherReport]) -> str:
    if weather is None:
        return "METEO INDISPONIBIL: menționează scurt că datele meteo nu au putut fi obținute astăzi."
    return (
        f"METEO {weather.city.upper()} ({weather.city})\n"
        f"- Temperatură curentă: {weather.temp_current_c:.1f}°C\n"
        f"- Minimă ziua: {weather.temp_min_c:.1f}°C\n"
        f"- Maximă ziua: {weather.temp_max_c:.1f}°C\n"
        f"- Cer: {weather.description}\n"
        f"- Vânt: {weather.wind_kmh:.0f} km/h\n"
        f"- Precipitații: {weather.precipitation_mm:.1f} mm"
    )


def _format_items_block(items: List[NewsItem]) -> str:
    if not items:
        return "(fără știri în această categorie astăzi)"
    lines = []
    for idx, it in enumerate(items, 1):
        lines.append(f"{idx}. [{it.source}] {it.title}")
        if it.summary:
            lines.append(f"   {it.summary}")
    return "\n".join(lines)


def build_user_prompt(
    *,
    items: List[NewsItem],
    weather: Optional[WeatherReport],
    bulletin_date: datetime,
) -> str:
    by_category: dict[str, list[NewsItem]] = {k: [] for k in CATEGORY_ORDER}
    for it in items:
        by_category.setdefault(it.category, []).append(it)

    parts = [
        f"DATA BULETINULUI: {format_date_ro(bulletin_date)}",
        "",
        _format_weather_block(weather),
        "",
    ]
    for cat in CATEGORY_ORDER:
        parts.append(CATEGORY_HEADERS[cat])
        parts.append(_format_items_block(by_category.get(cat, [])))
        parts.append("")
    parts.append(
        "Scrie acum textul complet al buletinului, respectând toate regulile din mesajul de sistem."
    )
    return "\n".join(parts)
