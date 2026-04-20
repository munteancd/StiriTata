# Design: „Azi în istorie" & Memorează poziția

**Data:** 2026-04-20
**Autor:** Cristi (munteancd@gmail.com)
**Destinatar:** Ilie (tatăl utilizatorului) — ascultător zilnic la 06:00

## Context

StiriTata este un buletin audio zilnic în română, generat automat la 03:00 UTC prin GitHub Actions și servit ca PWA pe GitHub Pages. Arhitectura actuală: 6 secțiuni (meteo, politică locală/națională/internațională, fotbal RO/EU), fiecare generată printr-un apel OpenAI dedicat pe gpt-4o, text-to-speech cu Piper (voce `ro_RO-mihai-medium`), durată ~14 minute.

Două îmbunătățiri cerute de utilizator după două săptămâni de folosire reală:

1. **„Azi în istorie"** — o secțiune nouă de ~1 minut la finalul buletinului, cu 2-3 momente istorice relevante datei curente, în stil „știați că".
2. **Memorează poziția** — dacă Ilie apasă pauză (sau închide app-ul) la minutul 7, data viitoare când deschide PWA în aceeași zi, reia automat de acolo.

## Non-obiective

- **Nu** adăugăm dedup semantic (evaluat și respins — nu s-au observat duplicate reale).
- **Nu** schimbăm arhitectura per-section a buletinului existent.
- **Nu** modificăm vocea Piper sau structura celor 6 secțiuni actuale.
- **Nu** adăugăm UI de preferințe pentru utilizator — feature-urile sunt automate.

---

## Feature 1: „Azi în istorie"

### Scop

Tata să audă la finalul buletinului 2-3 repere istorice despre ziua curentă, în stil conversațional („Știați că pe douăzeci aprilie...?"), prioritizând evenimente relevante spațiului românesc dar cu fallback global dacă nu sunt destule.

### Arhitectură

**Nou modul:** `generator/fetch_history.py`

- Sursă: **Wikipedia REST API** `feed/onthisday/all/{MM}/{DD}`
  - Primar: `https://ro.wikipedia.org/api/rest_v1/feed/onthisday/all/{MM}/{DD}`
  - Fallback: `https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/{MM}/{DD}` dacă RO returnează **< 3 candidați totali** (adică `len(events) + len(births) + len(deaths) < 3`)
- Timeout: 15s per request
- Retry: 1x cu backoff de 2s
- Fără API key necesar
- User-Agent personalizat (conform politicii Wikipedia): `StiriTata/1.0 (https://munteancd.github.io/StiriTata/; munteancd@gmail.com)`

**Ieșire:** `HistoryCandidates` dataclass cu trei liste:
```python
@dataclass
class HistoryCandidates:
    events: list[HistoryItem]   # top 15 by year desc
    births: list[HistoryItem]   # top 15 by year desc
    deaths: list[HistoryItem]   # top 15 by year desc

@dataclass
class HistoryItem:
    year: int
    text: str          # câmpul "text" din răspunsul Wikipedia (plain string)
    source_lang: str   # "ro" sau "en"
```

**Failure mode:** returnează `None` la eșec permanent (identic cu `fetch_weather`). Secțiunea va folosi fallback-ul existent dacă `None`.

### Integrare pipeline

**În `generator/main.py`:**
- `fetch_history()` se alătură lui `fetch_all_sources()` și `fetch_weather()` în `asyncio.gather()` — rulează **în paralel**, fără întârziere.
- Rezultatul `history` e pasat ca argument nou către `summarize()`.

**În `generator/prompt.py`:**
- Nouă secțiune `Section` în lista `SECTIONS`, după `football_eu`, înainte de outro:
  ```python
  Section(
      key="history",
      heading_ro="AZI ÎN ISTORIE",
      intro_phrase="Înainte de a încheia, câteva momente din istoria zilei de astăzi.",
      target_words=150,
      min_words=120,
      guidance=(
          "Alege 2-3 momente istorice relevante. Prioritizează evenimentele "
          "românești dacă există. Stil conversațional, „știați că" — nu listă "
          "seacă. Scrie anii în litere (ex. „o mie nouă sute patruzeci și cinci")."
      ),
      closing_rule=None,  # ca oricare secțiune non-meteo, fără wrap-up
  )
  ```
- `build_section_user_prompt` e extins să accepte `history: Optional[HistoryCandidates]` și, pentru secțiunea `history`, să serializeze candidații (ev+nașteri+decese) în prompt-ul user.
- Secțiunea `history` ignoră `items` și `weather` (primește doar `history`).

**În `generator/summarize.py`:**
- Semnătura `summarize()` primește un parametru nou: `history: Optional[HistoryCandidates] = None`.
- `_call_section` pasează `history` mai departe către `build_section_user_prompt` când `section.key == "history"`.
- Dacă `history is None`, secțiunea primește fallback-ul generic `_SECTION_FALLBACK` fără apel OpenAI (economisim un call inutil).

### Cost

- 1 request Wikipedia/zi (gratuit)
- 1 apel OpenAI suplimentar (~150 cuvinte ieșire, ~400 cuvinte intrare pentru candidați): **~$0.01/zi**
- Total nou: $0.07/zi în loc de $0.06/zi

### Failure mode

Dacă doar secțiunea history eșuează → ia `_SECTION_FALLBACK` („Din păcate, pentru această secțiune nu avem informații disponibile astăzi. Trecem mai departe."). Se contorizează în `failed_sections`. Pragul `max_section_failures=2` rămâne neschimbat — o secțiune eșuată nu strică buletinul.

### Exemplu de output

> „Înainte de a încheia, câteva momente din istoria zilei de astăzi. Știați că pe douăzeci aprilie, în o mie nouă sute cinci, scriitorul francez Jules Verne publica ultimul său roman? Tot pe această zi, în o mie nouă sute nouăzeci și nouă, a avut loc masacrul de la liceul Columbine din statul Colorado. Iar în o mie nouă sute cincizeci și unu, se năștea compozitorul italian Luca Turilli."

---

## Feature 2: Memorează poziția

### Scop

Dacă tata apasă pauză la minutul 7:23 (sau închide app-ul), când revine în aceeași zi, audio se poziționează automat la 7:23 cu un indicator scurt „Continuă de la 7:23". A doua zi (buletin nou) → start de la zero automat.

### Arhitectură

Modificare **100% frontend** în `pwa/app.js`. Fără modificări pe server, fără cost adițional.

**Stocare:** `localStorage`

- **Cheie:** `stiritata:position:<YYYY-MM-DD>` unde data vine din `latest.json` (câmpul `date`, nu `Date.now()`).
- **Valoare:** secundele de redare (float), serializate ca string.

**Momente de salvare:**
1. pe `audio.pause` event
2. pe `audio.timeupdate` throttled la 10 secunde (pentru crash / battery dead)
3. pe `document.visibilitychange` când devine `hidden` (ieșit din PWA pe telefon)
4. șters pe `audio.ended` (a ascultat tot → data viitoare începe de la zero)

**Restore la init:**

Ordinea executării după ce manifestul e descărcat:
1. Citește `localStorage.getItem('stiritata:position:' + manifest.date)`
2. Dacă nu există sau e `<= 10` secunde → nu face nimic (prag anti-blip)
3. Altfel:
   - Așteaptă `audio.loadedmetadata` (pentru ca `audio.duration` să fie disponibil)
   - Dacă poziția salvată `>= audio.duration` → ignoră (desincronizare), start de la zero
   - Altfel:
     - `audio.currentTime = position`
     - Afișează notificare: **„Continuă de la M:SS"**
       - font 14px, culoare discretă
       - poziționată deasupra butonului play
       - fade-out 5 secunde (CSS transition pe `opacity`)

**Important:** nu se pornește redarea automat. iOS/Android PWA interzic autoplay fără interacțiune utilizator. Tata apasă play și pornește de la poziția restaurată.

**Cleanup:**

La init, după citirea manifestului:
```js
const currentKey = 'stiritata:position:' + manifest.date;
Object.keys(localStorage)
  .filter(k => k.startsWith('stiritata:position:') && k !== currentKey)
  .forEach(k => localStorage.removeItem(k));
```
Evită acumulare de chei vechi peste luni de folosire.

### Cazuri limită

| Caz | Comportament |
|-----|--------------|
| Buletin nou mâine (date se schimbă) | Cheia veche ștearsă la cleanup → start de la 0 |
| `localStorage` indisponibil (modul privat) | try/catch global, feature silențios oprit, app funcționează normal |
| `audio.duration` încă `NaN` la load | așteptăm `loadedmetadata` event |
| Poziție salvată > durata audio | ignorăm, start de la 0 |
| Două taburi deschise simultan | ultimul care salvează câștigă; scenariu nerelevant pentru Ilie |
| Valoare localStorage coruptă (ex. manual) | `parseFloat` + `isFinite` check, fallback la 0 |

### Testabilitate

**Manual:** DevTools → Application → Local Storage → verificare cheie + valoare; test de reload cu poziție setată.

**Automat:** Nu adăugăm teste automate pentru acest feature — cod frontend scurt (~80 linii), comportament verificabil vizual în 30 secunde. Ar fi overkill să introducem Playwright/Vitest doar pentru asta.

### Cost

Zero — totul pe client.

---

## Ordine de implementare

1. **Feature 1** primul (backend, izolabil, testabil cu mock)
   - `fetch_history.py` + teste unitare (mock httpx)
   - Extensie `prompt.py` + teste pentru noua secțiune
   - Integrare `summarize.py` + `main.py` + teste
   - Run live pentru verificare audio

2. **Feature 2** după (frontend pur)
   - Modificări `pwa/app.js`
   - CSS pentru hint-ul „Continuă de la M:SS"
   - Verificare manuală pe desktop și pe telefonul tatei

Cele două feature-uri sunt **complet independente** — se pot deploya în ordine inversă sau separat fără probleme.

## Verificare de succes

**Feature 1:**
- [ ] Buletinul de mâine conține o secțiune istorică de ~1 minut înainte de outro.
- [ ] Conține anul scris în litere (verificabil în `latest.txt`).
- [ ] Nu conține wrap-up („Acestea au fost...") — strip-ul existent se aplică automat.
- [ ] Dacă Wikipedia pică, buletinul tot se generează (secțiune fallback).

**Feature 2:**
- [ ] Apăs pauză la 2:30, reîncarc pagina → audio e la 2:30, hint „Continuă de la 2:30" apare 5s apoi dispare.
- [ ] Aștept ca buletinul să se termine (sau skip la final) → cheia localStorage e ștearsă.
- [ ] Rulez GitHub Action manual pentru a genera buletin nou → deschid app-ul → start de la 0 (cheia veche ștearsă la cleanup).

---

## Open questions

Niciuna — toate deciziile de design au fost luate în brainstorm.
