# Știri Tată — Design Document

**Data:** 2026-04-19
**Autor:** Cristi (cu Claude)
**Status:** Aprobat la brainstorming, urmează spec review + plan de implementare

---

## 1. Context & Scop

Aplicație simplă pentru tatăl utilizatorului (Android, telefon + tabletă) care, la apăsarea unui buton Play, redă un buletin de știri vocal, în limba română, de 10-15 minute, acoperind:

- **Politică**: locală (Reșița / Caraș-Severin), națională, internațională
- **Fotbal**: România (SuperLiga, naționala) + european cu focus pe Big Five (Premier League, La Liga, Bundesliga, Serie A, Ligue 1) + UEFA Champions League / Europa League / Conference League + World Cup / European Championship
- **Meteo local**: Reșița

### Constrângeri principale

- **Cost minim**: buget țintă sub $5/lună
- **Zero mentenanță zilnică**: rulează singur, fără intervenția utilizatorului sau a autorului
- **Limba română, voce naturală**: criteriu critic de calitate
- **UX pentru vârstnic**: un buton mare, un indicator al datei, control minim (Play/Pauză, opțional rewind/forward 30s)

### Pattern de utilizare

Un buletin nou se generează **o dată pe zi** (06:00 ora României). Tata îl poate asculta de mai multe ori în ziua respectivă; la apăsări repetate pe Play în aceeași zi primește **același** buletin (din cache local). A doua zi după 06:00 primește buletinul nou.

---

## 2. Criterii de succes

1. Tata deschide aplicația, apasă un buton uriaș Play, aude 10-15 min de știri clare, în română, relevante pentru el.
2. Funcționează zilnic, automat, fără intervenție.
3. Cost total lunar < $5.
4. Tata nu e expus niciodată la concepte tehnice (URL-uri, cache, descărcare, update-uri).

---

## 3. Arhitectura

Sistemul are **două componente decuplate**, care comunică doar printr-un URL public:

```
┌─────────────────────────────────┐         ┌─────────────────────────────┐
│   GENERATOR (GitHub Actions)    │         │    PWA (telefon/tabletă)    │
│                                 │         │                             │
│   cron 03:00 UTC (06:00 RO)    │         │   HTML + JS + Service Worker│
│   ┌─────────────────────────┐  │         │   ┌─────────────────────┐   │
│   │ fetch news (RSS, x8)    │  │         │   │ check latest.json   │   │
│   │ fetch weather (OWM)     │  │         │   │                     │   │
│   │ summarize (ChatGPT)     │  │         │   │ if new → fetch MP3  │   │
│   │ TTS (Piper, local RO)   │  │         │   │ cache offline       │   │
│   │ publish to gh-pages     │──┼─────────┼──▶│                     │   │
│   └─────────────────────────┘  │   URL   │   │ Play/Pauză/Seek     │   │
│                                 │ public  │   └─────────────────────┘   │
└─────────────────────────────────┘         └─────────────────────────────┘
                                                        ↑
                                                        │
                                                     (tata)
```

Generatorul și PWA-ul nu știu unul de altul dincolo de formatul manifestului JSON. Poți înlocui oricare dintre ele independent.

---

## 4. Generatorul zilnic

### 4.1 Structura repo

```
stiritata/
├── .github/workflows/daily.yml       # cron 0 3 * * *
├── generator/
│   ├── fetch_news.py                 # RSS + dedup + filtrare ultimele 24h
│   ├── fetch_weather.py              # OpenWeatherMap → Reșița
│   ├── summarize.py                  # ChatGPT (gpt-4o-mini) cu prompt structurat
│   ├── tts.py                        # Piper TTS → MP3
│   ├── build_manifest.py             # latest.json
│   └── main.py                       # orchestrare
├── pwa/                              # HTML/CSS/JS + manifest.webmanifest + sw.js
├── public/                           # output publicat pe gh-pages
│   ├── index.html                    # PWA-ul copiat din pwa/
│   ├── latest.mp3
│   ├── latest.json
│   └── archive/
│       └── 2026-04-19.mp3            # istoric 7 zile
├── sources.yaml                      # lista RSS-uri, editabilă
└── requirements.txt
```

### 4.2 Fluxul workflow-ului

1. **Checkout + setup Python + install Piper** (cu cache de pași)
2. **Fetch news** (paralel, async) — toate RSS-urile din `sources.yaml`, filtrate la ultimele 24h, deduplicate după titlu normalizat
3. **Fetch weather** — un apel la OpenWeatherMap pentru Reșița
4. **Summarize** — un singur apel ChatGPT (model: `gpt-4o-mini`) cu tot contextul (news + weather) și prompt structurat care cere textul complet al buletinului pe secțiunile definite în §5
5. **TTS** — textul → Piper (voce `ro_RO-mihai-medium` sau `ro_RO-gabriela-medium`, decizie în timpul dezvoltării pe bază de ascultare comparativă) → MP3
6. **Build manifest** — `latest.json` cu `{date, duration, sections: [{title, start_seconds}], generated_at}`
7. **Publish** — commit pe branch-ul `gh-pages` în folderul rădăcină + `archive/<YYYY-MM-DD>.mp3` și păstrare ultimele 7 zile

### 4.3 Surse RSS (lista inițială din `sources.yaml`)

**Politică locală (Reșița / Caraș-Severin):**
- caon.ro
- banatulmontan.ro
- Caraș-Severin Expres (URL-ul RSS exact se confirmă la implementare)

**Politică națională:**
- digi24.ro
- hotnews.ro
- g4media.ro
- adevarul.ro

**Politică internațională:**
- bbc.com/news (international)
- reuters.com/world

**Fotbal România:**
- gsp.ro
- prosport.ro
- digisport.ro

**Fotbal european (Big 5 + cupe):**
- BBC Sport (football)
- ESPN (soccer)
- UEFA.com news

Sursele exacte (URL-uri RSS finale) se confirmă la implementare; dacă vreuna nu expune RSS, se omite sau se înlocuiește.

### 4.4 Prompt de sumarizare — principii

- Input: textele știrilor brute + obiectul meteo
- Output: **textul complet al buletinului**, gata de citit, pe secțiunile din §5
- Stil: neutru, calm, ca un prezentator de radio; propoziții scurte; fără anglicisme dacă există echivalent românesc; anii scriși ca "două mii douăzeci și șase" pentru TTS natural
- Anti-halucinație: promptul spune explicit *"folosește doar informații din textele primite; dacă o secțiune nu are știri, spune scurt «Astăzi nu sunt știri importante din X» și treci mai departe"*
- Lungimea țintă: ~2200-2500 cuvinte (≈ 10-15 min la ritm normal de citire)

### 4.5 Error handling

- **RSS picat**: log warning, continuă cu celelalte surse
- **ChatGPT eșuează**: retry ×2 cu backoff exponențial; dacă încă eșuează, păstrează MP3-ul de ieri (PWA-ul va continua să redea buletinul anterior)
- **Piper eșuează**: workflow-ul eșuează → GitHub trimite email automat la proprietarul repo-ului
- **OpenWeatherMap picat**: omite secțiunea meteo, menționează asta scurt în intro

### 4.6 Secrete (GitHub Secrets)

- `OPENAI_API_KEY` — cheia OpenAI
- `OPENWEATHER_API_KEY` — cheia OpenWeatherMap (se ia gratis la setup, tier gratis 1000 apeluri/zi)

**Notă de securitate**: cheia OpenAI din `GPT.txt` din repo-ul local trebuie **revocată și regenerată** după ce se setează în GitHub Secrets, pentru că a fost expusă într-un fișier plain-text.

---

## 5. Structura buletinului

Durată totală: **10-15 minute**. Ordinea fixă:

| # | Secțiune | Durată țintă | Conținut |
|---|----------|--------------|----------|
| 1 | **Intro** | ~15 sec | "Bună dimineața, tată. Astăzi este [ziua], [data]. Iată buletinul de știri." |
| 2 | **Meteo Reșița** | ~30 sec | Temperatură curentă, max/min ziua, precipitații, vânt |
| 3 | **Politică locală** | ~1.5-2 min | 2-3 știri din Reșița / Caraș-Severin (Caon, Banatul Montan, Caraș-Severin Expres) |
| 4 | **Politică națională** | ~2-3 min | 3-4 știri mari (Digi24, HotNews, G4Media, Adevărul) |
| 5 | **Politică internațională** | ~1.5-2 min | 2-3 știri majore (BBC, Reuters) |
| 6 | **Fotbal România** | ~2 min | SuperLiga (rezultate, clasament comentat scurt), naționala dacă are meciuri |
| 7 | **Fotbal — Big 5** | ~2-3 min | Rezultate weekend Premier League / La Liga / Bundesliga / Serie A / Ligue 1, comentarii scurte pe meciurile mari |
| 8 | **Fotbal — cupe europene** | ~1-2 min | Champions League / Europa League / Conference League, meciurile săptămânii |
| 9 | **Fotbal — turnee internaționale** | opțional | WC / EURO / preliminarii, doar dacă sunt active |
| 10 | **Outro** | ~10 sec | "Acesta a fost buletinul de astăzi. O zi bună!" |

---

## 6. Aplicația PWA

### 6.1 UI

Un singur ecran, minimalist:

- Titlu mare sus: "Știri Tată"
- Sub titlu, un text: "Buletin din [data, în română, citibil uman, ex. «19 aprilie»]"
- Buton Play ⇄ Pauză uriaș în centru (≈ 60% lățime ecran, minim 150×150 px)
- Bară de progres subțire sub buton
- Timp curent / timp total (ex: `04:23 / 13:45`)
- Butoane mai mici: `⏪ 30s` și `⏩ 30s`

**Principii vizuale:**
- Font minim 24px pentru text, buton enorm
- Contrast înalt (negru pe alb — dark mode nu e în scope inițial, poate fi adăugat ulterior dacă e cerut)
- Zero navigare, zero meniuri, zero setări vizibile

### 6.2 Comportament

- **Service Worker** cache-uiește `index.html`, CSS, JS și ultimul MP3 → aplicația funcționează offline după prima sincronizare.
- **La deschiderea aplicației**: PWA-ul face fetch silențios la `latest.json`. Dacă `date` e mai nou decât ce e în cache, descarcă noul MP3 în fundal. Tata nu vede nimic.
- **Apăsare Play**: redă instantaneu MP3-ul cache-uit.
- **Pauză / Continuare**: butonul comută între ▶ și ⏸.
- **Wake Lock API**: ecranul rămâne aprins cât rulează audio (opțional — dacă browser-ul nu suportă, fallback grațios).
- **Media Session API**: controalele apar în notification shade și pe lock screen.
- **Auto-resume**: dacă tata închide app-ul la minutul 5 și deschide iar, redă de la început (decizie simplă — "resume where left off" e complicat și nu e cerut).

### 6.3 Tech stack

- Vanilla HTML + CSS + JavaScript (fără framework)
- Fișiere: `index.html`, `style.css`, `app.js`, `sw.js`, `manifest.webmanifest`, iconițe PWA
- Hosted pe GitHub Pages (aceeași branch `gh-pages` ca MP3-urile)

### 6.4 Instalare (o singură dată)

1. Deschide Chrome pe telefon/tabletă
2. Accesează `https://<user>.github.io/stiritata/`
3. Meniu → "Add to Home Screen"
4. Iconița apare pe ecran, tata o apasă ca orice aplicație

---

## 7. Costuri estimate

| Componentă | Cost lunar estimat |
|------------|-------------------|
| ChatGPT gpt-4o-mini (1 apel/zi, ~5k tokens) | ~$0.30-0.50 |
| OpenAI TTS | — (nu folosim, Piper e local) |
| Piper TTS | **gratis** |
| OpenWeatherMap (1 apel/zi, tier gratis) | **gratis** |
| GitHub Actions (~90 min/lună din 2000 gratis) | **gratis** |
| GitHub Pages hosting | **gratis** |
| **TOTAL** | **< $1/lună** |

Bugetul țintă de < $5/lună e îndeplinit confortabil.

---

## 8. Riscuri identificate & mitigări

| Risc | Mitigare |
|------|----------|
| Piper pe GitHub Actions e prea lent (> 5 min) | La primul run măsurăm. Dacă e problematic: cache model Piper între rulări, sau trecem pe self-hosted runner pe PC-ul utilizatorului. |
| ChatGPT halucinează știri inexistente | Prompt anti-halucinație explicit (§4.4). Verificare manuală primele 3-4 buletine. |
| O sursă RSS moare | Workflow continuă cu celelalte, log warning. `sources.yaml` se actualizează manual când e nevoie. |
| Calitatea vocii Piper e insuficientă | Decizie acoperită: testăm `ro_RO-mihai-medium` și `ro_RO-gabriela-medium`. Dacă niciuna nu e acceptabilă, spec-ul se re-deschide cu opțiunea Azure Neural TTS (cost ~$5/lună). |
| Cheia OpenAI expusă în `GPT.txt` | Regenerare imediată + mutare în GitHub Secrets. |

---

## 9. Ce este explicit în afara scopului (YAGNI)

- Multi-user / profile multiple (e doar pentru tata)
- Personalizare conținut de către tata (alegere subiecte, durate)
- Dark mode (poate fi adăugat ulterior dacă e cerut)
- Offline fetch (PWA oricum funcționează offline din cache)
- Notificări push ("buletin nou disponibil")
- Controale de viteză playback (+10% / -10%) — se poate adăuga ulterior dacă tata cere
- Istoricul buletinelor expus în UI (arhiva există dar e internă, pentru fallback)
- Autentificare / parolă (app-ul e public, conținutul e generic)
- Alte limbi

---

## 10. Pași de implementare (ordine)

1. Creat repo GitHub `stiritata` (public)
2. Setare GitHub Secrets (`OPENAI_API_KEY`, `OPENWEATHER_API_KEY`)
3. Scris generatorul Python (fetch → summarize → TTS), testat local
4. Scris workflow GitHub Actions cu cron
5. Scris PWA (HTML/CSS/JS + SW + manifest)
6. Publicat pe GitHub Pages
7. Trigger manual al primului run → verificare MP3 (calitate voce, durată, corectitudine)
8. Instalare pe telefonul și tableta tatălui (Add to Home Screen)
9. Monitorizare 3-4 zile, ajustare prompt dacă e nevoie
10. Regenerare cheie OpenAI, revocare cheia expusă

---

## 11. Decizii luate în brainstorming

- **Platformă**: Android (telefon + tabletă)
- **Frecvență**: o generare/zi la 06:00 RO; tata poate asculta de mai multe ori același buletin
- **Durată buletin**: 10-15 minute
- **TTS**: Piper (local, gratis, voce românească)
- **Infrastructură generare**: GitHub Actions (cron)
- **Client**: PWA (nu aplicație nativă)
- **Sumarizare**: ChatGPT `gpt-4o-mini`
- **Sursă locală adăugată**: caon.ro
- **UI**: buton Play uriaș + data buletinului + progress + rewind/forward 30s
