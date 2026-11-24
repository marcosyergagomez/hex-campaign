# Reglas de campaña, primera versión

Hex Campaign guarda una campaña propia. Estas reglas no copian un reglamento de miniaturas. La raza, el comandante y la lista son nombres que escribe el jugador. La batalla se juega en la mesa y la aplicación solo anota el resultado.

El estado de la partida vive en la campaña. La sesión del jugador no es la campaña: una cuenta puede jugar varias a la vez y la campaña sigue guardada cuando la sesión caduca.

Las reglas se pueden cambiar mientras el propietario no ha pulsado empezar. Desde ese momento quedan fijas. El terreno que modifica el movimiento, los pueblos, los puestos avanzados y la economía de puntos esperan a su propio reglamento. Esta versión no tiene hexágonos infranqueables.

## La mesa

Una campaña tiene de 2 a 4 jugadores. El número se elige al crearla. Hasta pulsar empezar, el propietario puede bajarlo para cuadrar con quien ya se ha unido, sin bajar de 2 ni de las plazas ocupadas. Nadie entra después de empezar. El mapa, que se definirá aparte, se genera a partir de ese número y del tamaño elegido.

El nombre puede repetirse. Cada campaña tiene un id propio. El buscador encuentra solo ese id. El propietario también puede invitar por alias: a quien invita le aparece un aviso en la aplicación. O genera un enlace de invitación. Una cuenta puede crear como máximo tres campañas que sigan abiertas. Una campaña terminada deja libre esa plaza.

El creador es el único administrador hasta empezar, y el propietario mientras siga activo. Al empezar puede nombrar más administradores, hasta cubrir a todos los jugadores. Un administrador que no es el propietario tiene los mismos poderes que los demás administradores, y ninguno de ellos puede expulsar ni degradar al propietario activo.

## Lo que se elige al crear

Queda fijo en ese momento:

- Jugadores: 2, 3 o 4.
- Ejércitos iniciales de cada jugador: 1 o 2.
- Movimiento de cada ejército: 1, 2 o 3 hexágonos. En esta versión es el mismo para todos.
- Tamaño del mapa: 19, 37 o 61 hexágonos.
- Visibilidad de los ejércitos enemigos: todo el mapa, solo los adyacentes, o una ficha sin nombre ni composición.
- Victoria: destruir todos los ejércitos rivales, retener una fortaleza enemiga un número de turnos seguidos, o cualquiera de las dos.
- Turnos seguidos de retención: un entero de al menos 1.
- Quién coloca fortalezas y zonas de salida: los jugadores o la aplicación.
- Días máximos para cerrar las órdenes de un turno: un entero de 1 a 30.
- Días máximos para anotar una batalla: un entero de 1 a 30.
- Qué considera inactivo, además de la regla de la aplicación que va más abajo.

Cada jugador tiene una fortaleza. Al empezar, sus ejércitos iniciales ya están en el mapa y puede moverlos todos. No se compran ejércitos nuevos.

## Ejército

Un ejército es una ficha con nombre, comandante, raza y lista. La lista no cambia el movimiento ni las bajas de esta versión.

Dos ejércitos del mismo jugador no comparten hexágono. Cada uno gasta su propio movimiento: puede avanzar menos hexágonos o quedarse quieto, y no se transfiere movimiento de uno a otro.

Un jugador sin ejércitos queda eliminado. Sus órdenes pendientes se cancelan. La campaña sigue entre los demás.

## Territorio y visibilidad

Al empezar, cada jugador solo conoce su territorio. Mover un ejército descubre territorio. La opción «todo el mapa» enseña todos los hexágonos desde el principio. Las otras dos solo informan de ejércitos enemigos dentro del territorio que ya se ve: los adyacentes, o una ficha anónima, sin nombre, comandante, raza ni lista.

Las órdenes siguen siendo secretas hasta que todos los jugadores que deben cerrar han cerrado, aunque el mapa sea visible. Un choque contra un ejército que no se veía se resuelve igual.

## Movimiento

Un ejército puede cruzar un hexágono de territorio enemigo que no tenga un ejército encima. No puede cruzar una fortaleza ocupada por un ejército.

Entrar en un hexágono donde hay un ejército de otro jugador detiene el movimiento y abre una batalla.

Al cerrar la orden, el servidor rechaza lo que ya es ilegal con la información de ese jugador, y también que dos ejércitos suyos acaben en el mismo hexágono. Así puede corregirla antes de cerrar.

Cuando todos han cerrado, las órdenes se ejecutan a la vez. El servidor las simula antes de aplicar el turno:

- El que gasta menos hexágonos llega antes. El otro no le adelanta.
- Si dos enemigos llegan al mismo hexágono con el mismo coste, hay batalla en ese hexágono.
- Si un ejército entra en el hexágono de otro y ese otro entra en el suyo, los enemigos luchan. Dos ejércitos del mismo jugador se cruzan y no pasa nada más.
- Dos enemigos que acaban en el mismo hexágono luchan. Dos del mismo jugador no llegan a cerrar esa orden.

No decide el reloj de quién pulsó antes. Las órdenes son simultáneas.

## Batallas

Puede haber varias en un turno. Se juegan fuera de la aplicación. Los jugadores que han luchado anotan vencedor o empate. Si no coinciden, un administrador escribe el resultado. Hay un registro de todas las batallas.

El plazo para anotar es el de la campaña, como máximo 30 días. Si se cumple sin resultado, un administrador tiene que ponerlo.

Los resultados del turno se conocen y se aplican a la vez. El vencedor destruye al ejército enemigo de esa batalla. El empate no destruye a ninguno. No hay bajas parciales.

## Victoria

Se comprueba después de aplicar las batallas del turno, y también después de una expulsión.

Retener es ocupar una fortaleza de otro jugador con un ejército propio. Al terminar un turno así, el contador de ese jugador en esa fortaleza sube uno. Cualquier ejército suyo mantiene el contador mientras no deje el hexágono. Si lo abandona, el contador vuelve a cero. Si hay batalla y el ocupante pierde, vuelve a cero. Si gana, el contador sigue donde estaba.

Destruir ejércitos exige eliminar todos los ejércitos de todos los rivales.

Si en el mismo turno se cumplen las dos condiciones, gana quien retiene la fortaleza. Si varios jugadores completan la retención en el mismo turno, ganan todos ellos. No hay un máximo de turnos ni tablas por duración.

Si solo queda un jugador, gana. Una expulsión que borra los últimos ejércitos rivales también puede dar la victoria.

## Inactivos y plazos

Hay dos vías.

La aplicación marca inactivo en todas sus campañas a quien sea borrado o desactivado. Se avisa a un administrador de cada campaña. Los ejércitos se quedan quietos hasta que un administrador lo expulsa.

Además, al crear la campaña se elige qué otro silencio cuenta como inactividad. Si alguien no cierra la orden, un administrador puede cerrar el turno sin él. Pasado el plazo de días del turno, también. Un administrador puede expulsar a quien acumula turnos sin orden.

## Administradores

Pueden expulsar a un jugador que no sea el propietario activo, revertir solo el último turno, anotar un resultado si los luchadores no coinciden o si el plazo de la batalla se ha cumplido, cerrar un turno con órdenes pendientes y nombrar a otro jugador administrador.

Expulsar borra al momento sus ejércitos, su fortaleza y todo lo que en el futuro le pertenezca en el mapa. Cancela su orden secreta si el turno aún no se ha resuelto. No puede volver a esa campaña. La plaza no se reocupa. El contador de una fortaleza borrada desaparece con ella.

Revertir el último turno se puede repetir sobre el turno que vuelve a quedar último. Las órdenes de ese turno vuelven a ser secretas y sus resultados de batalla dejan de aplicarse. Todos los jugadores ven que el turno fue revertido.

Cada acción queda anotada: quién entra, las reglas si cambian, la colocación, las órdenes cerradas, el camino que recorrió cada ejército, las batallas y su resultado, las expulsiones, los abandonos, los ascensos y el final. Mientras la campaña sigue, esa crónica no se enseña. Cuando termina, quien estuvo en la mesa puede leerla entera, también lo que luego se deshizo.

Un administrador puede abandonar. Sus ejércitos mueren y sale de la campaña. Si quien se va es el propietario, o es el último administrador, un jugador aleatorio de los que siguen pasa a ser el propietario. Si el propietario queda inactivo, ocurre lo mismo y el nuevo propietario recibe el aviso para expulsarlo. El propietario activo no puede ser expulsado ni degradado por otro.

## Fuera de esta versión

Queda para más adelante: comprar ejércitos con puntos, movimiento según unidades y raza, bajas que no sean destrucción total, terreno que cambie el coste del hexágono, y pueblos o puestos avanzados. Cuando existan, una expulsión también los borra si pertenecen al jugador expulsado.
