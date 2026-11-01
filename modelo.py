
# Modelo de simulación discreta del check-in de un vuelo.

# Enfoque: PLANIFICACIÓN DE EVENTOS con avance de reloj VARIABLE (de evento en
# evento). La lista de eventos futuros (LEF) es una cola de prioridad (heap)
# ordenada por tiempo.

# Unidad de tiempo: minutos. 
# El reloj arranca en t = 0 = 180 min antes de la
# salida programada del vuelo (STD - 180). 
# Por eso un tiempo t equivale a "180 - t minutos antes de la salida".

# Eventos:
#   APERTURA  (abre un puesto de check-in)
#   LLEGADA   (un pasajero llega a la fila)
#   FIN       (un puesto termina de atender a un pasajero)
#   CIERRE    (cierre del check-in: las llegadas posteriores se rechazan;
#              quienes ya están en la fila igual son atendidos)

# Aqui se simula lo que pasa en los mostradores de
# check-in de un vuelo, desde 3 horas antes de la salida.
#
# La simulación: En vez de avanzar el reloj minuto a minuto,
# salta directamente de un suceso al siguiente (llega un pasajero, un
# puesto termina de atender, abre un puesto...). Todos los sucesos que van a
# pasar se anotan en una "agenda" ordenada por hora, y el programa los va
# tomando de a uno, del más temprano al más tardío.
#
# El archivo tiene tres partes:
#   1) Crear los pasajeros del vuelo (cuándo llegan, si traen valijas, etc.)
#   2) El motor que simula la fila y los puestos
#   3) Calcular los resultados (esperas, largo de fila, uso de los puestos...)

import heapq
from collections import deque
from generador import LCG
import variables as va

# Duración total de la simulación: 180 minutos (3 horas antes del vuelo).
# El minuto 0 de la simulación = 3 horas antes; el minuto 180 = hora de salida.
HORIZONTE = 180.0                    

# Tipos de sucesos. El número indica qué se resuelve primero si dos sucesos
# ocurren exactamente en el mismo instante (el más chico va primero).
# Prioridad de eventos simultáneos: primero se liberan puestos, luego aperturas,
# luego cierre, luego llegadas.
FIN, APERTURA, CIERRE, LLEGADA = 0, 1, 2, 3

# Configuración "normal" del escenario. Todos los experimentos parten de acá
# y cambian solo lo que quieren probar.
PARAMETROS_BASE = {
    # Vuelo y demanda
    "asientos": 180,                 
    "ocupacion": 0.85,               

    # Anticipación con que llega cada pasajero (min antes de la salida)
    # En promedio 100 min antes, con una variación típica de 25 min,
    # y nunca menos de 25 ni más de 180 min antes.
    "antic_media": 100.0, "antic_desvio": 25.0,
    "antic_min": 25.0, "antic_max": 180.0,

    # Horario del check-in (min antes de la salida)
    "apertura_antes": 120.0,         
    "cierre_antes": 40.0,            

    # Atributos de los pasajeros
    "p_web": 0.20,                   # proporción con check-in web hecho

    # Cantidad de valijas posibles y la probabilidad de cada una
    # (30 % sin valija, 55 % con una, 15 % con dos)
    "valijas_valores": [0, 1, 2],
    "valijas_probs": [0.30, 0.55, 0.15],

    # Tiempos de servicio (mín, moda, máx) en minutos
    "serv_checkin": (0.7, 1.2, 3.0),     # check-in completo en mostrador
    "serv_bagdrop": (0.4, 0.7, 1.5),     # solo despacho (ya hizo web check-in)
    "serv_valija": (0.2, 0.4, 0.9),      # adicional por cada valija

    # Multiplicador de todos los tiempos de atención (1.2 = un 20 % más lentos)
    "factor_servicio": 1.0,              # para análisis de sensibilidad

    # Recursos y política
    "puestos": 4,
    "apertura_escalonada": None,     # lista de minutos-antes-de-salida en que abre cada puesto
    "modo_cola": "unica",            # "unica" (fila serpentina) o "multiple" (una fila por puesto)
}

# ---------------------------------------------------------------------------
# 1) Generación de las entradas (pasajeros) — números aleatorios comunes
# ---------------------------------------------------------------------------
def generar_pasajeros(p, replica, semilla=12345):
    """Genera los pasajeros de una réplica.

    Cada fuente de aleatoriedad usa su propio flujo del generador:
      flujo 3r+0 → presentación y hora de llegada
      flujo 3r+1 → check-in web y cantidad de valijas
      flujo 3r+2 → tiempos de servicio
    Se consumen SIEMPRE los mismos números para cada asiento, de modo que dos
    escenarios con la misma réplica ven exactamente los mismos pasajeros
    (técnica de números aleatorios comunes → comparaciones más precisas).
    """
    # Crea la lista de pasajeros que pasarán por el mostrador en una
    # "repetición" (réplica) de la simulación.
    # - p: los parámetros del escenario
    # - replica: número de repetición (cada una tiene pasajeros distintos)
    #
    # Idea clave: si comparamos "3 puestos" contra "4 puestos" con la misma
    # réplica, los pasajeros son exactamente los mismos. Así la diferencia
    # que veamos se debe solo a los puestos y no a la suerte.

    # Tres generadores independientes, uno para cada tipo de dato
    g_lleg = LCG(semilla, 3 * replica + 0)
    g_attr = LCG(semilla, 3 * replica + 1)
    g_serv = LCG(semilla, 3 * replica + 2)
    pasajeros = []
    # Recorremos cada asiento del avión
    for _ in range(p["asientos"]):
        # ¿Este asiento tiene un pasajero que se presenta? (1 = sí, 0 = no)
        se_presenta = va.bernoulli(g_lleg, p["ocupacion"])
        # ¿Con cuántos minutos de anticipación llega al aeropuerto?
        antic = va.normal_truncada(g_lleg, p["antic_media"], p["antic_desvio"],
                                   p["antic_min"], p["antic_max"])
        # Número al azar que después decide si hizo el check-in web
        u_web = g_attr.random()
        # Cuántas valijas trae
        valijas = va.discreta_empirica(g_attr, p["valijas_valores"], p["valijas_probs"])
        # Sorteamos todos los tiempos posibles de atención, aunque después
        # no se usen todos. Esto es a propósito: así siempre se consumen los
        # mismos números al azar por asiento, sin importar el escenario.
        t_checkin = va.triangular(g_serv, *p["serv_checkin"])
        t_bagdrop = va.triangular(g_serv, *p["serv_bagdrop"])
        t_valijas = [va.triangular(g_serv, *p["serv_valija"]) for _ in range(2)]
        # Si el pasajero no viaja, pasamos al siguiente asiento
        if not se_presenta:
            continue
        # ¿Hizo check-in web? (según la proporción del escenario)
        web = u_web < p["p_web"]
        # Si ya hizo check-in web y no trae valijas, no pasa por el mostrador
        if web and valijas == 0:
            continue                  # web check-in sin valijas: va directo a seguridad
        # Tiempo base: solo dejar valijas (si hizo web) o check-in completo
        base = t_bagdrop if web else t_checkin
        # Tiempo total = base + un extra por cada valija, ajustado por el factor
        servicio = (base + sum(t_valijas[:valijas])) * p["factor_servicio"]
        # Guardamos al pasajero. La hora de llegada se pasa al reloj de la
        # simulación (minuto 0 = 3 h antes del vuelo).
        pasajeros.append({"llegada": HORIZONTE - antic, "servicio": servicio,
                          "web": web, "valijas": valijas})
    # Ordenamos a los pasajeros por hora de llegada
    pasajeros.sort(key=lambda x: x["llegada"])
    return pasajeros


# ---------------------------------------------------------------------------
# 2) Motor de simulación por eventos
# ---------------------------------------------------------------------------
def simular(pasajeros, aperturas, modo_cola="unica", t_cierre=float("inf"),
            registrar_traza=False):
    """Simula la atención.

    pasajeros : lista de dicts con 'llegada' y 'servicio' (minutos)
    aperturas : instante en que abre cada puesto (len = cantidad de puestos)
    modo_cola : 'unica' o 'multiple' (el pasajero elige la fila más corta)
    t_cierre  : llegadas posteriores se rechazan
    """
    # registrar_traza: si es True, se anota el largo de la fila en cada
    # momento (sirve para hacer el gráfico de la fila en el tiempo).

    # Cantidad de puestos
    c = len(aperturas)
    # La "agenda" de sucesos futuros. seq es un contador que desempata
    # sucesos que caen en el mismo instante y son del mismo tipo.
    lef, seq = [], 0                                   # lista de eventos futuros

    def programar(t, tipo, dato=None):
        # Anota un suceso en la agenda: a qué hora (t), de qué tipo y con
        # qué dato asociado (un pasajero, un número de puesto, etc.)
        nonlocal seq
        heapq.heappush(lef, (t, tipo, seq, dato)); seq += 1

    # Estado del sistema
    # ¿Cada puesto está abierto? Al principio, ninguno
    abierto = [False] * c
    # A quién está atendiendo cada puesto (None = está libre)
    ocupado = [None] * c                               # pasajero en atención
    # Las filas: una sola compartida, o una por cada puesto
    colas = [deque()] if modo_cola == "unica" else [deque() for _ in range(c)]
    # Copia de las horas de apertura (se devuelve al final)
    t_apertura_real = list(aperturas)
    # Cuánto tiempo estuvo trabajando cada puesto, en total
    ocupado_acum = [0.0] * c                           # tiempo ocupado de cada puesto
    # Cuántos pasajeros llegaron tarde (después del cierre)
    rechazados = 0

    # Para calcular el largo promedio de la fila vamos sumando
    # "personas en fila × tiempo que estuvieron así" (area_lq).
    # Estadísticas de tiempo continuo: largo de cola (área bajo Lq(t))
    # reloj = hora actual; t_ult = hora del suceso anterior;
    # lq_max = la fila más larga que se vio
    reloj, t_ult, area_lq, lq_max = 0.0, 0.0, 0.0, 0
    # Registro del largo de la fila en el tiempo (solo si se pidió)
    traza = []

    def lq():
        # Cantidad total de personas esperando en fila(s) en este momento
        return sum(len(q) for q in colas)

    # Solo medimos la fila desde que abre el primer puesto
    # (antes de abrir, la gente que espera no cuenta como "fila evitable")
    t_stats = min(aperturas)                           # Lq(t) se integra desde la apertura

    def actualizar_area(t):
        # Antes de procesar cada suceso, sumamos cuánta gente hubo en la fila
        # desde el suceso anterior hasta ahora
        nonlocal t_ult, area_lq
        if t > t_stats:
            area_lq += lq() * (t - max(t_ult, t_stats))
        t_ult = t

    def iniciar_servicio(i, pax, t):
        # El puesto i empieza a atender al pasajero pax en el instante t
        ocupado[i] = pax
        # Anotamos en el pasajero cuándo y dónde lo empezaron a atender
        pax["inicio"], pax["puesto"] = t, i
        # Agendamos el momento en que va a terminar su atención
        programar(t + pax["servicio"], FIN, i)

    def cola_de(i):
        # Devuelve la fila que corresponde al puesto i
        # (la única compartida, o la propia del puesto)
        return colas[0] if modo_cola == "unica" else colas[i]

    # Inicialización
    # Agendamos la apertura de cada puesto
    for i, ta in enumerate(aperturas):
        programar(ta, APERTURA, i)
    # Agendamos el cierre del check-in (si hay hora de cierre)
    if t_cierre != float("inf"):
        programar(t_cierre, CIERRE)
    # Agendamos la llegada de cada pasajero
    for pax in pasajeros:
        programar(pax["llegada"], LLEGADA, pax)

    # Lista de pasajeros que ya fueron atendidos
    atendidos = []
    # Bucle principal: mientras queden sucesos en la agenda, tomamos el
    # próximo (el de hora más temprana) y lo procesamos
    while lef:
        # Sacamos el próximo suceso y adelantamos el reloj hasta su hora
        reloj, tipo, _, dato = heapq.heappop(lef)       # avance de reloj variable
        # Sumamos al registro de la fila el tiempo transcurrido
        actualizar_area(reloj)

        # --- Suceso: LLEGA UN PASAJERO ---
        if tipo == LLEGADA:
            pax = dato
            # Si llegó después del cierre, no se lo atiende
            if reloj > t_cierre:
                rechazados += 1
                pax["rechazado"] = True
                continue
            if modo_cola == "unica":
                # Fila única: buscamos puestos abiertos y libres
                libres = [i for i in range(c) if abierto[i] and ocupado[i] is None]
                if libres:
                    # Si hay uno libre, pasa directo a ser atendido
                    iniciar_servicio(libres[0], pax, reloj)
                else:
                    # Si no, se pone al final de la fila
                    colas[0].append(pax)
            else:
                # Una fila por puesto: el pasajero elige la más corta
                # elige el puesto con menos gente (fila + en atención);
                # antes de la apertura considera todos los puestos
                candidatos = [i for i in range(c) if abierto[i]] or list(range(c))
                i = min(candidatos, key=lambda k: len(colas[k]) + (ocupado[k] is not None))
                if abierto[i] and ocupado[i] is None:
                    # El puesto elegido está libre: lo atienden ya
                    iniciar_servicio(i, pax, reloj)
                else:
                    # Si no, espera en la fila de ese puesto
                    colas[i].append(pax)

        # --- Suceso: UN PUESTO TERMINA DE ATENDER ---
        elif tipo == FIN:
            i = dato
            pax = ocupado[i]
            # Anotamos a qué hora terminó
            pax["fin"] = reloj
            # Sumamos el tiempo que el puesto estuvo trabajando
            ocupado_acum[i] += pax["servicio"]
            atendidos.append(pax)
            # El puesto queda libre
            ocupado[i] = None
            # Si hay gente esperando en su fila, llama al siguiente
            q = cola_de(i)
            if q:
                iniciar_servicio(i, q.popleft(), reloj)

        # --- Suceso: ABRE UN PUESTO ---
        elif tipo == APERTURA:
            i = dato
            abierto[i] = True
            # Si ya hay gente esperando, empieza a atender de inmediato
            q = cola_de(i)
            if q:
                iniciar_servicio(i, q.popleft(), reloj)

        # --- Suceso: CIERRA EL CHECK-IN ---
        elif tipo == CIERRE:
            # No hay que hacer nada acá: el rechazo de los que llegan tarde
            # ya se controla en el suceso de LLEGADA
            pass                                       # las llegadas posteriores se rechazan

        # Después de cada suceso, revisamos si la fila es la más larga vista
        lq_actual = lq()
        lq_max = max(lq_max, lq_actual)
        # Si se pidió, anotamos (hora, largo de la fila) para el gráfico
        if registrar_traza:
            traza.append((reloj, lq_actual))

    # Hora en que terminó de atenderse al último pasajero
    t_fin = max((p["fin"] for p in atendidos), default=reloj)
    # Devolvemos todos los datos crudos de la simulación
    return {"atendidos": atendidos, "rechazados": rechazados,
            "area_lq": area_lq, "lq_max": lq_max, "t_fin": t_fin,
            "ocupado_acum": ocupado_acum, "aperturas": t_apertura_real,
            "traza": traza}


# ---------------------------------------------------------------------------
# 3) Indicadores de una réplica
# ---------------------------------------------------------------------------
def percentil(xs, q):
    # Calcula el percentil q de una lista. Por ejemplo, con q = 0.95 devuelve
    # el valor que deja por debajo al 95 % de los datos ("el 95 % esperó
    # menos que esto").
    s = sorted(xs)
    # Si la lista está vacía, devolvemos 0
    if not s:
        return 0.0
    # Posición (puede tener decimales) donde está el percentil
    k = (len(s) - 1) * q
    f = int(k)
    # Si la posición cae entre dos valores, interpolamos entre ambos
    return s[f] + (s[min(f + 1, len(s) - 1)] - s[f]) * (k - f)


def correr_replica(p, replica, semilla=12345, registrar_traza=False):
    # Corre una repetición completa de un escenario: crea los pasajeros,
    # simula y calcula todos los indicadores que nos interesan.

    # 1) Crear los pasajeros de esta repetición
    pasajeros = generar_pasajeros(p, replica, semilla)
    # 2) Pasar las horas de apertura y cierre al reloj de la simulación
    t_ap = HORIZONTE - p["apertura_antes"]
    t_ci = HORIZONTE - p["cierre_antes"]
    # Si los puestos abren en horarios distintos, usamos esa lista;
    # si no, todos abren a la misma hora
    if p.get("apertura_escalonada"):
        aperturas = [HORIZONTE - a for a in p["apertura_escalonada"]]
    else:
        aperturas = [t_ap] * p["puestos"]
    # 3) Simular
    r = simular(pasajeros, aperturas, p["modo_cola"], t_ci, registrar_traza)
    # Hora en que abrió el primer puesto
    t_ap = min(aperturas)                  # apertura del primer puesto

    # 4) Calcular indicadores
    at = r["atendidos"]
    # Espera de cada pasajero contando desde que llegó
    esperas = [x["inicio"] - x["llegada"] for x in at]
    # la espera "evitable" se mide desde la apertura: quien llega antes de que
    # abra el check-in no puede ser atendido antes de esa hora
    esperas_desde_ap = [x["inicio"] - max(x["llegada"], t_ap) for x in at]
    # Cuánto duró la atención desde que abrió el primer puesto
    duracion = r["t_fin"] - t_ap
    # Uso de los puestos: tiempo trabajando / tiempo que estuvieron abiertos
    utiliz = sum(r["ocupado_acum"]) / sum(r["t_fin"] - a for a in r["aperturas"])
    return {
        "replica": replica,
        # Cuántos pasajeros pasaron por el mostrador
        "pax_mostrador": len(at),
        # Cuántos llegaron después del cierre
        "rechazados": r["rechazados"],
        # Espera promedio (desde la apertura), en minutos
        "espera_media": sum(esperas_desde_ap) / len(at),
        # Espera que no superó el 95 % de los pasajeros
        "espera_p95": percentil(esperas_desde_ap, 0.95),
        # La espera más larga de todas
        "espera_max": max(esperas_desde_ap),
        # Porcentaje de pasajeros que esperó más de 15 minutos
        "pct_espera_15": 100 * sum(w > 15 for w in esperas_desde_ap) / len(at),
        # Espera promedio contando desde que llegó (incluye esperar a que abra)
        "espera_total_media": sum(esperas) / len(at),
        # Cantidad promedio de personas en la fila
        "lq_media": r["area_lq"] / max(duracion, 1e-9) if duracion > 0 else 0,
        # La fila más larga que hubo
        "lq_max": r["lq_max"],
        # Porcentaje del tiempo que los puestos estuvieron trabajando
        "utilizacion": 100 * utiliz,
        # Cuántos fueron atendidos después de la hora de cierre
        # (estaban en la fila cuando cerró)
        "atendidos_post_cierre": sum(x["inicio"] > t_ci for x in at),
        # Cuántos minutos antes del vuelo terminó de atenderse al último
        "fin_antes_salida": HORIZONTE - r["t_fin"],   # min antes de la salida
        # Registro de la fila en el tiempo (solo para gráficos; empieza con _
        # para indicar que es un dato interno, no un indicador)
        "_traza": r["traza"],
    }


def con(**cambios):
    """Devuelve una copia de los parámetros base con cambios."""
    # Atajo para armar escenarios. Por ejemplo, con(puestos=5) devuelve la
    # configuración base pero con 5 puestos. No modifica la original.
    p = dict(PARAMETROS_BASE)
    p.update(cambios)
    return p
