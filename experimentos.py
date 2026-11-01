"""
Escenarios, réplicas y análisis de resultados.

Cada escenario se corre R veces (réplicas = vuelos distintos). Para cada
indicador se informa la media y el intervalo de confianza del 95 %.

Salida: carpeta resultados/ (CSV) y figuras/ (PNG).
"""
# Este es el archivo que se ejecuta para obtener los resultados del trabajo.
# Define una serie de "escenarios" (qué pasa con 3, 4, 5 o 6 puestos,
# si más gente hace check-in web, etc.), simula cada uno muchas veces,
# resume los resultados y genera tablas (CSV) y gráficos (PNG).

import csv, math, os, statistics as st
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from modelo import con, correr_replica, generar_pasajeros, HORIZONTE, PARAMETROS_BASE

# Cuántos vuelos se simulan por escenario. Más repeticiones = resultados más
# confiables, pero tarda más.
R = 100                      # réplicas por escenario
# Indicadores que se calculan para cada escenario (están explicados en modelo.correr_replica)
INDICADORES = ["espera_media", "espera_p95", "pct_espera_15", "fila_max",
               "utilizacion", "en_fila_al_cierre", "fin_antes_salida",
               "pasajeros", "rechazados"]

# ---------------------------------------------------------------------------
# Escenarios: en cada experimento se cambia UNA cosa respecto de la base
# (4 puestos, apertura 120 min antes, 20 % de check-in web)
# ---------------------------------------------------------------------------
# Cada escenario tiene un nombre y una configuración base 
# y cambia solo lo indicado entre paréntesis.
ESCENARIOS = {
    # E1 — cantidad de puestos
    "E1_3_puestos": con(puestos=3),
    "E1_4_puestos": con(puestos=4),
    "E1_5_puestos": con(puestos=5),
    "E1_6_puestos": con(puestos=6),

    # E2 — check-in web, con 3 puestos
    # (0 %, 20 %, 40 % y 60 % de los pasajeros con check-in web hecho)
    "E2_web_0": con(puestos=3, p_web=0.0),
    "E2_web_20": con(puestos=3, p_web=0.2),
    "E2_web_40": con(puestos=3, p_web=0.4),
    "E2_web_60": con(puestos=3, p_web=0.6),

    # E3 — horario de apertura, con 4 puestos
    # ¿Qué pasa si se abre antes, o si algunos puestos abren antes que otros?
    "E3_4_desde_120": con(),
    "E3_4_desde_150": con(apertura_antes=150.0),
    "E3_2_desde_150_y_2_desde_120": con(aperturas=[150, 150, 120, 120]),

    # E4 — sensibilidad a los tiempos de atención (4 puestos)
    # ¿Cuánto cambian los resultados si la atención es un 20 % más rápida
    # o más lenta de lo supuesto?
    "E4_atencion_menos_20": con(factor_servicio=0.8),
    "E4_atencion_base": con(),
    "E4_atencion_mas_20": con(factor_servicio=1.2),
}


def intervalo95(xs):
    # Media y semiancho del intervalo de confianza del 95 % (t de Student).
    # Dado un conjunto de resultados, devuelve el promedio y el margen de error. 
    # El valor real está entre media − semiancho y media + semiancho, con 95 % de seguridad.
    n = len(xs)
    media = st.mean(xs)
    semiancho = stats.t.ppf(0.975, n - 1) * st.stdev(xs) / math.sqrt(n)
    return media, semiancho


def correr_todo():
    # Simula todos los escenarios, R vuelos cada uno, y arma dos tablas:
    # - detalle: una fila por cada vuelo simulado de cada escenario
    # - resumen: una fila por escenario, con promedios y márgenes de error

    detalle, resumen = [], []
    for nombre, p in ESCENARIOS.items():
        # Simulación de los R vuelos del escenario
        reps = [correr_replica(p, r) for r in range(R)]

        # se guarda cada vuelo en el detalle
        for x in reps:
            detalle.append({"escenario": nombre, **{k: v for k, v in x.items() if k != "_traza"}})

        # Promedio y margen de error para cada indicador
        fila = {"escenario": nombre}
        for ind in INDICADORES:
            media, h = intervalo95([x[ind] for x in reps])
            fila[ind] = round(media, 2)
            fila[ind + "_ic95"] = round(h, 2)
        resumen.append(fila)

        # Resumen en pantalla
        print(f"{nombre:30s} espera={fila['espera_media']:5.1f} ±{fila['espera_media_ic95']:.1f}  "
              f"p95={fila['espera_p95']:5.1f}  %>15={fila['pct_espera_15']:5.1f}  "
              f"fila_max={fila['fila_max']:5.1f}  util={fila['utilizacion']:5.1f}  "
              f"en_fila_al_cierre={fila['en_fila_al_cierre']:4.1f}")
    return detalle, resumen


def guardar_csv(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=filas[0].keys())
        w.writeheader(); w.writerows(filas)


# Gráficos
AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
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
AP = PARAMETROS_BASE["apertura_antes"]; CI = PARAMETROS_BASE["cierre_antes"]


def marcar_horario(ax):
    for x, txt in [(AP, " apertura"), (CI, " cierre")]:
        ax.axvline(x, color=TINTA2, lw=1, ls="--")
        ax.text(x, ax.get_ylim()[1], txt, va="top", ha="left", color=TINTA2, fontsize=9)


def fig_llegadas():
    antes = []
    for r in range(R):
        antes += [HORIZONTE - p["llegada"] for p in generar_pasajeros(con(), r)]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.hist(antes, bins=range(30, 185, 5), color=AZUL, edgecolor=FONDO, linewidth=1.5,
            weights=[1 / R] * len(antes))
    ax.set_xlim(185, 25)                     # el tiempo avanza hacia la derecha
    ax.set_xlabel("Minutos antes de la salida del vuelo")
    ax.set_ylabel("Pasajeros cada 5 minutos")
    ax.set_title(f"Llegada de pasajeros al mostrador (promedio de {R} vuelos)")
    marcar_horario(ax)
    fig.tight_layout(); fig.savefig("figuras/fig1_llegadas.png"); plt.close(fig)


def fig_puestos(resumen):
    d = {f["escenario"]: f for f in resumen}
    cs = [3, 4, 5, 6]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    for ind, col, lab in [("espera_media", AZUL, "Espera media"),
                          ("espera_p95", NARANJA, "Espera del 5 % que más espera (percentil 95)")]:
        y = [d[f"E1_{c}_puestos"][ind] for c in cs]
        e = [d[f"E1_{c}_puestos"][ind + "_ic95"] for c in cs]
        ax.errorbar(cs, y, yerr=e, color=col, marker="o", ms=7, capsize=4, label=lab)
        for c, v in zip(cs, y):
            ax.annotate(f"{v:.1f}", (c, v), textcoords="offset points", xytext=(8, 5),
                        color=TINTA, fontsize=9)
    ax.set_xticks(cs); ax.set_xlabel("Puestos de check-in abiertos")
    ax.set_ylabel("Minutos de espera"); ax.set_ylim(0, 48)
    ax.set_title("Más puestos bajan la espera media, pero no la de los que llegan temprano")
    ax.legend(loc="lower left")
    fig.tight_layout(); fig.savefig("figuras/fig2_espera_vs_puestos.png"); plt.close(fig)


def fig_fila_en_el_tiempo():
    fig, ax = plt.subplots(figsize=(7, 3.8))
    for c, col in [(3, NARANJA), (4, AZUL), (5, AQUA)]:
        tr = correr_replica(con(puestos=c), 0, registrar_traza=True)["_traza"]
        ax.step([HORIZONTE - t for t, _ in tr], [q for _, q in tr], where="post",
                color=col, label=f"{c} puestos")
    ax.set_xlim(185, 0)
    ax.set_xlabel("Minutos antes de la salida del vuelo")
    ax.set_ylabel("Personas en la fila")
    ax.set_title("La fila se arma antes de que abra el check-in (un mismo vuelo)")
    ax.legend(loc="upper left")
    marcar_horario(ax)
    fig.tight_layout(); fig.savefig("figuras/fig3_fila_en_el_tiempo.png"); plt.close(fig)


def fig_web(resumen):
    d = {f["escenario"]: f for f in resumen}
    ws = [0, 20, 40, 60]
    y = [d[f"E2_web_{w}"]["espera_media"] for w in ws]
    e = [d[f"E2_web_{w}"]["espera_media_ic95"] for w in ws]
    ref = d["E1_4_puestos"]["espera_media"]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.errorbar(ws, y, yerr=e, color=AZUL, marker="o", ms=7, capsize=4)
    for w, v in zip(ws, y):
        ax.annotate(f"{v:.1f}", (w, v), textcoords="offset points", xytext=(8, 5),
                    color=TINTA, fontsize=9)
    ax.axhline(ref, color=TINTA2, lw=1, ls=":")
    ax.text(-4, ref - 0.6, f"referencia: 4 puestos con 20 % web = {ref:.1f} min", va="top", ha="left",
            color=TINTA2, fontsize=9)
    ax.set_xticks(ws); ax.set_xticklabels([f"{w} %" for w in ws]); ax.set_xlim(-5, 65)
    ax.set_xlabel("Pasajeros con check-in web hecho")
    ax.set_ylabel("Espera media (min)"); ax.set_ylim(bottom=0)
    ax.set_title("Con 3 puestos, el check-in web baja la espera")
    fig.tight_layout(); fig.savefig("figuras/fig4_checkin_web.png"); plt.close(fig)


def fig_apertura(resumen):
    d = {f["escenario"]: f for f in resumen}
    casos = [("E3_4_desde_120", "4 puestos desde 120'\n(base)"),
             ("E3_4_desde_150", "4 puestos desde 150'"),
             ("E3_2_desde_150_y_2_desde_120", "2 desde 150'\n+ 2 desde 120'")]
    fig, axs = plt.subplots(1, 2, figsize=(8.5, 3.4), sharey=True)
    for ax, ind, tit in [(axs[0], "espera_media", "Espera media (min)"),
                         (axs[1], "fila_max", "Fila máxima (personas)")]:
        y = [d[k][ind] for k, _ in casos]; e = [d[k][ind + "_ic95"] for k, _ in casos]
        pos = [2, 1, 0]
        ax.barh(pos, y, xerr=e, color=AZUL, height=0.6, capsize=3,
                error_kw={"ecolor": TINTA2, "lw": 1})
        for p_, v, err in zip(pos, y, e):
            ax.text(v + err, p_, f"  {v:.1f}", va="center", ha="left", color=TINTA, fontsize=9)
        ax.set_title(tit, fontsize=10.5); ax.grid(axis="y", visible=False)
        ax.set_xlim(0, max(y) * 1.3)
    axs[0].set_yticks([2, 1, 0]); axs[0].set_yticklabels([l for _, l in casos])
    fig.suptitle("Abrir antes, aunque sea con 2 puestos, casi elimina la espera",
                 x=0.01, ha="left", fontweight="bold")
    fig.tight_layout(); fig.savefig("figuras/fig5_apertura.png"); plt.close(fig)

if __name__ == "__main__":
    os.makedirs("resultados", exist_ok=True); os.makedirs("figuras", exist_ok=True)
    detalle, resumen = correr_todo()
    guardar_csv("resultados/replicas_detalle.csv", detalle)
    guardar_csv("resultados/resumen_escenarios.csv", resumen)
    fig_llegadas(); fig_puestos(resumen); fig_fila_en_el_tiempo()
    fig_web(resumen); fig_apertura(resumen)
    print("Listo: resultados/ y figuras/")
