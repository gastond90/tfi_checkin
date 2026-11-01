
#Diseño de experimentos, replicaciones y análisis de resultados.

# Cada escenario se corre R veces (réplicas independientes). Todas las réplicas
# r de distintos escenarios usan los mismos flujos aleatorios (números
# aleatorios comunes), por lo que las diferencias entre escenarios se pueden
# analizar con comparaciones PAREADAS.

# Se define una serie de "escenarios" ( 3, 4, 5 o 6 puestos, etc,
# , si más gente hace check-in web, etc.), simula cada uno muchas veces,
# compara los resultados entre sí y genera tablas (CSV) y gráficos (PNG).

# Salida: carpeta resultados/ (CSV) y figuras/ (PNG).

import csv, math, os, statistics as st
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Traigo el modelo
from modelo import con, correr_replica, generar_pasajeros, HORIZONTE, PARAMETROS_BASE

# Cuántas veces se repite cada escenario. Más repeticiones = resultados más
# confiables, pero tarda más.
R = 100                      # réplicas por escenario (ver replicas_necesarias.csv)

# Lista de indicadores que a resumir en cada escenario. explicados en modelo.correr_replica)
METRICAS = ["espera_media", "espera_total_media", "espera_p95", "espera_max", "pct_espera_15",
            "lq_media", "lq_max", "utilizacion", "atendidos_post_cierre",
            "fin_antes_salida", "pax_mostrador", "rechazados"]

# ---------------------------------------------------------------------------
# Escenarios
# ---------------------------------------------------------------------------
# Cada escenario tiene un nombre y una configuración. con(...) toma la
# configuración base y cambia solo lo indicado.
ESCENARIOS = {
    # E1 — cantidad de puestos (cola única, 20 % web)
    "E1_c3": con(puestos=3), "E1_c4": con(puestos=4),
    "E1_c5": con(puestos=5), "E1_c6": con(puestos=6),

    # E2 — disciplina de cola
    # ¿Conviene una sola fila para todos o una fila por puesto?
    "E2_c4_unica": con(puestos=4), "E2_c4_multiple": con(puestos=4, modo_cola="multiple"),
    "E2_c5_unica": con(puestos=5), "E2_c5_multiple": con(puestos=5, modo_cola="multiple"),

    # E3 — adopción de check-in web
    # Se arman automáticamente todas las combinaciones de 3 o 4 puestos con
    # 0 %, 20 %, 40 % y 60 % de pasajeros con check-in web
    **{f"E3_c{c}_web{int(w*100)}": con(puestos=c, p_web=w)
       for c in (3, 4) for w in (0.0, 0.2, 0.4, 0.6)},

    # E4 — política de apertura (todas con 4 puestos)
    # Qué pasa si se abre antes, o si algunos puestos abren antes que otros
    "E4_4a120": con(puestos=4),                                       # base
    "E4_4a150": con(puestos=4, apertura_antes=150.0),
    "E4_2a150_2a120": con(puestos=4, apertura_escalonada=[150, 150, 120, 120]),
    "E4_2a150_3a120": con(puestos=5, apertura_escalonada=[150, 150, 120, 120, 120]),

    # E5 — sensibilidad (4 puestos)
    # Cuánto cambian los resultados si algún supuesto no es exacto
    # (atención más rápida/lenta, avión más vacío/lleno, gente que llega más tarde)
    "E5_serv080": con(factor_servicio=0.8), "E5_serv100": con(),
    "E5_serv120": con(factor_servicio=1.2),
    "E5_ocup070": con(ocupacion=0.70), "E5_ocup100": con(ocupacion=1.00),
    "E5_antic_tarde": con(antic_media=85.0),     # pasajeros llegan 15 min más tarde
}


def ic95(xs):
    # Calcula el promedio (m), el margen de error con 95 % de confianza (h)
    # y la dispersión de los datos (s). 
    # El valor real está entre m − h y m + h con 95 % de seguridad.
    n = len(xs); m = st.mean(xs); s = st.stdev(xs) if n > 1 else 0.0
    h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    return m, h, s


def correr_todo():
    # Simulo todos los escenarios, R veces cada uno, y armo tres resultados:
    # - detalle: una fila por cada repetición de cada escenario
    # - resumen: una fila por escenario con promedios y márgenes de error
    # - crudos: los resultados completos, para hacer comparaciones después

    detalle, resumen, crudos = [], [], {}
    for nombre, p in ESCENARIOS.items():
        # Corro las R repeticiones del escenario
        reps = [correr_replica(p, r) for r in range(R)]
        crudos[nombre] = reps
        # Guardo cada repetición en el detalle (sin la traza)
        for x in reps:
            detalle.append({"escenario": nombre, **{k: v for k, v in x.items() if k != "_traza"}})

        # Para cada indicador, calculo promedio y margen de error
        fila = {"escenario": nombre}
        for m in METRICAS:
            media, h, s = ic95([x[m] for x in reps])
            fila[m] = round(media, 3)
            fila[m + "_ic95"] = round(h, 3)
        resumen.append(fila)

        # Muestro en pantalla un resumen del escenario
        print(f"{nombre:18s} espera={fila['espera_media']:6.2f} ±{fila['espera_media_ic95']:.2f} "
              f"p95={fila['espera_p95']:6.2f}  %>15={fila['pct_espera_15']:5.1f}  "
              f"Lqmax={fila['lq_max']:5.1f}  util={fila['utilizacion']:5.1f}  "
              f"post_cierre={fila['atendidos_post_cierre']:5.2f}")
    return detalle, resumen, crudos


def comparaciones_pareadas(crudos):
    # Compara escenarios de a dos para saber si la diferencia entre ellos es
    # real o podría ser casualidad. Como ambos escenarios usan los mismos
    # pasajeros en cada repetición, comparo repetición contra repetición
    # ("pareado"), lo que da conclusiones más precisas.

    # Pares de escenarios a comparar (A contra B)
    pares = [("E1_c3", "E1_c4"), ("E1_c4", "E1_c5"), ("E1_c5", "E1_c6"),
             ("E2_c4_unica", "E2_c4_multiple"), ("E2_c5_unica", "E2_c5_multiple"),
             ("E3_c3_web20", "E3_c3_web60"), ("E3_c3_web60", "E1_c4"),
             ("E4_4a120", "E4_4a150"), ("E4_4a120", "E4_2a150_2a120")]
    filas = []
    for a, b in pares:
        # Comparo en estos cuatro indicadores
        for m in ("espera_media", "espera_total_media", "espera_p95", "lq_max"):
            # Diferencia A − B en cada repetición
            d = [x[m] - y[m] for x, y in zip(crudos[a], crudos[b])]

            # Promedio de las diferencias y su margen de error
            media, h, s = ic95(d)
            # Para mostrar la ventaja del método pareado: cuánta dispersión
            # habría si los escenarios usaran pasajeros distintos
            # varianza de la diferencia si los escenarios fueran independientes
            s_ind = math.sqrt(st.variance([x[m] for x in crudos[a]]) +
                              st.variance([y[m] for y in crudos[b]]))
            filas.append({"A": a, "B": b, "metrica": m,
                          "dif_media_A_menos_B": round(media, 3),
                          "ic95": round(h, 3),
                          # Es "significativa" (real) si el margen de error
                          # no alcanza a cubrir el cero
                          "significativa": abs(media) > h,
                          "desvio_pareado": round(s, 3),
                          "desvio_si_independientes": round(s_ind, 3)})
    return filas


def replicas_necesarias(crudos, escenario="E1_c4", metrica="espera_media", error=0.5):
    # Calcula cuántas repeticiones harían falta para que el margen de error
    # sea de, como mucho, "error" minutos (por defecto medio minuto).
    # Sirve para justificar que R = 100 repeticiones alcanzan.
    xs = [x[metrica] for x in crudos[escenario]]
    # Dispersión de los resultados
    s = st.stdev(xs)
    # Fórmula para estimar la cantidad de repeticiones necesarias
    n = (stats.t.ppf(0.975, len(xs) - 1) * s / error) ** 2
    return {"escenario": escenario, "metrica": metrica, "desvio": round(s, 3),
            "semiancho_deseado": error, "replicas_necesarias": math.ceil(n),
            "replicas_usadas": len(xs),
            "semiancho_obtenido": round(float(ic95(xs)[1]), 3)}


def guardar_csv(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=filas[0].keys())
        w.writeheader(); w.writerows(filas)


# Gráficos
AZUL, NARANJA, AQUA, AMARILLO = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
TINTA, TINTA2, GRILLA, FONDO = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
    "axes.edgecolor": GRILLA, "axes.labelcolor": TINTA2, "xtick.color": TINTA2,
    "ytick.color": TINTA2, "text.color": TINTA, "axes.grid": True,
    "grid.color": GRILLA, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "lines.linewidth": 2,
    "legend.frameon": False, "figure.dpi": 150,
})

# Minutos antes del vuelo en que abre (AP) y cierra (CI) el check-in
AP = PARAMETROS_BASE["apertura_antes"]; CI = PARAMETROS_BASE["cierre_antes"]


def marcar_horario(ax):
    ax.axvline(AP, color=TINTA2, lw=1, ls="--")
    ax.axvline(CI, color=TINTA2, lw=1, ls="--")
    y = ax.get_ylim()[1]
    ax.text(AP, y, " apertura", va="top", ha="left", color=TINTA2, fontsize=9)
    ax.text(CI, y, " cierre", va="top", ha="left", color=TINTA2, fontsize=9)


def fig_llegadas():
    # Gráfico 1: a qué hora llegan los pasajeros al mostrador.
    # Es un histogram con cuántos llegan en cada tramo de 5 minutos,
    # promediando las R repeticiones.

    #Se junta la anticipación de todos los pasajeros de todas las repeticiones
    antic = []
    for r in range(R):
        antic += [HORIZONTE - p["llegada"] for p in generar_pasajeros(con(), r)]
    fig, ax = plt.subplots(figsize=(7, 3.6))

    # Barras cada 5 minutos
    ax.hist(antic, bins=range(20, 185, 5), color=AZUL, edgecolor=FONDO, linewidth=1.5,
            weights=[1 / R] * len(antic))

    ax.set_xlim(185, 20)                         
    ax.set_xlabel("Minutos antes de la salida del vuelo")
    ax.set_ylabel("Pasajeros por intervalo de 5 min")
    ax.set_title("Perfil de llegada de pasajeros al mostrador (promedio de 100 réplicas)")
    marcar_horario(ax)
    fig.tight_layout(); fig.savefig("figuras/fig1_llegadas.png"); plt.close(fig)


def fig_puestos(resumen):
    # Gráfico 2: cómo cambia la espera según la cantidad de puestos (3 a 6).
    # Muestra la espera promedio y la espera del percentil 95, con su margen de error.

    # Se pasa el resumen a un diccionario para buscar escenarios por nombre
    d = {f["escenario"]: f for f in resumen}
    cs = [3, 4, 5, 6]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    for m, col, lab in [("espera_media", AZUL, "Espera media"),
                        ("espera_p95", NARANJA, "Percentil 95 de la espera")]:
        y = [d[f"E1_c{c}"][m] for c in cs]
        e = [d[f"E1_c{c}"][m + "_ic95"] for c in cs]
        ax.errorbar(cs, y, yerr=e, color=col, marker="o", ms=7, capsize=4, label=lab)
        for c, v in zip(cs, y):
            ax.annotate(f"{v:.1f}", (c, v), textcoords="offset points", xytext=(8, 4),
                        color=TINTA, fontsize=9)
    ax.axhline(15, color=TINTA2, lw=1, ls=":")
    ax.text(6.05, 15, "objetivo 15 min", va="bottom", ha="right", color=TINTA2, fontsize=9)
    ax.set_xticks(cs); ax.set_xlabel("Puestos de check-in abiertos")
    ax.set_ylabel("Minutos"); ax.set_ylim(bottom=0)
    ax.set_title("Espera en la fila según cantidad de puestos (IC 95 %)")
    ax.legend(loc="upper right")
    fig.tight_layout(); fig.savefig("figuras/fig2_espera_vs_puestos.png"); plt.close(fig)


def fig_cola_tiempo():
    # Gráfico 3: cómo crece y se achica la fila a lo largo del tiempo,
    # comparando 3, 4 y 5 puestos con exactamente los mismos pasajeros.

    fig, ax = plt.subplots(figsize=(7, 3.8))
    for c, col in [(3, NARANJA), (4, AZUL), (5, AQUA)]:
        # Se corre la primera repetición registrando el largo de la fila
        tr = correr_replica(con(puestos=c), 0, registrar_traza=True)["_traza"]
        # Se pasa el tiempo a "minutos antes de la salida" y se separan los largos
        xs = [HORIZONTE - t for t, _ in tr]; ys = [q for _, q in tr]
        # Gráfico "en escalera": la fila cambia de golpe en cada suceso
        ax.step(xs, ys, where="post", color=col, label=f"{c} puestos")
    ax.set_xlim(185, 0)
    ax.set_xlabel("Minutos antes de la salida del vuelo")
    ax.set_ylabel("Personas en la fila")
    ax.set_title("Evolución de la fila en una réplica (misma demanda, réplica 1)")
    ax.legend(loc="upper left")
    marcar_horario(ax)
    fig.tight_layout(); fig.savefig("figuras/fig3_cola_en_el_tiempo.png"); plt.close(fig)


def fig_web(resumen):
    # Gráfico 4: cómo baja la espera a medida que más pasajeros hacen el
    # check-in web (0 %, 20 %, 40 %, 60 %), para 3 y 4 puestos.
    d = {f["escenario"]: f for f in resumen}
    ws = [0, 20, 40, 60]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    for c, col in [(3, NARANJA), (4, AZUL)]:
        y = [d[f"E3_c{c}_web{w}"]["espera_media"] for w in ws]
        e = [d[f"E3_c{c}_web{w}"]["espera_media_ic95"] for w in ws]
        ax.errorbar(ws, y, yerr=e, color=col, marker="o", ms=7, capsize=4, label=f"{c} puestos")
        ax.annotate(f"{c} puestos", (ws[-1], y[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", color=TINTA, fontsize=9)
    ax.set_xticks(ws); ax.set_xticklabels([f"{w} %" for w in ws])
    ax.set_xlim(-5, 72)
    ax.set_xlabel("Pasajeros con check-in web realizado")
    ax.set_ylabel("Espera media (min)"); ax.set_ylim(bottom=0)
    ax.set_title("Efecto de la adopción del check-in web (IC 95 %)")
    ax.legend(loc="upper right")
    fig.tight_layout(); fig.savefig("figuras/fig4_checkin_web.png"); plt.close(fig)


def fig_politicas(resumen):
    # Gráfico 5: compara distintas formas de organizar la apertura de puestos
    # y el tipo de fila. Son dos gráficos de barras horizontales lado a lado:
    # a la izquierda la espera media, a la derecha la fila más larga.
    d = {f["escenario"]: f for f in resumen}
    # Escenarios a mostrar
    filas = [("E4_4a120", "4 puestos desde 120' (base)"),
             ("E4_4a150", "4 puestos desde 150'"),
             ("E4_2a150_2a120", "2 desde 150' + 2 desde 120'"),
             ("E4_2a150_3a120", "2 desde 150' + 3 desde 120'"),
             ("E2_c4_multiple", "4 puestos, una fila por puesto")]
    fig, axs = plt.subplots(1, 2, figsize=(8.5, 3.6), sharey=True)
    for ax, m, tit in [(axs[0], "espera_total_media", "Espera media desde la llegada (min)"),
                       (axs[1], "lq_max", "Fila máxima (personas)")]:
        # Valores y márgenes de error de cada escenario
        y = [d[k][m] for k, _ in filas]; e = [d[k][m + "_ic95"] for k, _ in filas]
        pos = list(range(len(filas)))[::-1]
        ax.barh(pos, y, xerr=e, color=AZUL, height=0.6, capsize=3,
                error_kw={"ecolor": TINTA2, "lw": 1})
        for p_, v, err in zip(pos, y, e):
            ax.text(v + err, p_, f"  {v:.1f}", va="center", ha="left", color=TINTA, fontsize=9)
        ax.set_title(tit, fontsize=10.5); ax.grid(axis="y", visible=False)
        ax.set_xlim(0, max(y) * 1.3)
    axs[0].set_yticks(list(range(len(filas)))[::-1]); axs[0].set_yticklabels([l for _, l in filas])
    fig.suptitle("Políticas de apertura y disciplina de cola", x=0.01, ha="left",
                 fontweight="bold")
    fig.tight_layout(); fig.savefig("figuras/fig5_politicas.png"); plt.close(fig)


if __name__ == "__main__":
    os.makedirs("resultados", exist_ok=True); os.makedirs("figuras", exist_ok=True)
    detalle, resumen, crudos = correr_todo()
    guardar_csv("resultados/replicas_detalle.csv", detalle)
    guardar_csv("resultados/resumen_escenarios.csv", resumen)
    comp = comparaciones_pareadas(crudos)
    guardar_csv("resultados/comparaciones_pareadas.csv", comp)
    print("\nComparaciones pareadas (A - B):")
    for f in comp:
        if f["metrica"] == "espera_media":
            print(f"  {f['A']:16s} - {f['B']:16s} = {f['dif_media_A_menos_B']:7.2f} ± {f['ic95']:.2f}"
                  f"  {'*' if f['significativa'] else 'n.s.'}  (desvío pareado {f['desvio_pareado']}"
                  f" vs indep. {f['desvio_si_independientes']})")
    rn = replicas_necesarias(crudos)
    guardar_csv("resultados/replicas_necesarias.csv", [rn])
    print("\nRéplicas necesarias:", rn)
    fig_llegadas(); fig_puestos(resumen); fig_cola_tiempo(); fig_web(resumen); fig_politicas(resumen)
    print("Figuras guardadas en figuras/")
