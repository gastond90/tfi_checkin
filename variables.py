"""
variables.py — Generación de variables aleatorias (Unidad 3).

Todas las funciones reciben un generador `g` con método random() → U(0,1)
(el LCG propio de generador.py), de modo que el modelo no depende del
generador interno de Python/NumPy.
"""
# Este archivo es una "caja de herramientas": cada función sirve para sortear
# un número al azar que siga una forma determinada (por ejemplo, tiempos que
# suelen ser cortos pero a veces largos, o cantidades enteras como valijas).
# Todas parten de lo mismo: un número al azar entre 0 y 1 que nos da nuestro
# propio generador (g.random()), y lo "transforman" en el tipo de valor que
# necesitamos.

# Biblioteca estándar de matemática (logaritmos, raíces, pi, coseno, etc.)
import math


def exponencial(g, media):
    """Transformada inversa: F(x) = 1 - e^{-x/media}  ⇒  x = -media·ln(1-U)."""
    # Sorteamos un número entre 0 y 1 y lo convertimos en un tiempo.
    # El resultado son valores que en general son chicos pero que de vez en
    # cuando salen grandes; en promedio dan "media".
    # Se usa, por ejemplo, para el tiempo entre llegadas de clientes.
    return -media * math.log(1.0 - g.random())


def triangular(g, a, c, b):
    """Transformada inversa de la triangular (mín a, moda c, máx b).
    F(c) = (c-a)/(b-a); se invierte cada tramo de la acumulada."""
    # Esta distribución se usa cuando sabemos tres cosas de un tiempo:
    # lo mínimo que puede tardar (a), lo más común (c) y lo máximo (b).
    # Ideal para tiempos de atención en el mostrador.

    # Sorteamos un número entre 0 y 1
    u = g.random()
    # Calculamos qué proporción de los casos cae por debajo del valor más común.
    # Eso marca el punto donde el "triángulo" cambia de subir a bajar.
    fc = (c - a) / (b - a)
    # Si el número sorteado cae en la parte izquierda del triángulo
    # (entre el mínimo y el valor más común), usamos esta fórmula...
    if u < fc:
        return a + math.sqrt(u * (b - a) * (c - a))
    # ...si no, cae en la parte derecha (entre el valor más común y el máximo).
    return b - math.sqrt((1 - u) * (b - a) * (b - c))


def discreta_empirica(g, valores, probabilidades):
    """Transformada inversa discreta: se recorre la acumulada hasta superar U."""
    # Sirve para elegir al azar uno de varios valores posibles, cada uno con
    # su propia probabilidad. Ejemplo: cantidad de valijas 0, 1 o 2 con
    # probabilidades 30 %, 55 % y 15 %.
    #
    # La idea es como una ruleta: se sortea un número entre 0 y 1 y se van
    # sumando las probabilidades hasta que la suma supera al número sorteado.

    # Número sorteado (dónde "cae la bolita" de la ruleta)
    u = g.random()
    # Suma acumulada de probabilidades, arranca en cero
    acum = 0.0
    # Recorremos cada valor posible junto con su probabilidad
    for v, p in zip(valores, probabilidades):
        # Sumamos la probabilidad de este valor
        acum += p
        # Si ya alcanzamos al número sorteado, este es el valor elegido
        if u <= acum:
            return v
    # Por seguridad (errores de redondeo), si no se eligió ninguno
    # devolvemos el último valor de la lista
    return valores[-1]


def bernoulli(g, p):
    # Simula un "sí o no" con probabilidad p de que salga "sí".
    # Es como tirar una moneda cargada: devuelve 1 (sí) o 0 (no).
    # Ejemplo: ¿el pasajero se presenta al vuelo? Sí con probabilidad 0,85.
    return 1 if g.random() < p else 0


def binomial(g, n, p):
    """Suma de n Bernoulli (método de convolución)."""
    # Cuenta cuántos "sí" salen al repetir n veces el experimento anterior.
    # Ejemplo: de 180 asientos, ¿cuántos pasajeros se presentan?
    return sum(bernoulli(g, p) for _ in range(n))


def normal_estandar(g):
    """Box-Muller: Z = sqrt(-2 ln U1) · cos(2π U2)."""
    # Genera un valor con la clásica forma de "campana" (distribución normal),
    # centrada en 0 y con dispersión 1. Para lograrlo usa dos números al azar
    # entre 0 y 1 y los combina con una fórmula conocida (método Box-Muller).
    u1, u2 = g.random(), g.random()
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def normal_truncada(g, mu, sigma, lo, hi, max_intentos=10_000):
    """ACEPTACIÓN-RECHAZO: se genera N(mu, sigma) y se acepta solo si cae en
    [lo, hi]. La probabilidad de aceptar es P(lo ≤ X ≤ hi); el número de
    intentos es geométrico."""
    # Genera un valor con forma de campana (centrado en mu, con dispersión
    # sigma) pero que obligatoriamente quede entre un mínimo (lo) y un
    # máximo (hi). Ejemplo: con cuántos minutos de anticipación llega un
    # pasajero, sabiendo que nunca llega menos de 25 ni más de 180 minutos antes.
    #
    # El método es simple: sorteamos un valor; si queda dentro del rango lo
    # aceptamos, si no lo descartamos y volvemos a sortear.
    for _ in range(max_intentos):
        # Pasamos de la campana "estándar" (centrada en 0) a la que queremos
        # (centrada en mu y con dispersión sigma)
        x = mu + sigma * normal_estandar(g)
        # Si el valor cae dentro del rango permitido, lo devolvemos
        if lo <= x <= hi:
            return x
    # Si después de muchísimos intentos nunca cayó dentro del rango,
    # algo está mal configurado (el rango es casi imposible): avisamos con un error
    raise RuntimeError("tasa de aceptación demasiado baja")
