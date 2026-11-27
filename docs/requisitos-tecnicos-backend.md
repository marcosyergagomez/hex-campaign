# Requisitos técnicos del backend, primera versión

Las reglas de juego están en `docs/reglas-de-campana.md`. Aquí queda cómo las sostiene el backend.

## Límites

Las reglas puras viven en `hexcampaign.domain` y no importan Django ni FastAPI. Django guarda. FastAPI adapta. Cada comando de juego comprueba la sesión de jugador, el origen y `X-CSRF-Token`, igual que el cierre de sesión.

El reglamento y la partida siguen en el JSON de la campaña: `apps/campaigns/document.py` lee y escribe ese documento, el dominio trabaja con los tipos, y la fila se bloquea en cada comando. El JSON guardado lleva `schema_version`. Un documento sin esa clave es el formato anterior y se lee igual que el actual. Lo que se consulta sin abrir el tablero no entra en el JSON. La tabla de plazas responde qué campañas tiene una cuenta (cuenta, papel, estado y alias). La fila de la campaña copia fase, revisión, turno, plazas (`seat_limit`) y ocupación; el listado, el pulso y la vista previa de una invitación leen solo esas columnas. Una consulta nueva de listado añade el campo en `apps/campaigns/projection.py` y se rellena en el mismo `save`, en vez de recorrer documentos.

La partida, las invitaciones y los avisos viven en módulos distintos (`match`, `invitations`, `notices`). FastAPI parte los endpoints en lobby, invitaciones y mesa.

El buscador acepta el id exacto. El nombre puede repetirse y no busca. La descripción es opcional, hasta 15 000 caracteres Unicode normalizados, admite saltos de línea y se guarda en el documento de la campaña.

El límite de tres aplica a cada plaza activa en campañas en curso (fases órdenes o batallas), no solo al creador. Crear o dejar una campaña en preparación no cuenta. Al pasar a órdenes, si algún asiento activo ya tiene tres en curso, la API responde 422 y no guarda el cambio. Quien lo provoca en su propia cuenta recibe «Ya tienes tres campañas en curso.» Si el invitado ya está en el tope, la frase es «Ese jugador ya tiene tres campañas en curso.» Una finalizada libera plaza. Seguir sentado después de ceder el puesto no abre otra plaza, porque la plaza activa sigue contando.

Invitar es otra cosa. El propietario busca por alias y envía un aviso dentro de la aplicación, o genera un enlace. El enlace lleva un token distinto del id. En la base solo se guarda su resumen, igual que el enlace de confirmación del correo. Quien tiene el enlace ocupa una plaza libre antes de empezar.

## Fases y arranque

Las fases son reclutamiento, colocación si colocan los jugadores, preparación si hay mapa de terrenos, órdenes, batallas pendientes y terminada. Revertir el último turno vuelve a órdenes. Las batallas de ese turno quedan en el registro marcadas como revertidas y dejan de aplicarse.

Hasta que el propietario pulsa empezar puede cambiar las reglas y bajar el número de plazas, sin bajar de 2 ni de las plazas ya ocupadas. Al empezar quedan fijas. En ese momento se nombran el resto de administradores. Antes solo administra quien creó la campaña.

Sin mapa de terrenos, el tablero sigue midiendo 19, 37 o 61 hexágonos axiales y no hay casillas infranqueables. Con un mapa guardado o generado, el tamaño es el del mapa (hoy 271, 397 o 547 en los preajustes) y el dominio aplica el catálogo de terrenos. El documento dibujado puede ser un subconjunto del disco: `game.hexes` copia esas casillas. `/api/map-scales` publica los preajustes. `POST /api/maps` con `cells` guarda un dibujo; `PUT /api/maps/{id}` actualiza solo dibujos; `POST /api/maps/{id}/copy` clona uno (también generado) a dibujo editable; `DELETE /api/maps/{id}` borra el atlas.

Tras empezar, si la campaña tiene terrenos, la fase pasa a preparación. Cada asiento avanza por su cuenta: fortaleza, caminos, ejércitos. Ahí viven `POST .../placement`, `POST .../roads`, `POST .../roads/clear` y `POST .../roads/ready`. Colocar la fortaleza y las fichas responde un delta (`kind: fort_delta`): revisión, fase, la fortaleza de ese jugador y sus fichas con casilla. Poner o quitar un camino responde un delta (`kind: roads_delta`): revisión, fase, contadores de camino, `road_ready` y solo las casillas tocadas. Guardar los caminos de un asiento lo pasa a sus ejércitos y devuelve la vista completa. El primer turno se abre cuando todos los asientos activos han terminado la preparación, no al cerrar los caminos.

Con la sesión abierta, el navegador escucha `GET /api/events` (eventos del servidor) para avisos y para el pulso de campaña: revisión, fase y plazas. El pulso puntual sigue en `GET /api/campaigns/{id}/pulse`.

## Órdenes, vista y escrituras

Una orden es el camino: hexágonos adyacentes, como máximo el movimiento —o los puntos de salida, con terrenos—. Vacía es quedarse quieto. Al cerrarla se rechaza lo que ese jugador ya puede ver como ilegal, y que dos ejércitos suyos terminen en la misma casilla. Un choque con un ejército que no ve no impide cerrar. Sale cuando todos han cerrado y el dominio simula el turno.

El navegador recibe la vista de ese jugador, calculada en el dominio. Las órdenes ajenas no salen, tampoco para el propietario. Con la visibilidad de ficha anónima se ocultan nombre, comandante, raza y lista. La crónica de movimientos y acciones vive en el mismo documento y no se recorta. La vista la incluye solo cuando la fase es terminada y quien mira tiene plaza. El admin de Django sí puede abrir el documento entero.

Cada respuesta de juego lleva un número de versión. La escritura lo repite. Si la campaña cambió, la API responde 409 con «La campaña ha cambiado. Vuelve a leerla.» y no aplica nada. La fila se bloquea durante el comando. Las escrituras de cuentas (alta, verificación, perfil y restablecer contraseña) comparten un tope, por defecto 30 por minuto y cliente (`ACCOUNT_POST_LIMIT`, ventana `ACCOUNT_POST_WINDOW_SECONDS`). Las de campañas, mapas e invitaciones tienen otro, por defecto 180 por minuto (`PLAY_POST_LIMIT`, `PLAY_POST_WINDOW_SECONDS`). Fuera de `DEBUG`, las respuestas pueden enviar HSTS.

## Batallas, plazos y cuentas

Cada luchador anota vencedor o empate y puede cambiarlo hasta que ambos coinciden. Si no coinciden, o si el plazo se ha cumplido, solo un administrador cierra. No hay un proceso en segundo plano. El reloj es UTC y el plazo son 24 horas por día desde que se abre el turno o la batalla. Al leer o escribir se comprueba si ya venció. El turno no avanza solo.

Desactivar la cuenta marca inactivas sus plazas en la misma transacción. El aviso al administrador es una nota dentro de la campaña. Esta versión no manda correo por eso. Borrar una cuenta no entra todavía.

El silencio configurable es de 1 a 5 turnos seguidos sin orden. La plaza queda inactiva y un administrador puede expulsarla. No se expulsa sola.

Si hay que pasar el propietario, el dominio sortea entre quien sigue y no está inactivo. El aleatorio se inyecta para poder probarlo. Si no queda nadie, la campaña se cierra sin vencedor.

## Errores, topes y pruebas

El dominio devuelve un código. La API lo traduce a una frase española fija y el frontend la pasa por el catálogo. Las frases de campaña viven en `backend/api/campaigns/http.py`; las de mapas, en `backend/api/maps.py`.

| Código | Frase |
| --- | --- |
| `rules_invalid` | Las reglas no son válidas. |
| `phase_invalid` | Esa acción no corresponde a esta fase. |
| `forbidden` | No puedes hacer eso en esta campaña. |
| `seat_full` | La campaña ya no tiene plazas. |
| `already_joined` | Ya estás en esta campaña. |
| `expelled` | No puedes volver a esta campaña. |
| `order_illegal` | Esa orden no es legal. |
| `text_invalid` | Ese texto no es válido. |
| `sheet_incomplete` | Falta el comandante o la lista obligatoria de un ejército. |
| `commander_taken` | Ese comandante ya está en otro ejército tuyo. |
| `battle_closed` | Esa batalla ya está cerrada. |
| `battle_unknown` | Esa batalla no existe. |
| `cannot_expel_owner` | El propietario activo no se puede expulsar. |
| `not_found` | No hay ninguna campaña con ese identificador. |
| `unknown_player` | No hay ningún jugador con ese alias. |
| `invitation_invalid` | La invitación no es válida. |
| `revision_conflict` | La campaña ha cambiado. Vuelve a leerla. |
| `campaign_limit` | Ya tienes tres campañas en curso. |
| `invitee_campaign_limit` | Ese jugador ya tiene tres campañas en curso. |
| `campaign_delete_locked` | Esa campaña no se puede eliminar así. |
| `confirm_name_mismatch` | Escribe el nombre exacto de la campaña para confirmar. |
| `map_unknown` | No hay ningún mapa con ese identificador. |
| `faction_invalid` | Elige una raza de The Old World. |
| `color_invalid` | Elige un color de la paleta. |
| `color_taken` | Ese color ya pertenece a otro jugador. |
| `identity_required` | Todos los jugadores deben elegir raza y color antes de empezar. |
| `lobby_not_ready` | Todos los jugadores deben estar listos antes de iniciar. |
| `search_limited` | Demasiadas búsquedas. Prueba de nuevo en unos minutos. |
| `map_limit` | Ya tienes el máximo de mapas guardados. |
| `map_readonly` | Ese mapa generado no se puede sobrescribir; crea una copia. |

`account_inactive` no tiene frase propia: la API responde 401 con «La sesión no es válida.» Una cuenta desactivada y una sesión ausente se ven igual.

Una excepción que nadie atrapó se registra con la traza completa y el `request_id` de la petición. El cliente recibe 500 y el cuerpo `{"detail": "Error interno."}`. Ese registro es el punto donde más adelante se puede enganchar Sentry u OpenTelemetry. El proceso lleva tres contadores en memoria, en `apps/campaigns/telemetry.py`: turno resuelto, conflicto 409 y ese 500. Cada uno deja una línea `event`, `count` y `request_id`. Los números no salen del proceso.

Nombre de ejército, comandante y raza: 40 caracteres. Lista: 2000. Una petición de cuentas no pasa de 4 KB (4096 bytes). Una de campaña o invitación no pasa de 64 KB (65536). Una de mapa no pasa de 96 KB (98304).

Las pruebas del dominio no usan base de datos. Las de la API usan Postgres y cubren la orden que el rival no puede leer, la versión que responde 409 y la cuenta desactivada que deja la plaza inactiva. Si Redis no puede publicar, el proceso lo deja en el log y entrega el aviso en local. El flujo de comprobación del backend es `ruff check .`, `mypy --strict` y `pytest --cov=hexcampaign --cov=api --cov=apps --cov-report=term-missing --cov-fail-under=86`. El modo estricto cubre el dominio y la API. El suelo de cobertura es 86.
