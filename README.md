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

A person registers with email and a password of 12 to 128 characters, plus a unique alias of 3 to 24 letters, digits, or underscore. The date of birth must make them at least 16. Sex is one of woman, man, other, or undisclosed. If that email belongs to a confirmed account, ignoring case and surrounding spaces, the API responds with 422 and “Este correo ya está registrado.” and leaves the account unchanged. An unconfirmed signup can be replaced by a later registration for the same email: the previous link stops working and a new message is sent. Confirming the link requires the password from that signup. Staff, inactive, and admin-created accounts are left untouched. A taken alias is reported when it belongs to someone else. Birth date and sex are shown in the Django admin only.

A confirmed, active player signs in with `POST /api/session`. The response sets `__Host-session` (HttpOnly) and `__Host-csrf`. Logout sends that second value back in the `X-CSRF-Token` header. The database stores only an HMAC-SHA256 of each secret, keyed with `SESSION_PEPPER`, so a copy of the database is not a usable cookie. The cookie lasts at most 180 days and ends after 60 days without a visit. The campaign stays stored either way. One account may keep 10 sessions, and any of them can play every campaign. Logout closes only that browser. Changing the password or deactivating the account closes all of them. An unknown email, an unconfirmed email, and a wrong password all get the same 401. The `Origin` or `Referer` must be `API_ORIGIN`, and the map has to be served on that origin. This cookie is not the Django admin session.

## Architecture

The browser talks to one API. FastAPI owns that HTTP contract. Django owns persistence, accounts, and the admin. Registration and email confirmation are the routes under `/api`. Campaign rules belong in `hexcampaign.domain`, which does not import a web framework.

One process serves both frameworks.

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

Swagger is at http://127.0.0.1:8000/api/docs while `DEBUG` is on. It is absent when debug is off.

On macOS or Linux, activate the virtual environment with `source .venv/bin/activate`.

`migrate` creates the tables on an empty database and applies later changes without deleting campaigns. The Docker volume keeps the data between restarts. Mailpit accepts the confirmation message on port 1025 and shows it at http://localhost:8025. The link uses `API_ORIGIN`. `config.settings.production` refuses to start unless that origin is `https`, `DJANGO_SECRET_KEY` is a unique secret of at least 50 characters, and `SESSION_PEPPER` is a different secret of that length. The sample pepper in `.env.example` is refused in production.

## Español

Mapa de campaña en el navegador para partidas de miniaturas. Los jugadores cierran órdenes en secreto. El servidor las resuelve cuando todos han cerrado. La batalla se juega en la mesa y después se anota el resultado.

Las reglas de campaña son propias. No hay arte oficial ni texto de reglamento copiado.

El alta pide correo, contraseña de 12 a 128 caracteres, alias de 3 a 24 letras, números o guion bajo, fecha de nacimiento con un mínimo de 16 años, y sexo (`woman`, `man`, `other` o `undisclosed`). Si el correo ya está confirmado, sin distinguir mayúsculas ni espacios alrededor, la respuesta es 422 con «Este correo ya está registrado» y la cuenta no cambia. Un alta sin confirmar se puede repetir: el enlace anterior deja de valer y se envía otro. Para confirmar hay que escribir la contraseña del alta. Las cuentas de administración, las inactivas y las creadas en el admin no se sustituyen. Si el alias pertenece a otra persona, se avisa. La fecha y el sexo solo se ven en el admin.

Quien ya confirmó el correo y tiene la cuenta activa entra con `POST /api/session`. La respuesta deja `__Host-session` (HttpOnly) y `__Host-csrf`. Para cerrar sesión hay que devolver ese segundo valor en la cabecera `X-CSRF-Token`. En la base solo se guarda un HMAC-SHA256 de cada secreto, con la clave `SESSION_PEPPER`: una copia de la base no sirve para entrar. La cookie dura como mucho 180 días y se cierra sola si pasan 60 días sin visita. La campaña sigue guardada. Una cuenta puede tener 10 sesiones y cualquiera de ellas sirve para todas las campañas. Cerrar sesión solo cierra ese navegador. Cambiar la contraseña o desactivar la cuenta cierra todas. Si el correo no existe, no está confirmado o la contraseña no coincide, la respuesta es el mismo 401. El `Origin` o el `Referer` tienen que ser `API_ORIGIN`, y el mapa tiene que servirse en ese origen. Esta cookie no es la del admin de Django.
