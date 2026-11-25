# Reglas de campaña, primera versión

Hex Campaign guarda una campaña propia. Estas reglas no copian un reglamento de miniaturas. La raza, el comandante y la lista son nombres que escribe el jugador. La batalla se juega en la mesa y la aplicación solo anota el resultado.

El estado de la partida vive en la campaña. La sesión del jugador no es la campaña: una cuenta puede jugar varias a la vez y la campaña sigue guardada cuando la sesión caduca.

Las reglas se pueden cambiar mientras el propietario no ha pulsado empezar. Desde ese momento quedan fijas. Los pueblos, los puestos avanzados y la economía de puntos esperan. El catálogo de terrenos está en «Mapa y terrenos» y todavía no cambia las partidas de esta versión: siguen sin hexágonos infranqueables.

## La mesa

Una campaña tiene de 2 a 4 jugadores. El número se elige al crearla. Hasta pulsar empezar, el propietario puede bajarlo para cuadrar con quien ya se ha unido, sin bajar de 2 ni de las plazas ocupadas. Nadie entra después de empezar. El mapa, que se definirá aparte, se genera a partir de ese número y del tamaño elegido.

El nombre puede repetirse. Cada campaña tiene un id propio. El buscador encuentra solo ese id. El propietario también puede invitar por alias: a quien invita le aparece un aviso en la aplicación. O genera un enlace de invitación. Una cuenta puede crear como máximo tres campañas que sigan abiertas. Una campaña terminada deja libre esa plaza.

El creador es el único administrador hasta empezar, y el propietario mientras siga activo. Al empezar puede nombrar más administradores, hasta cubrir a todos los jugadores. Un administrador que no es el propietario tiene los mismos poderes que los demás administradores, y ninguno de ellos puede expulsar ni degradar al propietario activo.

## Lo que se elige al crear

Queda fijo en ese momento:

- Jugadores: 2, 3 o 4.
- Ejércitos iniciales de cada jugador: 1 o 2.
- Movimiento de cada ejército: 1, 2 o 3 hexágonos. En esta versión es el mismo para todos.
- Tamaño del mapa: 19, 37 o 61 hexágonos. Cuando la campaña use un mapa de terrenos, esos tres tamaños se llaman pequeño, mediano y grande.
- Visibilidad de los ejércitos enemigos: todo el mapa, solo los adyacentes, o una ficha sin nombre ni composición. Con un mapa de terrenos, esta elección pasa a ser la de «Mapa y terrenos»: total, mapa conocido con niebla, o solo el territorio propio.
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

## Mapa y terrenos

Esto no cambia las partidas de esta versión. Es el mapa que viene después.

Cada casilla tiene un terreno. El territorio de un jugador no se pinta casilla a casilla: es el disco alrededor de su fortaleza, definido más abajo. Lo demás es neutral. De quién es una casilla no cambia lo que cuesta salir de ella. El territorio propio se ve entero, siempre, con terreno y ejércitos.

El movimiento elegido al crear, 1, 2 o 3, pasa a ser puntos. Los puntos se gastan al salir de una casilla, no al entrar. Salir cuesta lo que dice el terreno que se pisa. Entrar en la siguiente no añade otro coste. Quedarse quieto gasta cero y no borra lo ya abonado. La casilla que se pisa no se paga otra vez por estar en ella: desde una montaña se sale pagando el coste de la montaña, y la llanura de destino no cobra.

Una orden puede pedir una salida que este turno no alcanza a pagar. Los puntos que sí tiene se abonan a esa salida y el ejército se queda. El abono queda en el ejército hasta que sale de esa casilla. Al turno siguiente sigue faltando la diferencia. Si la orden es quedarse, el abono no crece y no se pierde. Cada ejército lleva el suyo. No se pasa a otro.

Un ejemplo. Un ejército está en una llanura, con 3 puntos, y su orden es llanura, bosque profundo, llanura. Salir de la llanura cuesta 1: entra en el bosque profundo y le quedan 2. Salir del bosque profundo cuesta 3. Abona esos 2 y le falta 1. Se queda ahí, con el abono guardado. El mismo viaje por un bosque normal cuesta 1 y luego 2: con 3 puntos sale del bosque y llega a la llanura siguiente, sin puntos de sobra.

Quien ya conoce una casilla infranqueable no puede cerrar una orden que entre en ella. Quien todavía no la ha descubierto puede cerrar. Al resolver, si el destino no se puede pisar, no se cobra la salida y el ejército se para. El abono no se gasta en una salida imposible.

Mientras le faltan puntos para salir, el ejército sigue ocupando su casilla. Quien termina antes de pagar sale antes. Llegar a una casilla compara los puntos gastados en esa salida, no los hexágonos cruzados. Si dos enemigos completan la salida hacia la misma casilla con el mismo coste, hay batalla ahí. Un ejército que todavía está pagando no ha entrado.

El camino y el puente no sustituyen al suelo. Van encima. Salir de una casilla con camino cuesta 1, aunque el suelo cueste más, y la mirada sigue siendo la del suelo. Al completar esa salida, el ejército suma 1 punto, que puede gastar en salidas posteriores de ese turno. El camino no abre una montaña rocosa, un acantilado ni un lago. El puente o el vado solo puede ir sobre una orilla o un río completo, y salir de ahí cuesta 1. Camino y puente pueden compartir casilla: salir cuesta 1 y, por el camino, suma el punto.

Hay dos velos, y no hacen lo mismo.

El conocimiento es el terreno que ya se ha visto y no se olvida: el suelo, el camino o el puente, de quién es la casilla y si hay una fortaleza. Una casilla sin descubrir no enseña nada de eso. La niebla es qué ejércitos enemigos se ven ahora mismo. Los propios se ven siempre. El territorio propio se conoce y se ve entero aunque ningún ejército esté mirando hacia él. Ningún terreno tapa lo que hay detrás: la mirada llega hasta su distancia, y no se corta en una montaña.

Al crear se elige una de tres, al modo de un mapa de estrategia:

- Total. Se conoce todo el mapa y se ve a todos los ejércitos. La colina, la montaña y el bosque profundo no cambian esa mirada.
- Mapa conocido con niebla. El terreno se conoce entero desde el principio. Un ejército enemigo solo se ve dentro de la mirada o dentro del territorio propio.
- Solo el territorio propio. Al empezar, cada jugador conoce y ve su disco, y el resto está por descubrir. Salta un aviso en la campaña de que empieza así.

En las dos con niebla, un ejército mira a 2 casillas. La distancia cuenta la propia como 0 y llega hasta N inclusive. La colina lo deja en 3, la montaña que se puede subir lo deja en 4, y el bosque profundo lo deja en 0: solo la casilla que pisa, además del territorio propio, que se sigue viendo entero. El resto de terrenos no cambia la mirada. La mirada del jugador es la suma de la de sus ejércitos. Cuando la niebla deja ver a un enemigo, se ve su nombre. Un choque contra un ejército que la niebla tapaba se resuelve igual.

Mientras las órdenes están abiertas, cada cual ve lo que conoce y lo que la niebla le deja en las posiciones de salida. Cerrar la orden no descubre nada. Cuando las órdenes se ejecutan a la vez, cada paso que entra en una casilla descubre lo que se miraría desde ahí y actualiza la niebla. Al cerrar el turno, la niebla queda en las posiciones finales, más el territorio propio. El terreno descubierto por el camino se queda. Un enemigo que solo estuvo a la vista a mitad del camino deja de verse si al final no cae en la mirada ni en el territorio propio.

Al generar un mapa, el propietario puede no mirarlo. Si no lo mira, no se lleva un conocimiento de más: al empezar sabe lo que diga la visibilidad elegida. Si lo mira, conoce todo el terreno desde ese momento. Quien dibujó un mapa propio ya lo conoce. Un mapa oculto lo coloca la aplicación. Si van a colocar los jugadores, el terreno se ve durante la colocación y, al empezar el primer turno, se aplica la visibilidad elegida.

El conocimiento de cada jugador, y el abono de salida de cada ejército, forman parte del turno. Revertir el último turno olvida lo descubierto en ese turno y devuelve los abonos a como estaban. Expulsar borra el conocimiento de ese jugador. Los demás conservan el suyo. Ni el propietario ve a través de la niebla por serlo. Quien lucha una batalla, y el administrador que la juzga, conocen esa casilla. Una fortaleza ya vista sigue en el recuerdo hasta que la mirada vuelve a pasar por ella.

Cualquier ejército paga el mismo coste. En este catálogo no hay combate, cobertura de disparo, emboscadas, desgaste, producción, barcos ni vuelo. Un terreno puede compartir efectos con otro y seguir siendo otro terreno, para poder separarlos más adelante sin rehacer el mapa.

Al crear la campaña, el tamaño se elige como pequeño, mediano o grande. Pequeño son 19 casillas, mediano 37 y grande 61. El contorno es ese disco. El propietario usa un mapa que ya haya guardado, o pide uno generado de ese tamaño. Al empezar, la campaña se queda una copia. Luego puede cambiar el original y la partida no se entera.

El terreno de un jugador es el disco alrededor de su fortaleza, recortado por el borde del mapa. En el pequeño y en el mediano llega a distancia 1: la fortaleza y sus vecinas, 7 casillas si todas caben. En el grande llega a distancia 2: hasta 19 casillas. El resto del mapa queda neutral. La idea es que la campaña no salga partida entera entre los jugadores: tiene que sobrar terreno de nadie.

La fortaleza, y cualquier ejército, solo se colocan donde se puede entrar. El disco de una fortaleza no puede compartir casilla con el de otra. Tiene que quedar al menos una casilla del mapa fuera de todos los discos. Si con esas plazas no cabe, esas fortalezas no valen y hay que moverlas o bajar plazas. En el mediano el disco no sube a distancia 2 porque, con 3 o 4 jugadores, un territorio de 19 casillas no dejaría frontera en un mapa de 37. En el grande, distancia 2 con 4 jugadores puede no caber: entonces esa colocación no vale.

Si colocan los jugadores, la fortaleza y los ejércitos van en casillas distintas, todas transitables, y la fortaleza tiene que cumplir el disco. Un ejército inicial puede quedar en la fortaleza. El segundo, si lo hay, en una vecina libre en la que se pueda entrar y, si cabe, dentro del propio disco.

En un mapa hecho a mano, si coloca la aplicación, reparte las fortalezas junto al borde, lo más lejos posible unas de otras, cumpliendo lo de arriba. El mapa en sí es libre: puede tener un río suelto, una cordillera partida o el transitable cortado en dos.

En un mapa generado, las fortalezas salen solas y el mapa nace simétrico. Cada jugador tiene el mismo disco: los mismos terrenos, los mismos caminos o puentes, las mismas casillas por las que se puede salir y el mismo coste para llegar al centro. El centro queda neutral y es la frontera común. Nadie empieza detrás de una montaña rocosa, un acantilado o un lago que el otro no tenga en el mismo sitio de su porción.

El disco se parte en tantas porciones como plazas, y las demás porciones son la primera girada. Con 2 jugadores, media vuelta. Con 3, un tercio de vuelta. Con 4, la rejilla hexagonal no parte el mapa en cuatro porciones exactas: se hacen dos pares opuestos, cada par idéntico al girar media vuelta, los cuatro a la misma distancia del centro y con el mismo contenido en el disco. La fortaleza cae en el mismo punto de cada porción. Si así no caben los discos o el centro no queda libre, se genera otra vez.

El generado, además, se recorre entero por donde se entra y se construye así:

- El río completo forma un curso. Cada casilla, salvo los extremos, tiene dos vecinas de río completo. Un extremo toca un lago o el borde del mapa. No hay un río de una sola casilla, ni una mancha, ni un cruce.
- La orilla toca al menos un río completo.
- El acantilado forma una cadena de al menos dos casillas, y cada una toca un lago o el borde del mapa.
- La playa toca un lago o el borde del mapa.
- Un lago de varias casillas es contiguo.
- La montaña y la montaña rocosa forman una cordillera: cada casilla toca otra de las dos, salvo un pico aislado.
- El bosque profundo toca al menos un bosque.
- El pantano toca un río completo, una orilla o un lago.
- El camino forma un tramo de al menos dos casillas y no se coloca sobre un terreno infranqueable. Puede enlazar con un puente.
- El puente o el vado está sobre una orilla o un río completo y une dos casillas en las que se puede entrar.

Esos rasgos son opcionales. Un mapa pequeño puede ser casi todo llanura. Lo que sí se coloca, se coloca seguido.

| Terreno | Al salir | Mirada del ejército que está encima |
| --- | --- | --- |
| Llanura | 1 | 2, la de partida |
| Colina | 2 | 3 |
| Bosque | 2 | 2, la de partida |
| Bosque profundo | 3 | 0, solo su casilla |
| Montaña | 3 | 4 |
| Montaña rocosa | No se entra | No se ocupa |
| Desierto | 1 | 2, la de partida |
| Tundra | 2 | 2, la de partida |
| Orilla | 2, o 1 con puente o vado | 2, la de partida |
| Río completo | 3, o 1 con puente o vado | 2, la de partida |
| Pantano | 3 | 2, la de partida |
| Lago | No se entra | No se ocupa |
| Playa | 1 | 2, la de partida |
| Acantilado | No se entra | No se ocupa |
| Mina o cantera | 1 | 2, la de partida |
| Campo de cultivo | 1 | 2, la de partida |

| Vía | Dónde puede ir | Qué cambia |
| --- | --- | --- |
| Camino | Encima de un terreno en el que se puede salir | Salir cuesta 1. Al completar esa salida, suma 1 punto para las salidas de después. |
| Puente o vado | Encima de una orilla o de un río completo | Salir cuesta 1. |

Desierto, mina y campo se salen y se ven como una llanura. Están en el catálogo porque el desgaste y la producción vendrán después, y el mapa no tendrá que cambiar de terreno. La playa es la costa por la que se puede entrar. El acantilado no se escala. No hay desembarco. Salir de la montaña cuesta 3 y, mientras se está encima, la mirada llega a 4. La montaña rocosa es la barrera.

## Fuera de esta versión

Queda para más adelante: comprar ejércitos con puntos, movimiento según unidades y raza, bajas que no sean destrucción total, y pueblos o puestos avanzados. El catálogo de terrenos ya está escrito arriba; aplicarlo a la partida es el paso siguiente. Cuando existan pueblos o puestos, una expulsión también los borra si pertenecen al jugador expulsado.
