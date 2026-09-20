# Gacha Tracker

[![CI](https://github.com/Haencky/Gacha-Tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Haencky/Gacha-Tracker/actions/workflows/ci.yml)

Gacha Tracker especially for Honkai: Star Rail and other games.

Support for each game lives in its own Django app that registers itself with the
game-agnostic `core` app, so the core never needs to know about a specific game.

## Requirements

- Python 3.14
- Node.js 20+ — builds the Tailwind/daisyUI stylesheet
- PostgreSQL 14+ — optional, SQLite is the default
- GNU gettext — only needed to work on translations

## Local development setup

```bash
git clone git@github.com:Haencky/Gacha-Tracker.git
cd Gacha-Tracker

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

cp .env.example .env               # Windows: Copy-Item .env.example .env

npm install
npm run css:build

python manage.py migrate
python manage.py runserver
```

The start page is then served at <http://127.0.0.1:8000/>.

Two steps above are easy to miss:

- **`.env` is required.** `SECRET_KEY` has no default, and the app refuses to
  start without it. `.env.example` ships a development key — generate your own
  before deploying anywhere public.
- **`static/css/app.css` is a build artifact** and is not in the repository.
  Without `npm run css:build` every page renders unstyled. Use
  `npm run css:watch` while working on templates.

## Database

SQLite is the default and needs no configuration. It runs in WAL mode with
`transaction_mode="IMMEDIATE"`, which keeps concurrent reads working while a
write is in flight.

PostgreSQL is supported as an alternative — point `DATABASE_URL` at it:

```bash
DATABASE_URL=postgres://user:password@localhost:5432/gacha
```

Both databases are covered by the test matrix in CI. SQLite is lenient about
types, so running against PostgreSQL catches problems (such as integer overflow
on 19-digit warp IDs) before anyone switches.

## Tests and linting

```bash
pytest                      # test suite
ruff check .                # lint
ruff format --check .       # formatting
djlint . --lint             # template lint
djlint . --check            # template formatting
```

Drop `--check` from the `ruff format` and `djlint` calls to apply fixes instead
of only reporting them. CI runs all five on every push and pull request.

## Translations

The UI is written in English and translated with Django's i18n framework. This
needs GNU gettext on your PATH (`choco install gettext` on Windows,
`apt install gettext` on Debian/Ubuntu):

```bash
python manage.py makemessages -l de     # collect strings into locale/de/
python manage.py compilemessages        # build the .mo files Django reads
```

Item and banner names come from imported UIGF data, not from the message
catalogs — only the surrounding UI is translated.

## License

MIT — see [LICENSE](LICENSE).
