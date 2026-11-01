"""
validacion.py — Verificación y validación del motor de simulación.

Se usa EL MISMO motor (modelo.simular) en un caso donde existe solución
analítica: la cola M/M/c en estado estacionario (fórmula de Erlang C).
Si el motor está bien implementado, la espera media simulada debe coincidir
con la teórica dentro del intervalo de confianza. Además se verifica la
ley de Little (Lq = λ·Wq).
"""
# ¿Para qué sirve este archivo? Para comprobar que nuestro simulador
# funciona bien. Existe un tipo de fila "de libro" (llegadas totalmente al
# azar, atención totalmente al azar, c puestos) para la cual hay fórmulas
# exactas que dicen cuánto se espera en promedio. Entonces:
#   1) calculamos la espera con la fórmula,
#   2) simulamos esa misma fila con nuestro simulador,
#   3) comparamos. Si dan parecido, el simulador está bien hecho.

# Herramientas estándar: archivos CSV, matemática, carpetas y estadística básica
import csv, math, os, statistics as st
# Tablas estadísticas (para calcular el margen de error)
from scipy import stats

# Nuestro generador de números al azar
from generador import LCG
# Nuestras funciones para sortear tiempos, cantidades, etc.
import variables as va
# El motor de simulación que queremos verificar
from modelo import simular


def erlang_c(lam, mu, c):
    # Calcula con fórmulas exactas cómo debería comportarse la fila.
    # - lam: cuántas personas llegan por minuto, en promedio
    # - mu: cuántas personas atiende un puesto por minuto, en promedio
    # - c: cantidad de puestos

    # Cuántos puestos "harían falta" en promedio para atender a todos
    a = lam / mu                    # carga ofrecida
    # Qué tan ocupado está cada puesto (de 0 a 1; 0,8 = ocupado el 80 % del tiempo)
    rho = a / c
    # Partes de la fórmula de Erlang C (fórmula clásica de teoría de colas)
    suma = sum(a**k / math.factorial(k) for k in range(c))
    ultimo = a**c / (math.factorial(c) * (1 - rho))
    # Probabilidad de que una persona que llega tenga que esperar
    p_espera = ultimo / (suma + ultimo)
    # Tiempo promedio de espera en la fila
    wq = p_espera / (c * mu - lam)
    # Devolvemos todo junto. Lq es la cantidad promedio de personas en la
    # fila (por la "ley de Little": personas en fila = llegadas × espera)
    return {"rho": rho, "p_espera": p_espera, "Wq": wq, "Lq": lam * wq}


def replica_mmc(lam, mu, c, n, calentamiento, replica):
    # Simula UNA vez la fila "de libro" con nuestro motor y devuelve la
    # espera promedio y el largo promedio de la fila.
    # - n: cuántas personas simular
    # - calentamiento: cuántas de las primeras personas ignorar (al principio
    #   la fila arranca vacía y no es representativa)
    # - replica: número de repetición (para usar números al azar distintos)

    # Un generador para las llegadas y otro para los tiempos de atención.
    # Usamos flujos altos (900 en adelante) para no mezclarlos con los del modelo.
    g_a = LCG(777, 900 + 2 * replica)
    g_s = LCG(777, 901 + 2 * replica)
    # t es el reloj; pax es la lista de pasajeros que vamos creando
    t, pax = 0.0, []
    for _ in range(n):
        # El siguiente llega un rato después del anterior (tiempo al azar)
        t += va.exponencial(g_a, 1 / lam)
        # Guardamos cuándo llega y cuánto tardará en ser atendido
        pax.append({"llegada": t, "servicio": va.exponencial(g_s, 1 / mu)})
    # Corremos la simulación: c puestos, todos abiertos desde el minuto 0, fila única
    r = simular(pax, [0.0] * c, "unica")
    # Ordenamos a los atendidos por hora de llegada y descartamos los primeros
    at = sorted(r["atendidos"], key=lambda x: x["llegada"])[calentamiento:]
    # Espera promedio = (hora en que lo empezaron a atender − hora en que llegó)
    wq = st.mean(x["inicio"] - x["llegada"] for x in at)
    # Largo promedio de la fila a lo largo del tiempo
    lq_tiempo = r["area_lq"] / r["t_fin"]
    return wq, lq_tiempo


def ic95(xs):
    # Dado un conjunto de resultados, calcula el promedio (m) y el margen de
    # error (h) con 95 % de confianza. O sea: "el valor real está entre
    # m − h y m + h" con 95 % de seguridad.
    n = len(xs); m = st.mean(xs); s = st.stdev(xs)
    h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    return m, h


# Este bloque solo se ejecuta al correr este archivo directamente
if __name__ == "__main__":
    # Creamos la carpeta de resultados si no existe
    os.makedirs("resultados", exist_ok=True)
    # Los casos a probar: (nombre, llegadas por minuto, atenciones por minuto, puestos)
    casos = [("M/M/1", 0.8, 1.0, 1), ("M/M/3", 1.2, 0.5, 3),
             ("M/M/4", 1.6, 0.5, 4), ("M/M/4 (ρ=0,9)", 1.8, 0.5, 4)]
    # R = repeticiones por caso, N = personas por repetición,
    # CAL = personas iniciales que se descartan
    R, N, CAL = 20, 40_000, 4_000
    filas = []
    for nombre, lam, mu, c in casos:
        # Resultado según la fórmula exacta
        teo = erlang_c(lam, mu, c)
        # Resultado según la simulación, repetida R veces
        res = [replica_mmc(lam, mu, c, N, CAL, r) for r in range(R)]
        # Promedio y margen de error de la espera simulada
        wq, hw = ic95([x[0] for x in res])
        # Promedio y margen de error del largo de fila simulado
        lq, hl = ic95([x[1] for x in res])
        # ¿El valor teórico cae dentro del margen de error de la simulación?
        dentro = abs(wq - teo["Wq"]) <= hw
        # Diferencia porcentual entre simulación y teoría
        error = 100 * (wq - teo["Wq"]) / teo["Wq"]
        # Guardamos una fila con todos los datos del caso
        filas.append({"modelo": nombre, "lambda": lam, "mu": mu, "c": c,
                      "rho": round(teo["rho"], 3),
                      "Wq_teorico": round(teo["Wq"], 4),
                      "Wq_simulado": round(wq, 4), "IC95_Wq": round(hw, 4),
                      "error_pct": round(error, 2),
                      "teorico_dentro_IC": dentro,
                      "Lq_teorico": round(teo["Lq"], 4),
                      "Lq_simulado": round(lq, 4),
                      "Little_lambda_Wq": round(lam * wq, 4)})
        # Mostramos el resumen del caso en pantalla
        print(f"{nombre:14s} ρ={teo['rho']:.2f}  Wq teo={teo['Wq']:.3f}  "
              f"sim={wq:.3f} ± {hw:.3f} ({error:+.1f}%)  "
              f"{'✓ dentro del IC' if dentro else '✗ fuera del IC'}  |  "
              f"Lq sim={lq:.3f}  λ·Wq={lam*wq:.3f}  teo={teo['Lq']:.3f}")
    # Guardamos todos los casos en un archivo CSV
    with open("resultados/validacion_mmc.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=filas[0].keys())
        w.writeheader(); w.writerows(filas)
