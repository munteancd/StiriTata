# -*- coding: utf-8 -*-
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from .models import HistoryCandidates, HistoryItem, NewsItem, WeatherReport
from .text_utils import format_date_ro

# ----------------------------------------------------------------------------
# Whole-bulletin prompt (kept for single-call fallback and for tests).
# The production path uses per-section prompts below.
# ----------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Ești un redactor de știri radio în limba română. Rolul tău este să scrii textul complet \
al unui buletin de dimineață de aproximativ 13 minute, gata de citit cu voce tare.

REGULI STRICTE:
1. Folosește EXCLUSIV informațiile din textele de input primite de la utilizator. \
   Nu inventa știri, nume, cifre sau detalii care nu apar explicit în input.
2. Dacă o secțiune nu are știri, spune scurt și treci mai departe.
3. Ton neutru, calm, profesionist — ca un prezentator de radio matinal.
4. Propoziții scurte și clare, ușor de urmărit la ascultare.
5. Fără anglicisme dacă există echivalent românesc.
6. Scrie anii și numerele în cuvinte pentru TTS natural (excepție: scorurile rămân \
   cu cifre, de exemplu „a câștigat cu 2-1").
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


def _format_history_block(history: Optional["HistoryCandidates"]) -> str:
    if history is None or (
        not history.events and not history.births and not history.deaths
    ):
        return "(candidați istorici indisponibili astăzi)"
    lines: list[str] = []

    def _append_section(label: str, entries: List["HistoryItem"]) -> None:
        if not entries:
            return
        lines.append(label)
        for it in entries:
            tag = "[RO]" if it.source_lang == "ro" else "[EN]"
            lines.append(f"- {it.year} {tag} {it.text}")
        lines.append("")

    _append_section("EVENIMENTE:", history.events)
    _append_section("NAȘTERI:", history.births)
    _append_section("DECESE:", history.deaths)
    return "\n".join(lines).rstrip()


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


# ----------------------------------------------------------------------------
# Per-section configuration (production path).
# Each section is generated in its own API call with a specific word target.
# This gives us reliable control over total bulletin length.
# ----------------------------------------------------------------------------

SECTION_SYSTEM_PROMPT = """\
Ești un redactor de știri radio în limba română. Scrii o SECȚIUNE dintr-un \
buletin de dimineață care va fi citit cu voce tare de un motor TTS \
ROMÂNESC (Piper, voce „mihai-medium").

REGULI STRICTE:
1. Folosește EXCLUSIV informațiile din inputul utilizatorului. Nu inventa \
   nimic (știri, nume, cifre, citate, ore).
2. Ton neutru, calm, profesionist — prezentator de radio matinal.
3. Propoziții scurte și clare, ușor de urmărit la ascultare.
4. Fără anglicisme dacă există echivalent românesc („antrenor", nu „coach").
5. Scrie anii ȘI numerele în cuvinte pentru TTS natural: \
   „două mii douăzeci și șase", „opt virgulă unu grade", „treizeci și șase de ani". \
   Excepție: scorurile sportive rămân cu cifre („2-1", „4-2").
6. Nu scrie titluri de secțiuni, nu folosi markdown, nu lăsa paranteze explicative. \
   Doar proză curată, gata de citit la microfon.

PRONUNȚIA NUMELOR STRĂINE (REGULĂ IMPORTANTĂ):
Motorul TTS citește TOT textul cu fonetică românească. Dacă scrii „Manchester City", \
îl va pronunța literă cu literă în română și va suna ridicol. De aceea, REscrie \
numele străine (echipe de fotbal, jucători, politicieni străini, orașe străine) \
FONETIC în română, astfel încât sunetul rezultat să imite pronunția reală.

Exemple concrete:
- „Manchester City" → scrie „Mencester Siti"
- „Liverpool" → „Liverpul"
- „Chelsea" → „Celsi"
- „Arsenal" → „Arsnăl"
- „Tottenham" → „Totnăm"
- „Leicester" → „Lestăr"
- „Newcastle" → „Niucasăl"
- „Nottingham Forest" → „Notingăm Forest"
- „Bayern München" → „Baiărn Miunhen"
- „Borussia Dortmund" → „Borusia Dortmund"
- „Real Madrid" → „Rial Madrid"
- „Atlético Madrid" → „Atletico Madrid"
- „Juventus" → „Iuventus"
- „Paris Saint-Germain" / „PSG" → „Paris Sengermen" (sau „Pe-Se-Je")
- „Champions League" → „Ceampions Lig"
- „Europa League" → „Europa Lig"
- „Premier League" → „Premier Lig"
- Jucători: „Haaland" → „Holand"; „Mbappé" → „Mbape"; „Foden" → „Fodăn"; \
  „Saka" → „Saka"; „Salah" → „Salah"; „Rodrygo" → „Rodrigo"
- Politicieni/lideri străini: „Trump" → „Tramp"; „Biden" → „Baidăn"; \
  „Macron" → „Macron"; „Netanyahu" → „Netaniahu"; „Zelensky" → „Zelenski"
- Orașe străine comune: păstrează varianta românească dacă există \
  („Londra", „Paris", „Roma", „Viena"); altfel transliterează fonetic \
  („New York" → „Niu Iork"; „Washington" → „Uașington")

Dacă ești în dubiu cu un nume, alege varianta care se citește cel mai aproape \
de pronunția reală când e spusă cu fonetică românească.

STIL — FĂRĂ CONCLUZII, REZUMATE SAU WRAP-UP (REGULĂ CATEGORICĂ):
Ultima propoziție a secțiunii TREBUIE să fie despre ULTIMA știre concretă, \
nu o frază de încheiere, nu un rezumat, nu o reflecție generală.

INTERZIS să termini secțiunea cu fraze ca:
- „Acestea au fost principalele știri din..."
- „Acestea sunt principalele știri..."
- „Rămâne de văzut cum vor evolua..."
- „Vom urmări cu interes..."
- „Rămânem atenți la evoluții"
- „Aceste rezultate subliniază..."
- „Lupta continuă..."
- orice frază care comentează pe ansamblu sau face conexiuni generale

După ultima știre, OPREȘTE-te. Punct. Fără încheiere.

De asemenea, nu adăuga mini-rezumate după fiecare știre individuală \
(„Această situație arată...", „Acest caz ridică întrebări..."). Prezintă \
știrea și treci la următoarea cu o tranziție scurtă ori o conjuncție \
(„Tot în această zonă", „În altă ordine de idei", „De asemenea").

EXCEPȚIE UNICĂ: doar la meteo poți închide cu o recomandare practică \
scurtă (umbrelă, haine groase) dacă vremea o cere. Nicăieri altundeva.

OBLIGATORIU — LUNGIME:
Secțiunea TREBUIE să aibă CEL PUȚIN {min_words} cuvinte. Ideal \
{target_words} cuvinte. Dacă ai puține elemente în input, dezvoltă fiecare \
cu context, nume, cifre, reacții, implicații — NU umple cu concluzii goale.
"""


@dataclass(frozen=True)
class Section:
    key: str
    intro_phrase: str       # e.g. "Trecem acum la politica națională."
    target_words: int
    min_words: int
    guidance: str           # Extra instructions specific to this section


SECTIONS: list[Section] = [
    Section(
        key="meteo",
        intro_phrase="Începem cu prognoza meteo pentru Reșița.",
        target_words=180,
        min_words=130,
        guidance=(
            "Citește prognoza pentru Reșița. Menționează temperatura curentă, "
            "minima și maxima ziua, starea cerului, vântul și precipitațiile. "
            "Spune-o ca un prezentator — nu înșira doar cifre, adaugă o scurtă "
            "recomandare practică (umbrelă, haine groase, etc.) dacă e cazul. "
            "Scrie TOATE valorile numerice în cuvinte (ex: „opt virgulă unu grade”)."
        ),
    ),
    Section(
        key="local_politics",
        intro_phrase="Trecem la știrile locale din Reșița și Caraș-Severin.",
        target_words=400,
        min_words=320,
        guidance=(
            "Prezintă toate știrile locale. Pentru fiecare, dezvoltă cu context: "
            "cine, ce, unde, când, de ce, cum. Include detalii din input (nume, "
            "vârste, străzi, cifre). Folosește tranziții naturale între știri "
            "(„În altă ordine de idei”, „Tot în această zonă”, „De asemenea”)."
        ),
    ),
    Section(
        key="national_politics",
        intro_phrase="Pe plan național, iată ce s-a întâmplat.",
        target_words=500,
        min_words=400,
        guidance=(
            "Prezintă știrile politice și de interes național. Dezvoltă fiecare "
            "știre: protagoniști, poziții, reacții, implicații. Menționează numele "
            "și funcțiile complete (premier, ministru, lider partid). Folosește "
            "tranziții naturale între știri."
        ),
    ),
    Section(
        key="international_politics",
        intro_phrase="Pe plan internațional, principalele evenimente.",
        target_words=400,
        min_words=320,
        guidance=(
            "Prezintă știrile internaționale prezente în input. Pentru fiecare, "
            "oferă context geografic și uman: țara, liderii, cauza, consecințele. "
            "Nu presupune cunoștințe pe care ascultătorul poate nu le are."
        ),
    ),
    Section(
        key="football_ro",
        intro_phrase="Trecem la fotbalul românesc.",
        target_words=400,
        min_words=320,
        guidance=(
            "Prezintă rezultatele recente și știrile din SuperLiga României și "
            "de la echipa națională. Pentru meciuri, dă scorul, marcatorii (dacă "
            "sunt menționați), momentul cheie, și implicația în clasament. "
            "Pentru transferuri sau declarații, dezvoltă cu context. Dacă în "
            "input sunt preview-uri pentru meciuri de azi, menționează-le clar "
            "cu formula „astăzi se joacă” sau „în această după-amiază joacă”."
        ),
    ),
    Section(
        key="football_eu",
        intro_phrase="În fotbalul european, rezumăm etapa.",
        target_words=450,
        min_words=360,
        guidance=(
            "Prezintă rezultatele și știrile din Premier League, La Liga, "
            "Bundesliga, Serie A, Ligue 1, Champions League, Europa League și "
            "Conference League. Grupează pe campionate. Pentru fiecare meci, "
            "dă scorul și o frază de context (cine a marcat, cum e în clasament). "
            "Dacă input-ul menționează meciuri de azi, spune-le clar."
        ),
    ),
    Section(
        key="history",
        intro_phrase="Înainte de a încheia, câteva momente din istoria zilei de astăzi.",
        target_words=150,
        min_words=120,
        guidance=(
            "Alege 2 până la 3 momente istorice relevante din candidații furnizați. "
            "Prioritizează evenimentele românești [RO] dacă există; completează cu "
            "[EN] doar dacă e nevoie. Stil conversațional, \u201eștiați că\u201d — nu listă "
            "seacă. Pentru fiecare moment, scrie anul în CUVINTE (de exemplu \u201euna "
            "nouă sute patruzeci și cinci\u201d). Tranziții naturale între momente "
            "(\u201eTot pe această zi\u201d, \u201eIar în\u201d). Nu inventa evenimente care nu apar "
            "în listă."
        ),
    ),
]


def build_intro(bulletin_date: datetime) -> str:
    """Hardcoded intro — deterministic, no API call needed."""
    return (
        f"Bună dimineața, Ilie. Astăzi este {format_date_ro(bulletin_date)}. "
        "Iată buletinul de știri."
    )


OUTRO = "Acesta a fost buletinul de astăzi. O zi bună, Ilie!"


def build_section_system_prompt(section: Section) -> str:
    return SECTION_SYSTEM_PROMPT.format(
        target_words=section.target_words,
        min_words=section.min_words,
    )


def build_section_user_prompt(
    *,
    section: Section,
    items: List[NewsItem],
    weather: Optional[WeatherReport],
    bulletin_date: datetime,
    history: Optional[HistoryCandidates] = None,
) -> str:
    """Build the user-role prompt for one section's API call."""
    parts = [
        f"DATA BULETINULUI: {format_date_ro(bulletin_date)}",
        f"SECȚIUNEA CURENTĂ: {section.key}",
        f"ȚINTA DE LUNGIME: {section.target_words} cuvinte (minim {section.min_words}).",
        "",
        "INSTRUCȚIUNI SPECIFICE:",
        section.guidance,
        "",
    ]

    if section.key == "meteo":
        parts.append("DATE DE INPUT:")
        parts.append(_format_weather_block(weather))
    elif section.key == "history":
        parts.append("DATE DE INPUT (AZI ÎN ISTORIE — candidați Wikipedia):")
        parts.append(_format_history_block(history))
    else:
        # News section — include the matching category
        cat_items = [it for it in items if it.category == section.key]
        parts.append(f"DATE DE INPUT ({CATEGORY_HEADERS.get(section.key, section.key)}):")
        parts.append(_format_items_block(cat_items))

    parts.append("")
    closing_rule = (
        "Termină EXACT la ultima știre concretă, fără frază de închidere, "
        "fără „Acestea au fost”, fără „Rămâne de văzut”."
    )
    if section.key == "meteo":
        closing_rule = (
            "Poți închide cu o recomandare practică scurtă (umbrelă, haine groase) "
            "dacă vremea o cere — o singură propoziție, nu mai mult."
        )
    parts.append(
        f"Scrie ACUM textul secțiunii „{section.key}”, fără titlu, fără paranteze, "
        f"doar proza pentru microfon. Începe cu fraza de tranziție: "
        f"„{section.intro_phrase}”. {closing_rule}"
    )
    return "\n".join(parts)
