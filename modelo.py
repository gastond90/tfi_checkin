# Modelo de simulación discreta del check-in de un vuelo.
#
# Planificación de eventos con avance de reloj variable: el reloj salta
# de un evento al siguiente. La lista de eventos futuros (LEF) se mantiene
# ordenada por tiempo.
#
# Unidad de tiempo: minutos. 
# El reloj arranca en t = 0, que corresponde a 180 minutos antes de la salida del vuelo. 
# Un pasajero que llega "100 minutos antes de la salida" llega en t = 180 - 100 = 80.
#
# Eventos:
#   APERTURA  abre un puesto de check-in
#   LLEGADA   un pasajero llega a la fila
#   FIN       un puesto termina de atender a un pasajero
#   CIERRE    cierre del check-in: las llegadas posteriores se rechazan
#             (quienes ya están en la fila igual son atendidos)

# Se simula lo que pasa en los mostradores de
# check-in de un vuelo desde 3 horas antes de la salida.
#
# En vez de avanzar el reloj minuto a minuto, salta
# directamente de un suceso al siguiente. Todos los sucesos que van a pasar
# se anotan en una agenda ordenada por hora, y el programa los va tomando
# de a uno, del más temprano al más tardío.
#
# El archivo tiene tres partes:
#   1) Crear los pasajeros del vuelo (cuándo llegan, si traen valijas, etc.)
#   2) El motor que simula la fila y los puestos
#   3) Calcular los resultados (esperas, largo de la fila, uso de los puestos...)

import heapq
from collections import deque
from generador import LCG
import variables as va

# Duración total de lo simulado: 180 minutos (3 horas antes del vuelo).
# El minuto 0 de la simulación = 3 h antes; el minuto 180 = hora de salida.
HORIZONTE = 180.0          # t = 0 equivale a 180 minutos antes de la salida

# Tipos de sucesos. El número indica cuál se resuelve primero si dos ocurren
# exactamente al mismo tiempo (el más chico va primero). Por ejemplo, primero
# se libera un puesto y después se procesa la llegada de alguien.
# Si dos eventos ocurren en el mismo instante se procesan en este orden
FIN, APERTURA, CIERRE, LLEGADA = 0, 1, 2, 3

# Escenario "normal". Todos los experimentos parten de acá
# y cambian solo lo que quieren probar.
PARAMETROS_BASE = {
    # Vuelo
    "asientos": 180,                      
    "ocupacion": 0.85,                    

    # Llegada de cada pasajero, en minutos ANTES de la salida
    "llegada": (30.0, 100.0, 180.0),      # (mínimo, más probable, máximo)

    # Horario del check-in, en minutos antes de la salida
    "apertura_antes": 120.0,
    "cierre_antes": 40.0,

    # Pasajeros
    "p_web": 0.20,                        # proporción con check-in web hecho

    # Cantidad de valijas posibles y la probabilidad de cada una
    # (30 % sin valija, 55 % con una, 15 % con dos)
    "valijas_valores": [0, 1, 2],
    "valijas_probs": [0.30, 0.55, 0.15],

    # Tiempos de atención en minutos (mínimo, más probable, máximo)
    "serv_checkin": (0.7, 1.2, 3.0),      # check-in completo
    "serv_despacho": (0.4, 0.7, 1.5),     # solo despacho (hizo check-in web)
    "serv_valija": (0.2, 0.4, 0.9),       # adicional por cada valija
    "factor_servicio": 1.0,               # 1,2 = atención 20 % más lenta (sensibilidad)

    # Recursos
    "puestos": 4,
    "aperturas": None,    # opcional: minutos antes de la salida en que abre CADA puesto
}


# 1) Generar los pasajeros de un vuelo
def generar_pasajeros(p, replica, semilla=12345):
    # Crea los pasajeros de una réplica (un vuelo).
    #
    # Cada fuente de azar usa su propio flujo del generador:
    #   flujo 3r+0 → si se presenta y hora de llegada
    #   flujo 3r+1 → check-in web y cantidad de valijas
    #   flujo 3r+2 → tiempos de atención
    #
    # Así, la réplica r tiene los MISMOS pasajeros en todos los escenarios y las
    # diferencias entre escenarios se deben solo al cambio que se está probando.

    # - p:  parámetros del escenario
    # - replica: número de repetición (cada una es un vuelo distinto)

    # Tres generadores independientes, uno para cada tipo de dato
    g_lleg = LCG(semilla, 3 * replica + 0)
    g_attr = LCG(semilla, 3 * replica + 1)
    g_serv = LCG(semilla, 3 * replica + 2)
    pasajeros = []

    # Recorro cada asiento del avión
    for _ in range(p["asientos"]):
        # se generan todos los valores aunque el asiento quede vacío,
        # para que cada asiento use siempre los mismos números

        # El asiento tiene un pasajero que se presenta (1 = sí, 0 = no)
        se_presenta = va.bernoulli(g_lleg, p["ocupacion"])

        # Con cuántos minutos de anticipación llega al aeropuerto
        antes = va.triangular(g_lleg, *p["llegada"])

        # hizo check-in web (True = sí)
        web = g_attr.random() < p["p_web"]

        # Cuántas valijas trae
        valijas = va.discreta_empirica(g_attr, p["valijas_valores"], p["valijas_probs"])

        # Tiempos posibles de atención (después se usan solo los que correspondan)
        t_checkin = va.triangular(g_serv, *p["serv_checkin"])
        t_despacho = va.triangular(g_serv, *p["serv_despacho"])

        # Tiempo extra para cada una de hasta dos valijas
        t_valijas = [va.triangular(g_serv, *p["serv_valija"]) for _ in range(2)]

        # Si el asiento quedó vacío, se pasa al siguiente
        if not se_presenta:
            continue

        # Si ya hizo check-in web y no trae valijas, no tiene nada que hacer
        # en el mostrador: no entra en la simulación
        if web and valijas == 0:
            continue                      # check-in web sin valijas: no pasa por el mostrador

        # Tiempo base: solo dejar valijas (si hizo web) o check-in completo
        base = t_despacho if web else t_checkin

        # Tiempo total = base + un extra por cada valija, ajustado por el factor
        servicio = (base + sum(t_valijas[:valijas])) * p["factor_servicio"]

        # se guarda al pasajero. La hora de llegada se pasa al reloj de la
        # simulación.
        pasajeros.append({"llegada": HORIZONTE - antes, "servicio": servicio})
    return pasajeros


# 2) Motor de simulación por eventos
def simular(pasajeros, aperturas, t_cierre=float("inf"), registrar_traza=False):
    # Hace pasar a los pasajeros por el check-in (fila única, FIFO).
    #
    # pasajeros : lista de dicts con 'llegada' y 'servicio' (minutos)
    # aperturas : instante en que abre cada puesto (uno por puesto)
    # t_cierre  : las llegadas posteriores se rechazan

    # FIFO = el primero que llega es el primero que atienden.
    # registrar_traza: si es True, se anota el largo de la fila en cada
    # momento.

    # Cantidad de puestos
    
    c = len(aperturas)
    # "agenda" de sucesos futuros
    lef = []                          # lista de eventos futuros: (tiempo, tipo, nº, dato)
    # Número de orden de cada suceso agendado, desempata sucesos iguales
    # que caen en el mismo instante
    contador = 0

    def programar(t, tipo, dato=None):
        # Anota un suceso en la agenda: a qué hora (t), de qué tipo y con qué
        # dato asociado (un pasajero, un número de puesto, etc.)
        nonlocal contador
        heapq.heappush(lef, (t, tipo, contador, dato))
        contador += 1

    # Estado del sistema
    abierto = [False] * c             # si el puesto ya abrió
    ocupado = [None] * c              # pasajero que está atendiendo cada puesto
    fila = deque()                    # fila única

    # Cuánto tiempo estuvo trabajando cada puesto, en total
    tiempo_ocupado = [0.0] * c

    # Pasajeros ya atendidos, cuántos llegaron tarde, la fila más larga vista
    # y el registro de la fila en el tiempo
    atendidos, rechazados, fila_max, traza = [], 0, 0, []

    def atender(i, pax, t):
        # El puesto i empieza a atender al pasajero pax en el instante t
        ocupado[i] = pax
        # Se anota cuándo lo empezaron a atender
        pax["inicio"] = t
        # Se agenda el momento en que va a terminar
        programar(t + pax["servicio"], FIN, i)

    # Inicialización: se cargan en la LEF las aperturas, el cierre y las llegadas
    for i, t in enumerate(aperturas):
        programar(t, APERTURA, i)
    if t_cierre != float("inf"):
        programar(t_cierre, CIERRE)
    for pax in pasajeros:
        programar(pax["llegada"], LLEGADA, pax)

    # Bucle principal: tomar el próximo evento, adelantar el reloj y ejecutar su rutina
    while lef:
        # Se saca de la agenda el suceso más próximo; el reloj salta a su hora
        reloj, tipo, _, dato = heapq.heappop(lef)

        # --- Suceso: LLEGA UN PASAJERO ---
        if tipo == LLEGADA:
            pax = dato
            # Si llegó después del cierre, no se lo atiende
            if reloj > t_cierre:
                rechazados += 1
            else:
                # Se buscan puestos abiertos y libres
                libres = [i for i in range(c) if abierto[i] and ocupado[i] is None]
                if libres:
                    # Hay uno libre: pasa directo a ser atendido
                    atender(libres[0], pax, reloj)
                else:
                    # No hay ninguno libre: se pone al final de la fila
                    fila.append(pax)

        # --- Suceso: UN PUESTO TERMINA DE ATENDER ---
        elif tipo == FIN:
            i = dato
            pax = ocupado[i]
            # Se anota a qué hora terminó
            pax["fin"] = reloj
            # Se suma el tiempo que el puesto estuvo trabajando
            tiempo_ocupado[i] += pax["servicio"]
            atendidos.append(pax)
            # El puesto queda libre
            ocupado[i] = None
            # Si hay gente esperando, llama al primero de la fila
            if fila:
                atender(i, fila.popleft(), reloj)

        # --- Suceso: ABRE UN PUESTO ---
        elif tipo == APERTURA:
            i = dato
            abierto[i] = True
            # Si ya hay gente esperando, empieza a atender enseguida
            if fila:
                atender(i, fila.popleft(), reloj)

        # --- Suceso: CIERRA EL CHECK-IN ---
        elif tipo == CIERRE:
            # No hace falta hacer nada acá: el rechazo de los que llegan
            # tarde ya se controla en el suceso de LLEGADA
            pass                      # desde ahora las llegadas se rechazan

        # Después de cada suceso, se revisa si la fila es la más larga vista
        fila_max = max(fila_max, len(fila))
        # Si se pidió, se anota para el gráfico
        if registrar_traza:
            traza.append((reloj, len(fila)))

    # Hora en que terminó de atenderse al último pasajero
    t_fin = max(p["fin"] for p in atendidos)
    # Mostrar datos de la simulación
    return {"atendidos": atendidos, "rechazados": rechazados, "fila_max": fila_max,
            "t_fin": t_fin, "tiempo_ocupado": tiempo_ocupado, "traza": traza}


# 3) Correr un vuelo y calcular sus indicadores
def percentil(xs, q):
    # Calcula el percentil q de una lista. q = 0.95 devuelve el valor que
    # deja por debajo al 95 % de los datos ("el 95 % esperó menos que esto").
    s = sorted(xs)
    # Posición donde está el percentil
    k = (len(s) - 1) * q
    f = int(k)
    # Si la posición cae entre dos valores, se toma un punto intermedio
    return s[f] + (s[min(f + 1, len(s) - 1)] - s[f]) * (k - f)


def correr_replica(p, replica, semilla=12345, registrar_traza=False):
    # Corre un vuelo completo de un escenario: crea los pasajeros, simula
    # y calcula los indicadores que nos interesan.

    # 1) Crear los pasajeros de este vuelo
    pasajeros = generar_pasajeros(p, replica, semilla)

    # 2) Calcular a qué hora (en el reloj de la simulación) abre cada puesto.
    # Si se indicó un horario distinto para cada puesto se usa esa lista;
    # si no, todos abren juntos.
    if p["aperturas"]:
        aperturas = [HORIZONTE - a for a in p["aperturas"]]
    else:
        aperturas = [HORIZONTE - p["apertura_antes"]] * p["puestos"]

    # Hora de cierre del check-in en el reloj de la simulación
    t_cierre = HORIZONTE - p["cierre_antes"]

    # 3) Simular
    r = simular(pasajeros, aperturas, t_cierre, registrar_traza)

    # 4) Calcular indicadores
    at = r["atendidos"]
    # Cuánto esperó cada pasajero, contando desde que llegó
    esperas = [x["inicio"] - x["llegada"] for x in at]          # desde que llegó
    
    # Tiempo total que estuvieron abiertos los puestos (sumando todos)
    tiempo_abierto = sum(r["t_fin"] - a for a in aperturas)
    return {
        "replica": replica,

        # Cuántos pasajeros pasaron por el mostrador
        "pasajeros": len(at),

        # Cuántos llegaron después del cierre
        "rechazados": r["rechazados"],

        # Espera promedio, en minutos
        "espera_media": sum(esperas) / len(at),

        # Espera que no superó el 95 % de los pasajeros
        "espera_p95": percentil(esperas, 0.95),

        # Porcentaje de pasajeros que esperó más de 15 minutos
        "pct_espera_15": 100 * sum(w > 15 for w in esperas) / len(at),

        # La fila más larga que hubo
        "fila_max": r["fila_max"],

        # Porcentaje del tiempo que los puestos estuvieron trabajando
        "utilizacion": 100 * sum(r["tiempo_ocupado"]) / tiempo_abierto,

        # Cuántos seguían en la fila cuando cerró el check-in
        # (atendidos después de la hora de cierre)
        "en_fila_al_cierre": sum(x["inicio"] > t_cierre for x in at),

        # Cuántos minutos antes del vuelo terminó de atenderse al último
        "fin_antes_salida": HORIZONTE - r["t_fin"],

        # Registro de la fila en el tiempo (solo para el gráfico; empieza
        # con _ para indicar que es un dato interno, no un indicador)
        "_traza": r["traza"],
    }


def con(**cambios):
    # Copia de los parámetros base con algunos cambios.
    # Atajo para armar escenarios. Por ejemplo, con(puestos=5) devuelve la
    # configuración base pero con 5 puestos. No modifica la original.
    p = dict(PARAMETROS_BASE)
    p.update(cambios)
    return p
