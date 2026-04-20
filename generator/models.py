from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    source: str
    category: str
    published: datetime


@dataclass
class WeatherReport:
    city: str
    temp_current_c: float
    temp_min_c: float
    temp_max_c: float
    description: str
    wind_kmh: float
    precipitation_mm: float


@dataclass
class BulletinSection:
    title: str
    text: str
    start_seconds: int


@dataclass
class Bulletin:
    date: datetime
    sections: List[BulletinSection]
    full_text: str


@dataclass
class HistoryItem:
    year: int
    text: str
    source_lang: str  # "ro" or "en"


@dataclass
class HistoryCandidates:
    events: List["HistoryItem"]
    births: List["HistoryItem"]
    deaths: List["HistoryItem"]
