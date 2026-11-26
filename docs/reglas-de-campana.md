# Reglas de campaña, primera versión

Hex Campaign guarda una campaña propia. Estas reglas no copian un reglamento de miniaturas. El jugador elige su raza o facción de un catálogo; el comandante y la lista se escriben libremente. La batalla se juega en la mesa y la aplicación solo anota el resultado.

### Estandartes y territorios

Cada jugador elige su facción y un color en «Tu estandarte», dentro de la campaña. El desplegable incluye las diez facciones principales de The Old World (también Gran Catai) y las siete Legacy: Enanos del Caos, Demonios del Caos, Elfos Oscuros, Hombres Lagarto, Reinos Ogros, Skaven y Condes Vampiro. El catálogo se contrasta con las [descargas oficiales de The Old World](https://www.warhammer-community.com/en-gb/downloads/warhammer-the-old-world/). Solo se usan nombres, no se incorporan reglas ni ilustraciones de esos libros.

Los colores de la paleta no se pueden repetir dentro de una campaña, aunque las facciones sí. Las campañas nuevas no empiezan hasta que todos hayan elegido ambos. Se pueden cambiar durante el reclutamiento y quedan fijos al empezar. Las campañas antiguas conservan sus datos y permiten completar el estandarte una vez aunque ya hayan comenzado. Esta identidad no cambia el movimiento, la visión, las listas ni los datos descriptivos de los ejércitos.

El mapa de campaña representa cada territorio con una veladura tenue y un contorno exterior continuo, por debajo de árboles, caminos y construcciones. El estandarte de la fortaleza y la leyenda identifican al jugador; «Territorios» permite ocultar la veladura. El territorio neutral no se tiñe. Solo se envía la propiedad de las casillas conocidas: las zonas sin explorar no revelan terreno, dueño ni fortalezas. Se usa la superficie territorial guardada en la campaña, no un radio calculado en el navegador. En los tableros antiguos sin terrenos se respeta la distribución por proximidad, dejando neutrales los empates. Ocupar una fortaleza no transfiere automáticamente su territorio: siguen aplicándose las reglas de ocupación y victoria.

El estado de la partida vive en la campaña. La sesión del jugador no es la campaña: una cuenta puede jugar varias a la vez y la campaña sigue guardada cuando la sesión caduca.

Las reglas se pueden cambiar mientras el propietario no ha pulsado empezar. Desde ese momento quedan fijas. Los pueblos, los puestos avanzados y la economía de puntos esperan. Con un mapa de terrenos, el catálogo de «Mapa y terrenos» sí rige la partida: hay casillas infranqueables, costes al salir, niebla y caminos. Sin mapa de terrenos, la mesa antigua de 19, 37 o 61 casillas sigue sin terrenos.

## La mesa

Una campaña tiene de 2 a 4 jugadores. El número se elige al crearla. Hasta pulsar empezar, el propietario puede bajarlo para cuadrar con quien ya se ha unido, sin bajar de 2 ni de las plazas ocupadas. Nadie entra después de empezar. El mapa, que se definirá aparte, se genera a partir de ese número y del tamaño elegido.

El nombre puede repetirse. Cada campaña tiene un id propio. El buscador encuentra solo ese id. Puede llevar una descripción libre de hasta 15 000 caracteres (trasfondo, acuerdos de mesa, tono de la guerra); es opcional y se ve en la ficha de la campaña. El propietario también puede invitar por alias: a quien invita le aparece un aviso en la aplicación. O genera un enlace de invitación. Una campaña está preparada (reclutamiento, colocación o preparación de caminos), en curso (órdenes o batallas) o finalizada. Una cuenta puede tener como máximo tres campañas en curso a la vez; las preparadas y las finalizadas no ocupan esa plaza.

El creador es el único administrador hasta empezar, y el propietario mientras siga activo. Al empezar puede nombrar más administradores, hasta cubrir a todos los jugadores. Un administrador que no es el propietario tiene los mismos poderes que los demás administradores, y ninguno de ellos puede expulsar ni degradar al propietario activo.

## Lo que se elige al crear

Queda fijo en ese momento:

- Jugadores: 2, 3 o 4.
- Ejércitos iniciales de cada jugador: 1 o 2.
- Movimiento base de cada ejército: de 1 a 5 puntos. El explorador suma 4 a ese valor. Al crear, se recomienda 3 en mapa pequeño, 4 en mediano y 5 en grande; el creador puede cambiarlo.
- Tamaño del mapa: pequeño, mediano o grande. En la creación de campaña se autogenera un paisaje o se elige uno generado; el tamaño lo fija ese mapa (hoy 271, 397 o 547 casillas). Los mapas guardados de otros tamaños siguen siendo compatibles.
- Visibilidad de los ejércitos enemigos: todo el mapa, solo los adyacentes, o una ficha sin nombre ni composición. Con un mapa de terrenos, esta elección pasa a ser la de «Mapa y terrenos»: total, mapa conocido con niebla, o solo el territorio propio.
- Victoria: destruir todos los ejércitos rivales, retener una fortaleza enemiga un número de turnos seguidos, o cualquiera de las dos.
- Turnos seguidos de retención: un entero de al menos 1.
- Quién coloca fortalezas y zonas de salida: los jugadores o el predeterminado.
- Días máximos para cerrar las órdenes de un turno: un entero de 1 a 30.
- Días máximos para anotar una batalla: un entero de 1 a 30.
- Qué considera inactivo, además de la regla de la aplicación que va más abajo.

Cada jugador tiene una fortaleza. Al empezar, sus ejércitos iniciales ya están en el mapa y puede moverlos todos. No se compran ejércitos nuevos.

## Preparación de caminos

Si la campaña lleva mapa de terrenos, cada jugador recorre la preparación por su cuenta y en orden: fortaleza, caminos y ejércitos. No espera al resto en cada paso. Si las fortalezas las colocan los jugadores, elige la casilla dentro del territorio que se le marcó al principio y la confirma; a partir de ahí su territorio se mide desde esa fortaleza. Luego traza sus caminos y, al guardarlos, coloca cada ficha dentro del anillo de la fortaleza: una casilla alrededor en el mapa pequeño, dos en el mediano y tres en el grande. Si tiene dos ejércitos, o dos exploradores, ve un número en sus fichas; el rival no lo ve. El comandante (y la lista, si la campaña la pide) se escribe con un doble clic. Cuando ha terminado esos pasos, espera. El primer turno se abre cuando todos los asientos activos han acabado la suya. Durante la partida, un doble clic en un ejército abre esa misma ficha, ya fija. Sin mapa de terrenos, el primer turno de órdenes se abre al instante.

En preparación, todos los asientos activos colocan a la vez. Cada uno dispone de un presupuesto de piezas igual al doble de la distancia máxima, en hexágonos, desde su fortaleza hasta el borde de su territorio. Solo puede poner camino en casillas transitables de su territorio, nunca en la fortaleza. Cada pieza nueva tiene que tocar la fortaleza o una pieza ya puesta, de modo que la red quede conectada. Poner camino sobre un río completo añade puente. Puede quitar una pieza propia mientras el resto siga unido a la fortaleza. Quien ha terminado sus caminos sigue con sus ejércitos, sin esperar a los demás. El turno 1 se abre cuando todos los asientos activos han acabado la preparación entera. Los mapas generados salen sin caminos locales: las piezas las pone cada jugador en esta fase. Un mapa dibujado a mano puede traer caminos o puentes ya puestos.

## Ejército y explorador

Al empezar, cada jugador recibe uno o dos ejércitos, según lo elegido al crear la campaña, y un explorador. El aspecto de cada ficha sigue la raza del estandarte y toma el color elegido.

Un ejército es la ficha de combate: puede pelear, ocupar fortalezas y cuenta para la victoria por destrucción. Dos ejércitos del mismo jugador no comparten hexágono. Cada uno gasta su propio movimiento; no se transfiere de uno a otro.

Cada ejército lleva el nombre de su comandante. Ese nombre es obligatorio, distingue unas fichas de otras y no se puede repetir entre los ejércitos del mismo jugador. La lista se escribe en texto, hasta 2000 caracteres. Por defecto es opcional. Al crear la campaña se puede marcar que la lista sea obligatoria. Comandante y lista solo se editan en la preparación (o en la colocación, si esa es la última fase antes de la guerra) y quedan fijos al abrirse el primer turno. El explorador no lleva comandante ni lista.

El explorador es un jinete que no lucha. Se mueve 4 puntos más que el ejército y mira 5 casillas más lejos. Las reglas de coste del terreno le afectan igual. Puede compartir casilla con cualquier ejército o explorador, propio o ajeno, y no provoca batalla. No puede entrar en ninguna fortaleza.

Un jugador sin ejércitos de combate queda eliminado, aunque le quede el explorador. Sus órdenes pendientes se cancelan. La campaña sigue entre los demás.

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

Cada acción queda anotada: quién entra, las reglas si cambian, la colocación, quién marca la preparación de caminos y cuándo se cierra, las órdenes cerradas, el camino que recorrió cada ejército, las batallas y su resultado, las expulsiones, los abandonos, los ascensos y el final. Mientras la campaña sigue, esa crónica no se enseña. Cuando termina, quien estuvo en la mesa puede leerla entera, también lo que luego se deshizo.

Un administrador puede abandonar. Sus ejércitos mueren y sale de la campaña. Si quien se va es el propietario, o es el último administrador, un jugador aleatorio de los que siguen pasa a ser el propietario. Si el propietario queda inactivo, ocurre lo mismo y el nuevo propietario recibe el aviso para expulsarlo. El propietario activo no puede ser expulsado ni degradado por otro.

## Mapa y terrenos

Con un mapa de terrenos, estas reglas rigen la partida. Sin él, la mesa antigua no usa este catálogo.

Cada casilla tiene un terreno. El territorio de un jugador es una zona compacta alrededor de su fortaleza, definida más abajo. Lo demás es neutral. De quién es una casilla no cambia lo que cuesta salir de ella. El territorio propio se ve entero, siempre, con terreno y ejércitos.

El movimiento elegido al crear, de 1 a 5, pasa a ser puntos. Los puntos se gastan al salir de una casilla, no al entrar. Salir cuesta lo que dice el terreno que se pisa. Entrar en la siguiente no añade otro coste. Quedarse quieto gasta cero y no borra lo ya abonado. La casilla que se pisa no se paga otra vez por estar en ella: desde una montaña se sale pagando el coste de la montaña, y la llanura de destino no cobra.

Una orden puede pedir una salida que este turno no alcanza a pagar. Los puntos que sí tiene se abonan a esa salida y el ejército se queda. El abono queda en el ejército hasta que sale de esa casilla. Al turno siguiente sigue faltando la diferencia. Si la orden es quedarse, el abono no crece y no se pierde. Cada ejército lleva el suyo. No se pasa a otro.

Un ejemplo. Un ejército está en una llanura, con 3 puntos, y su orden es llanura, bosque profundo, llanura. Salir de la llanura cuesta 1: entra en el bosque profundo y le quedan 2. Salir del bosque profundo cuesta 3. Abona esos 2 y le falta 1. Se queda ahí, con el abono guardado. El mismo viaje por un bosque normal cuesta 1 y luego 2: con 3 puntos sale del bosque y llega a la llanura siguiente, sin puntos de sobra.

Quien ya conoce una casilla infranqueable no puede cerrar una orden que entre en ella. Quien todavía no la ha descubierto puede cerrar. Al resolver, si el destino no se puede pisar, no se cobra la salida y el ejército se para. El abono no se gasta en una salida imposible.

Mientras le faltan puntos para salir, el ejército sigue ocupando su casilla. Quien termina antes de pagar sale antes. Llegar a una casilla compara los puntos gastados en esa salida, no los hexágonos cruzados. Si dos enemigos completan la salida hacia la misma casilla con el mismo coste, hay batalla ahí. Un ejército que todavía está pagando no ha entrado.

El camino y el puente no sustituyen al suelo. Van encima. Salir de una casilla con camino cuesta 1, aunque el suelo cueste más, y la visión sigue siendo la del suelo. Completar un movimiento por camino da +1 movimiento ese turno. El camino no abre una montaña rocosa, un acantilado ni un lago. El puente o el vado solo puede ir sobre un río completo, y salir de ahí cuesta 1. Camino y puente pueden compartir casilla: salir cuesta 1 y, por el camino, se obtiene el +1 de movimiento.

Hay dos velos, y no hacen lo mismo.

El conocimiento es el terreno que ya se ha visto y no se olvida: el suelo, el camino o el puente, de quién es la casilla y si hay una fortaleza. Una casilla sin descubrir no enseña nada de eso. La niebla es qué ejércitos enemigos se ven ahora mismo. Los propios se ven siempre. El territorio propio se conoce y se ve entero aunque ningún ejército esté mirando hacia él. Ningún terreno tapa lo que hay detrás: la mirada llega hasta su distancia, y no se corta en una montaña.

Al crear se elige una de tres, al modo de un mapa de estrategia:

- Total. Se conoce todo el mapa y se ve a todos los ejércitos. La colina, la montaña y el bosque profundo no cambian esa mirada.
- Mapa conocido con niebla. El terreno se conoce entero desde el principio. Un ejército enemigo solo se ve dentro de la mirada o dentro del territorio propio.
- Solo el territorio propio. Al empezar, cada jugador conoce y ve su disco, y el resto está por descubrir. Salta un aviso en la campaña de que empieza así.

En las dos con niebla, un ejército mira a 2 casillas. La distancia cuenta la propia como 0 y llega hasta N inclusive. La colina lo deja en 3, la montaña que se puede subir lo deja en 4, y el bosque profundo lo deja en 0: solo la casilla que pisa, además del territorio propio, que se sigue viendo entero. El explorador suma 5 a esa mirada. El resto de terrenos no cambia la mirada. La mirada del jugador es la suma de la de sus fichas. Cuando la niebla deja ver a un enemigo, se ve su nombre. Un choque contra un ejército que la niebla tapaba se resuelve igual.

Mientras las órdenes están abiertas, cada cual ve lo que conoce y lo que la niebla le deja en las posiciones de salida. Cerrar la orden no descubre nada. Cuando las órdenes se ejecutan a la vez, cada paso que entra en una casilla descubre lo que se miraría desde ahí y actualiza la niebla. Al cerrar el turno, la niebla queda en las posiciones finales, más el territorio propio. El terreno descubierto por el camino se queda. Un enemigo que solo estuvo a la vista a mitad del camino deja de verse si al final no cae en la mirada ni en el territorio propio.

Al generar un mapa, el propietario puede no mirarlo. Si no lo mira, no se lleva un conocimiento de más: al empezar sabe lo que diga la visibilidad elegida. Si lo mira, conoce todo el terreno desde ese momento. Quien dibujó un mapa propio ya lo conoce. Un mapa oculto lo coloca la aplicación. Si van a colocar los jugadores, el terreno se ve durante la colocación y, al empezar el primer turno, se aplica la visibilidad elegida.

El conocimiento de cada jugador, y el abono de salida de cada ejército, forman parte del turno. Revertir el último turno olvida lo descubierto en ese turno y devuelve los abonos a como estaban. Expulsar borra el conocimiento de ese jugador. Los demás conservan el suyo. Ni el propietario ve a través de la niebla por serlo. Quien lucha una batalla, y el administrador que la juzga, conocen esa casilla. Una fortaleza ya vista sigue en el recuerdo hasta que la mirada vuelve a pasar por ella.

Cualquier ejército paga el mismo coste. En este catálogo no hay combate, cobertura de disparo, emboscadas, desgaste, producción, barcos ni vuelo. Un terreno puede compartir efectos con otro y seguir siendo otro terreno, para poder separarlos más adelante sin rehacer el mapa.

Al crear la campaña, el asistente ofrece pequeño, mediano o grande y autogenera un paisaje o elige uno generado; no hay vista previa en esa pantalla. El tamaño es el del mapa (hoy 271, 397 y 547 casillas). La pequeña admite 2 y 3 jugadores; las otras admiten 2, 3 y 4. Estos tamaños son una configuración, no tres algoritmos: `TABLE_RADII` en [hexes.py](../backend/src/hexcampaign/domain/hexes.py) define los radios ofrecidos. El tamaño se calcula como `1 + 3*r*(r+1)`. `/api/map-scales` publica tamaños, plazas viables, recomendación y superficie territorial; la interfaz no mantiene otra lista. Al cambiar esos radios, el mismo motor calcula las nuevas geometrías y composiciones. Los radios válidos son enteros de 2 a 64, dentro del límite de coordenadas guardadas, aunque los más pequeños no admiten campañas generadas con la separación exigida. Al empezar, la campaña se queda una copia del mapa. Los tableros antiguos sin terrenos (19, 37, 61) siguen siendo compatibles si ya existen.

En un mapa nuevo generado, cada territorio ocupa aproximadamente el 7 % del tablero, redondeado a una casilla, con un mínimo de siete. Los tamaños actuales producen 19, 28 y 38 casillas por jugador. Se toman las casillas más próximas a la fortaleza y, en el anillo incompleto, se priorizan las que miran al interior del tablero. Así crecen de forma gradual, sin tener que añadir un anillo entero ni agrandar artificialmente el mapa. Todos reciben la misma superficie, sus territorios no se solapan y el centro queda neutral. El mapa guarda `home_size` y la campaña copia ese valor. Los documentos anteriores sin ese campo conservan sus discos originales: por ejemplo, 19 casillas en mapas de 397, 37 en los de 547 y 61 en los de 817.

La fortaleza, y cualquier ejército, solo se colocan donde se puede entrar. El territorio de una fortaleza no puede compartir casilla con el de otra. Tiene que quedar terreno neutral. Si con esas plazas no cabe, esas fortalezas no valen y hay que moverlas o bajar plazas.

Si colocan los jugadores, al empezar cada asiento recibe un territorio de casa ya marcado (el mismo disco que usaría una fortaleza sembrada). Solo puede poner la fortaleza y las fichas iniciales en casillas transitables de ese territorio; la fortaleza tiene que seguir cumpliendo los límites territoriales entre vecinos. El ejército puede quedar en la fortaleza. El explorador no puede entrar en ella, pero sí puede compartir casilla con el ejército.

En un mapa hecho a mano, si coloca la aplicación, reparte las fortalezas junto al borde, lo más lejos posible unas de otras, cumpliendo lo de arriba. El mapa en sí es libre: puede tener un río suelto, una cordillera partida o el transitable cortado en dos.

En un mapa generado, las fortalezas salen solas, lejos unas de otras, y cada semilla dibuja un país distinto. No es una copia girada del mismo reino: es un solo paisaje. El lago, el río y la sierra caen donde caigan, y el otro jugador no nace con el mismo dibujo, pero sí con una fortaleza transitable, un territorio que no pisa el del vecino y un viaje de al menos cinco turnos hasta cualquier fortaleza rival. No basta con contar trece casillas: el generador calcula el viaje más rápido con 3 puntos por turno, el coste al salir y el +1 de movimiento de los caminos. El viaje puede rodear el lago: esa es la frontera, no una recta de llanura vacía. El centro del tablero queda fuera de los territorios. Nadie nace sobre el agua ni encerrado por una barrera que no se pueda rodear.

El generado conecta las fortalezas por terreno transitable. Cada masa de terreno es contigua, pero puede haber muchas separadas por claros y valles; no tiene por qué usar todos los terrenos:

- El río completo forma un curso. Cada casilla, salvo los extremos, tiene dos vecinas de río completo. Un extremo toca un lago o el borde del mapa. No hay un río de una sola casilla, ni una mancha, ni un cruce.
- El acantilado, si sale, forma una cadena de al menos dos casillas, y cada una toca un lago o el borde del mapa.
- La playa toca un lago o el borde del mapa.
- Un lago de varias casillas es contiguo.
- La montaña y la montaña rocosa forman sierras cortas, separadas por pasos transitables.
- Hay varias masas de bosque. El bosque profundo, si sale, toca al menos un bosque.
- El pantano, si sale, toca un río completo o un lago.
- El puente o el vado está sobre un río completo y une dos casillas en las que se puede entrar.

Los mapas generados no pintan caminos ni puentes: salen limpios para la preparación. Conservan terreno transitable, frontera y miradores. La fortaleza conserva su salida normal. El puente, cuando lo pone un jugador o un mapa a mano, iguala el río a la llanura y, sin camino encima, no da el +1 de movimiento. Un camino sobre río lleva puente. Salir por camino cuesta 1 y completar ese movimiento da +1 movimiento ese turno. No cambian la visión del terreno ni abren casillas infranqueables.

En el editor de mapas el jugador parte de un disco de llanura del tamaño elegido, puede quitar o recuperar hexágonos dentro de ese disco, pintar terreno, caminos y puentes a pincel, y colocar de 0 o de 2 a 4 fortalezas. Un mapa generado se abre como copia editable; el original no se sobrescribe. Al guardar solo se exige que haya casillas y que las fortalezas, si las hay, sean transitables.

Cada jugador dispone de al menos tres casillas de acceso a su frontera y una posición elevada de observación accesible allí. Con movimiento 3 se exige llegar como máximo en dos turnos para los tamaños actuales; el límite crece con el alcance territorial si se configuran mesas mayores. Se aprovecha una colina o montaña existente cuando es posible; no se convierte toda la frontera en colinas. El bosque no oculta por sí mismo a un ejército ni corta la visión; la mirada depende del terreno del observador.

Para aceptar el mapa, el viaje más rápido de cada jugador a su rival más cercano no puede diferir en más de un turno respecto a los demás, medido con movimiento 3. Se mantienen los cinco turnos mínimos, pero ahora también se limita el máximo: cualquier viaje entre fortalezas debe caber en `ceil(distancia_hexagonal / 3) + 2` turnos. También debe existir una casilla neutral cercana al centro con una diferencia de llegada máxima de dos turnos. No son objetivos nuevos de victoria: son comprobaciones de generación que evitan tanto ataques prematuros como rodeos interminables.

Los caminos, una vez puestos, son parte del mapa: también los puede aprovechar un rival. Las garantías de paisaje se aplican a mapas nuevos generados por esta versión. No se redistribuye terreno en mapas guardados o campañas existentes. El propietario puede borrar un mapa guardado suyo que aún no use otra mesa.

El dibujo se compone por capas: suelo, agua continua, vegetación y relieve, construcciones y cuadrícula. Los árboles y las cumbres pueden sobresalir visualmente de su casilla, pero no cambian el terreno de la vecina. La casilla conserva su tipo, coste y mirada; pasar el puntero por ella muestra su terreno. Los puentes dibujados corresponden a puentes del mapa, no son adornos que concedan pasos nuevos. El trazado evita pequeños triángulos entre caminos vecinos, conservando cruces y circuitos amplios; el movimiento sigue dependiendo de las casillas, no de las líneas dibujadas. Los mapas de más de 547 casillas conservan todos sus detalles, pero prescinden del filtro global de ruido sobre la vegetación para reducir el coste del zoom.

Los mapas nuevos crecen con contornos irregulares alrededor de sus núcleos, bosques secundarios separados y cordilleras que pueden recorrer el interior. Una misma semilla reproduce el resultado con esta versión del generador. Los mapas guardados conservan sus casillas: la mejora del dibujo no regenera su geografía ni altera campañas existentes.

El motor aumenta el número de masas, no su tamaño sin límite: busca aproximadamente un 27 % de bosque en grupos de 7–14 casillas, sierras de 6–12, colinas de 3–6 y campos de 2–4. Añade lagunas secundarias y reserva claros entre masas. Los campos conservan su coste de llanura, sin introducir producción ni objetivos nuevos. Se exige al menos un 23 % de bosque y un 7 % de campos; en cada uno de los seis sectores del tablero, al menos un tercio debe contener terreno distinto de llanura, desierto, playa o tundra. No basta con cumplir una densidad global mientras media mesa queda vacía.

Ninguna masa conexa de bosque o de relieve transitable puede superar 18 casillas ni exigir más de cuatro turnos entre dos de sus casillas con movimiento 3, incluso recorriéndola por dentro. El territorio neutral no recibe caminos: son los claros y la fragmentación del paisaje los que evitan atravesar bosques de cien casillas. Estas condiciones se comprueban también para tamaños que no aparecen en los tres preajustes. El dibujo suaviza las transiciones y representa ríos de anchura variable que llegan al borde o se funden con el lago. La anchura dibujada no cambia las reglas de cruce.

La vegetación, las piedras y las cumbres se dibujan más pequeñas y mezcladas dentro del terreno que representan. Son detalles visuales, no casillas adicionales ni efectos nuevos. Los caminos se unen entre casillas y sus cruces se ven completos; al pasar el puntero se indica el terreno, el camino y el puente o vado, si los hay.

En el visor se puede ampliar hasta el 300 %, desplazarse por el mapa y volver al 100 %. La cuadrícula puede ocultarse para contemplar el paisaje; las fortalezas y la identificación del terreno al pasar el puntero siguen disponibles. Estos controles solo cambian la vista.

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
| Río completo | 3, o 1 con puente o vado | 2, la de partida |
| Pantano | 3 | 2, la de partida |
| Lago | No se entra | No se ocupa |
| Playa | 1 | 2, la de partida |
| Acantilado | No se entra | No se ocupa |
| Mina o cantera | 1 | 2, la de partida |
| Campo de cultivo | 1 | 2, la de partida |

| Vía | Dónde puede ir | Qué cambia |
| --- | --- | --- |
| Camino | Encima de un terreno en el que se puede salir | Salir cuesta 1. Completar un movimiento por camino: +1 movimiento. |
| Puente o vado | Encima de un río completo | Salir cuesta 1. |

Desierto, mina y campo se salen y se ven como una llanura. Están en el catálogo porque el desgaste y la producción vendrán después, y el mapa no tendrá que cambiar de terreno. La playa es la costa por la que se puede entrar. El acantilado no se escala. No hay desembarco. Salir de la montaña cuesta 3 y, mientras se está encima, la visión llega a 4. La montaña rocosa es la barrera.

## Fuera de esta versión

Queda para más adelante: comprar ejércitos con puntos, movimiento según unidades y raza, bajas que no sean destrucción total, y pueblos o puestos avanzados. El catálogo de terrenos ya rige las campañas con mapa; quedan por cerrar en pantalla el lobby completo, las órdenes y las batallas. Cuando existan pueblos o puestos, una expulsión también los borra si pertenecen al jugador expulsado.
