# Generación de variables aleatorias.
#
# Convierte los números U(0,1) del generador propio en los datos del modelo.
# Todas las funciones reciben un generador `g` con método random().
# Se usa el método de la transformada inversa en todos los casos.

# Cada función sortea un valor al azar con una forma determinada 
# (un sí/no, una cantidad de valijas, un tiempo de atención...). 

# Todas parten de lo mismo: un número al azar entre 0 y 1
# que nos da nuestro propio generador (g.random()), y lo "transforman" en el
# tipo de dato que necesita la simulación.

import math


def bernoulli(g, p):
    # Devuelve 1 con probabilidad p (ej.: ¿el pasajero se presenta?)."""
    # si es menor que p la respuesta es "sí" (1), si no es "no" (0).
    return 1 if g.random() < p else 0


def discreta_empirica(g, valores, probabilidades):
    # Transformada inversa discreta: se recorre la probabilidad acumulada
    # hasta que supera U.

    # cada valor ocupa una porción proporcional a
    # su probabilidad, y el número sorteado indica dónde cae.

    # Número sorteado
    u = g.random()

    # Suma de probabilidades que vamos acumulando, arranca en cero
    acumulada = 0.0

    # Recorremos cada valor posible junto con su probabilidad
    for v, p in zip(valores, probabilidades):
        # Sumamos la probabilidad de este valor
        acumulada += p
        # Si la suma ya alcanzó al número sorteado, este es el valor elegido
        if u <= acumulada:
            return v
        
    # Si no se eligió ninguno devolvemos el último valor de la lista
    return valores[-1]


def triangular(g, a, c, b):
    # Transformada inversa de la triangular (mínimo a, moda c, máximo b).
    # Se despeja x de la función acumulada F(x) = U en cada tramo.

    # Se usa cuando de un valor se conocen tres cosas: 
    # lo mínimo (a), lo más común (c) y lo máximo (b). 

    # Por ejemplo, el tiempo de atención en el mostrador o con cuánta anticipación llega un pasajero.

    # Número entre 0 y 1
    u = g.random()
    # Proporción de casos que quedan por debajo del valor más común.
    # Marca el punto donde el "triángulo" deja de subir y empieza a bajar.
    fc = (c - a) / (b - a)               # F(c): probabilidad acumulada en la moda

    # Si el número sorteado cae en la parte izquierda del triángulo
    # (entre el mínimo y el valor más común), usamos esta fórmula:
    if u < fc:
        return a + math.sqrt(u * (b - a) * (c - a))
    
    # si no, cae en la parte derecha (entre el valor más común y el máximo)
    return b - math.sqrt((1 - u) * (b - a) * (b - c))


def exponencial(g, media):
    # Transformada inversa: F(x) = 1 - e^(-x/media)  →  x = -media · ln(1 - U).
    # Se usa solo en la validación contra la cola M/M/1.

    # Da tiempos que en general son cortos pero que de vez en cuando salen
    # largos; en promedio valen "media". Es la forma típica del tiempo entre
    # llegadas de clientes totalmente al azar.
    return -media * math.log(1.0 - g.random())
