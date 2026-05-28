# Știri Tată — Voice & PWA Feature Parity with Știri Cristi

**Date:** 2026-05-28
**Status:** Approved design

## Goal

Bring Știri Tată up to the same *functionality* as Știri Cristi — multi-voice
TTS (including a female voice) and the newer PWA player features — **without**
changing Știri Tată's own news topics, sources, weather location, or branding.

The two apps diverged: Știri Cristi gained a voice picker, playback-speed
control, a weather-driven theme, and a headlines list, while Știri Tată kept
chapter navigation (which Știri Cristi dropped). This change is an additive
port: Știri Tată keeps its chapters and gains everything Știri Cristi has.

## Non-goals

- No change to news categories, RSS sources, prompt, or weather city (Reșița).
- No change to the daily schedule or GitHub Actions trigger logic.
- Do **not** port `pronunciation.py` — it is unused dead code in Știri Cristi
  (a markdown file, imported nowhere). The real romanization lives in
  `text_utils.py`.

## Approach (chosen: surgical port)

Add only the missing capabilities to Știri Tată, preserving its identity
(title "Știri Tată", chapters, Reșița weather, `stiritata:` localStorage keys).

## Voices

Three voices with an in-PWA picker, mirroring Știri Cristi:

| id    | label | gender | backend | model / voice          |
|-------|-------|--------|---------|------------------------|
| mihai | Mihai | male   | piper   | `ro_RO-mihai-medium`   |
| alina | Alina | female | edge    | `ro-RO-AlinaNeural`    |
| emil  | Emil  | male   | edge    | `ro-RO-EmilNeural`     |

- **Default voice: `alina`** (female). The generator runs with
  `TTS_VOICES=alina,mihai,emil`; the first listed that succeeds becomes the
  fallback `latest.mp3`, so the default playback voice is Alina.
- Each voice produces `public/latest-<id>.mp3`. The manifest lists all
  successfully generated voices under `voices`.

## Backend changes (`generator/`)

1. **`requirements.txt`** — add `edge-tts>=6.1.10`.
2. **`tts.py`** — replace with the Știri Cristi version: `PiperConfig`,
   `EdgeTTSConfig`, `synthesize`, `synthesize_edge`, the `VoiceSpec` registry
   (`AVAILABLE_VOICES`, `VOICE_BY_ID`), and `synthesize_voice` dispatcher.
3. **`text_utils.py`** — add `romanize_for_tts` and `romanize_for_edge_tts`
   plus their substitution tables (`_PHONETICS`, `_EDGE_CORRECTIONS`) from
   Știri Cristi. The shared date/number/dedup helpers are identical and stay.
4. **`build_manifest.py`** — replace with the Știri Cristi version, which
   already supports `chapters` **and** `headlines` / `weather_summary` /
   `voices`. Chapters remain supported, so nothing is lost.
5. **`.github/workflows/daily.yml`** — add `TTS_VOICES: alina,mihai,emil` to
   the `env:` of the generator run step (Știri Cristi uses `mihai,alina`;
   Știri Tată leads with `alina` so the default `latest.mp3` is the female
   voice). No other workflow change needed — the Piper model cache step stays.
6. **`main.py`** — port the multi-voice loop and `_resolve_voices`:
   - `--voices` flag / `TTS_VOICES` env var (default `alina`).
   - Generate one MP3 per voice; first success → `latest.mp3`.
   - Keep Știri Tată's existing single-city weather call
     (`fetch_weather(lat, lon, city)`) and `_build_chapters()`.
   - Manifest now also carries `headlines` (titles of top items),
     `weather_summary` (`weather.description`), `voices`, **and** `chapters`.

## Frontend changes (`pwa/`)

Port the four player features Știri Cristi has and Știri Tată lacks, while
keeping Știri Tată's chapter UI:

1. **Voice picker** — 🎙 button, `#voice-panel`, `#voice-options`; reads
   `manifest.voices`, persists choice in `localStorage` key
   `stiritata:voice`, swaps `audio.src` while preserving position.
2. **Playback speed** — cycle button 1× / 1.25× / 1.5× / 2×.
3. **Weather theme** — `applyWeatherTheme(manifest.weather_summary)` sets a
   `body` class; corresponding CSS theme classes ported to `style.css`.
4. **Headlines list** — "În ediția de azi:" populated from
   `manifest.headlines`.
5. **Play button playing-state** class (`play-btn--playing`).

Preserve: chapter buttons (`renderChapters` / `updateActiveChapter` /
`seekTo`), position persistence, wake lock, media session — all with Știri
Tată branding ("Știri Tată") and `stiritata:` localStorage prefixes.

`index.html`, `app.js`, `style.css` updated accordingly. `manifest.webmanifest`
and `sw.js` stay as-is except any cache-list additions for new asset names if
needed (none expected — same filenames).

## Voice models / assets

- Piper `ro_RO-mihai-medium` model already handled by
  `scripts/download_voice.sh` (unchanged).
- Edge voices need no local model (neural, fetched at generation time) but
  require network access during the GitHub Actions run — already available.

## Testing

- Port/adjust unit tests from Știri Cristi covering `synthesize_voice`
  dispatch, `_resolve_voices`, and manifest fields (`voices`, `headlines`).
- Keep Știri Tată's existing chapter / manifest tests green.
- Manual: run `python -m generator.main --voices alina,mihai,emil`, confirm
  three `latest-*.mp3` files, a `latest.mp3` (= Alina), and a manifest with
  `voices`, `headlines`, `weather_summary`, and `chapters`.
- Manual PWA: load locally, verify voice picker switches audio, speed button
  cycles, weather theme applies, headlines render, chapters still jump.

## Risks

- **Edge-tts network dependency** at generation time. Mitigation: existing
  Piper (Mihai) remains in the voice set, and the multi-voice loop already
  tolerates per-voice failure, falling back to any voice that succeeds.
- **Manifest shape change** consumed by an older cached service worker.
  Mitigation: manifest is cache-busted (`?v=<date>`); new fields are additive
  and the frontend guards each with presence checks.
