# AGENTS.md

Instrucciones para modificar este repositorio. El arranque local está en `README.md`. Las reglas de juego y el contrato del servidor están en `docs/`.

## Proyecto

Hex Campaign es un mapa de campaña en el navegador para partidas de miniaturas. Los jugadores cierran órdenes en secreto. El servidor las resuelve cuando todos han cerrado. La batalla se juega en la mesa y después se anota el resultado. La mesa es de 2 a 4 jugadores.

Antes de cambiar comportamiento, lee el documento que ya lo describe:

- `docs/reglas-de-campana.md` — reglas de juego
- `docs/requisitos-tecnicos-backend.md` — cómo las sostiene el backend

Las reglas de campaña son propias. El repositorio no incluye arte oficial ni texto de reglamento copiado.

## Dónde vive cada cosa

- `backend/src/hexcampaign/domain/` — reglas puras. Devuelven un código (`DomainError`), nunca una frase ni una respuesta HTTP.
- `backend/api/` — único HTTP que llama el navegador (FastAPI). Traduce cada código a una frase española fija.
- `backend/apps/` — Django: cuentas, persistencia y admin. La partida viva está en el JSON de la campaña.
- `backend/apps/campaigns/projection.py` — columnas de listado copiadas del documento. Se rellenan en el mismo `save`.
- `frontend/` — React y TypeScript. Vite en el puerto 5173 reenvía `/api` a uvicorn.
- `shared/terrain.json` — única tabla de terrenos. La leen el dominio y `frontend/src/game/hex/terrainContract.ts`.

Si el código y el documento de `docs/` dicen cosas distintas, actualiza los dos en el mismo cambio.

## Límites

Antes de modificar más de 3 archivos o alterar un contrato entre backend y frontend,
presenta el plan de archivos y espera confirmación.

`hexcampaign.domain` permanece libre de Django, FastAPI y Django REST framework. Lo vigila `backend/tests/domain/test_boundaries.py`. Un caso de juego nuevo entra primero en el dominio. La API y la pantalla solo lo adaptan.

Un proceso sirve los dos frameworks. El navegador habla solo con FastAPI.

Cada escritura de juego comprueba la sesión de jugador, el origen y la cabecera `X-CSRF-Token`, repite el número de revisión y bloquea la fila. Si la campaña cambió, la respuesta es 409 y no se aplica nada.

El listado, el pulso y la vista previa de una invitación leen columnas (`phase`, `revision`, `turn`, `seat_limit`, `occupied`). Una consulta nueva de listado añade el campo en `projection.py` y lo rellena en el mismo `save`.

La respuesta de juego es la vista de ese jugador. Las órdenes ajenas permanecen ocultas, también para el propietario.

## Módulos que no se vuelven a juntar

El dominio ya está partido por trabajo. Un caso nuevo entra en el módulo de ese trabajo. No vuelve a `game.py` ni se pega al final de un vecino porque el archivo ya estaba abierto.

- `game.py` — tipos del documento (`Game`, `Member`, `Army`, `Fortress`, `Battle`) y las consultas (`find_*`, `require_*`, `bump`, `notice`). Sin reglas de turno, lobby ni marcha. `to_dict` y `from_dict` viven en `apps/campaigns/document.py`, que escribe `schema_version`. `apps/campaigns/telemetry.py` cuenta turnos resueltos, conflictos 409 y errores 500. No lo metas en `match.py`.
- `lobby.py` — fachada. Reclutamiento e identidad en `recruit.py`, colocación en `placement.py`, hojas y fichas en `muster.py`, casas y terreno donde se planta en `homes.py`.
- `turn.py` — fachada. Cerrar órdenes y simular el turno en `resolution.py`, anotar y juzgar batallas en `battle_report.py`, salida de jugadores en `departure.py`.
- `view.py` — fachada. Casillas, fichas y fortalezas visibles en `view_map.py`. Película de la marcha y batallas de la vista en `view_playback.py`.
- `march.py`, `clock_march.py`, `terrain_order.py`, `occupy.py` — resolución del movimiento. El plan que ve el jugador está en `frontend/src/game/hex/orders.ts` y tiene que coincidir. Lo vigilan `backend/tests/domain/test_movement_contract.py` y `frontend/tests/terrain-parity.test.ts`.
- `sight.py` — niebla y mirada.
- `roads.py` — caminos de la preparación.
- `terrain.py` — única lectura Python de `shared/terrain.json`.
- `maps.py`, `map_document.py`, `landscape.py`, `board.py`, `land.py`, `balance.py` — forma y equilibrio del mapa.
- `rules.py`, `identity.py`, `hexes.py`, `territory.py`, `units.py`, `phases.py`, `clock.py`, `chronicle.py`, `errors.py` — piezas pequeñas. No las absorbas en las grandes.

En el navegador el tablero está partido igual:

- `terrainContract.ts` — única lectura TypeScript de `shared/terrain.json`.
- `orders.ts` — plan de ruta. No copia la tabla de costes.
- `courses.ts` — contornos (ríos, orillas, territorio).
- `geometry.ts` y `disk.ts` — geometría axial.
- `TerrainArt.tsx`, `tokens.tsx`, `useHexPaint.ts`, `useMarchFilm.ts`, `boardTokens.ts` — pintura, fichas y película.
- `boardTypes.ts` — tipos del tablero, medida y tinte de marca.
- `useBoardCamera.ts` y `BoardTools.tsx` — zoom, recentrado y desplazamiento de la cámara.
- `useBoardPointer.ts` — puntero a hexágono, `spotAtRef` y arrastre de ficha.
- `useBoardCaption.ts` — pie con el terreno o la nota de la ficha.
- `HexTerrainLayer.tsx` — terreno, ríos, lagos, caminos, puentes y niebla.
- `TokenLayer.tsx` — fichas, cruces de colocación, velo de mirada y selección.
- `useMarchGlide.ts` — deslizamiento de la marcha ya resuelta. No entra en `useMarchFilm.ts`.
- `OrderLayer.tsx` — trazos, rutas de órdenes y espadas del choque.
- `HexBoard.tsx` — compone el tablero y el puntero. No recupera la pintura, los contornos ni el plan de ruta.
- `frontend/src/pages/campaign/` — sesión, órdenes, preparación, selección y paneles. `CampaignDetailPage.tsx` solo los compone.

`game.py`, `landscape.py`, `HexBoard.tsx`, `courses.ts`, `readCampaign.ts`, `MapEditorPage.tsx` y `CreateCampaignPage.tsx` ya están en el techo de su trabajo. `lobby.py`, `view.py` y `turn.py` solo reexportan: el trabajo nuevo entra en el hermano de esa tarea (`recruit`, `placement`, `muster`, `homes`, `view_map`, `view_playback`, `resolution`, `battle_report`, `departure`). Un arreglo de ese mismo trabajo puede añadir unas líneas. No se fusiona un hermano de vuelta para dejarlo junto.

## Terreno

`shared/terrain.json` es el único contrato de terrenos. Lo leen solo `backend/src/hexcampaign/domain/terrain.py` y `frontend/src/game/hex/terrainContract.ts`. El resto del dominio y de la interfaz llama a esas funciones. Nadie más importa el JSON ni repite un coste, una mirada, un terreno infranqueable o un bono de explorador.

Las claves publicadas son `grounds`, `impassable`, `exit`, `gaze`, `base_gaze`, `explorer_move_bonus`, `explorer_gaze_bonus` y `open_grounds`. Los identificadores de terreno ya publicados no se renombran. Un terreno nuevo es un id nuevo en ese JSON.

El archivo tiene que seguir cumpliendo lo que `terrain.py` rechaza al arrancar: `impassable`, `gaze` y `open_grounds` son subconjuntos de `grounds`; `exit` cubre cada terreno transitable y ninguno infranqueable. Una carretera o un puente deja el hexágono en coste 1. Eso vive en las funciones de `terrain.py` y `terrainContract.ts`, no en una segunda tabla.

Después de tocar el JSON, desde `backend/`:

```bash
pytest tests/domain/test_terrain.py tests/domain/test_movement_contract.py tests/campaigns/test_map_api.py
```

Y desde `frontend/`:

```bash
npm run test:maps
```

## Textos que ve el jugador

La API JSON responde en español. El navegador traduce esa frase cuando está en el catálogo.

Una frase nueva de la API sigue este camino:

1. Se escribe en el diccionario HTTP de campañas o mapas (`backend/api/campaigns/http.py`, `backend/api/maps.py`) o como constante de cuentas (`backend/apps/accounts/validation.py`).
2. Gana una clave en `frontend/src/i18n/en.ts`. Esa clave define el tipo `MessageKey`.
3. Se traduce en `es.ts`, `fr.ts`, `it.ts` y `de.ts`.
4. Si la interfaz debe reconocer la frase del servidor, la clave entra en `fromSpanish` de `frontend/src/i18n/catalog.ts`. La frase de `es.ts` coincide carácter por carácter con la de la API. Dos claves no comparten la misma frase española.

Los correos y las páginas de confirmación viven aparte, en `backend/apps/accounts/languages.py`, con las cinco lenguas.

## Sesión

`POST /api/session` deja `__Host-session` (HttpOnly) y `__Host-csrf`. Cerrar sesión devuelve el segundo valor en `X-CSRF-Token`. En la base solo se guarda un HMAC-SHA256 de cada secreto, con la clave `SESSION_PEPPER`.

Correo desconocido, correo sin confirmar y contraseña incorrecta reciben el mismo 401. En local, `API_ORIGIN` es `http://localhost:5173`. Esta cookie es distinta de la sesión del admin de Django.

Deja los secretos, las cookies y el pepper fuera de logs, respuestas y commits. `.env` permanece fuera del repositorio.

## Comprobar un cambio

Desde `backend/`, con el entorno activo (en Windows, `.venv\Scripts\activate`):

```bash
ruff check .
mypy --strict
pytest --cov=hexcampaign --cov=api --cov=apps --cov-report=term-missing --cov-fail-under=86
```

`mypy --strict` exige tipos estrictos en `hexcampaign` y en `api`. `apps` y `config` conservan el nivel anterior, declarado en `backend/pyproject.toml`, para que Django no entre en ese modo. El suelo de cobertura es 86.

Las pruebas de dominio no usan base de datos. Las de la API usan PostgreSQL, levantado desde la raíz con `docker compose up -d postgres`.

Desde `frontend/`:

```bash
npm run lint
npm test
```

`npm test` también comprueba el suelo de cobertura de `src/game/hex/` (sentencias 42, ramas 34, funciones 47, líneas 45) y de `src/api/` (sentencias 1, ramas 0, funciones 0, líneas 1).

`npm run build` ejecuta el comprobador de TypeScript y el empaquetado. Ejecuta el comprobador del lado que modificaste y deja el resultado verde antes de dar el cambio por hecho.

## Estilo

Python 3.12, líneas de 100 caracteres, Ruff como en `backend/pyproject.toml`. TypeScript sin `any` y sin `console` en `src/` y `tests/`. Componentes de función. Comentarios del código en inglés, como el resto del repositorio.

Conserva los identificadores ya publicados: fases, terrenos y códigos de error. Añade la prueba del comportamiento que toques.
