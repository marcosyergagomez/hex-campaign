# Hex Campaign

A browser campaign map for tabletop miniature games. Players lock secret moves on a hex map. When every player has locked an order, the server resolves the turn. Battles are played with miniatures on a real table, and the result is then recorded.

The campaign rules are original. The project does not include official artwork or copied rule text.

## Stack

- Python for the campaign rules, with no web framework inside those rules
- Django for the database, users, and admin
- FastAPI as the only HTTP API the browser calls
- React and TypeScript for the interface
- PostgreSQL

## Status

PostgreSQL runs in Docker. Django migrations create the tables, including the campaign row that stores the living state.

A person registers with email, a unique alias, a date of birth, and sex. The account stays unverified until the one-time link in the mailbox is confirmed. Birth date and sex are shown in the Django admin only.

## Architecture

The browser talks to one API. FastAPI owns that HTTP contract. Django owns persistence, accounts, and the admin. Registration and email confirmation are the routes under `/api`. A pure Python package, `hexcampaign.domain`, owns movement, vision, fortresses, and victory. FastAPI asks that package to resolve a turn and Django stores the result.

One process serves both frameworks. The game is one product, and a recruiter should be able to run it as one product.

## Local database

Copy `.env.example` to `.env`. From the repository root, start PostgreSQL and Mailpit, then apply the migrations:

```bash
docker compose up -d postgres mailpit
cd backend
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
python manage.py migrate
pytest
uvicorn config.asgi:application --reload
```

On macOS or Linux, activate the virtual environment with `source .venv/bin/activate`.

`migrate` creates the tables on an empty database and applies later changes without deleting campaigns. The Docker volume keeps the data between restarts. Mailpit accepts the confirmation message on port 1025 and shows it at http://localhost:8025. The link uses `API_ORIGIN`.

## Español

Mapa de campaña en el navegador para partidas de miniaturas. Los jugadores cierran órdenes en secreto. El servidor las resuelve cuando todos han cerrado. La batalla se juega en la mesa y después se anota el resultado.

Las reglas de campaña son propias. No hay arte oficial ni texto de reglamento copiado.

El alta pide correo, alias, fecha de nacimiento y sexo. El correo se confirma con un enlace de un solo uso. La fecha y el sexo solo se ven en el admin.
