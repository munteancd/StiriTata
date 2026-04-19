# Știri Tată

Aplicație zilnică de buletin de știri vocal în română.

- **Spec:** `docs/superpowers/specs/2026-04-19-stiritata-design.md`
- **Plan:** `docs/superpowers/plans/2026-04-19-stiritata-implementation.md`

## Dev setup

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows bash; use .venv/bin/activate on Linux/macOS
pip install -r requirements-dev.txt
cp .env.example .env  # completează cheile
pytest
```

## Rulare manuală locală

```bash
python -m generator.main
```

Output: `public/latest.mp3` + `public/latest.json`.
