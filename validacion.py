# Verificación del motor de simulación.
#
# Se usa EL MISMO motor (modelo.simular) en un caso con solución teórica
# conocida: la cola M/M/1 (llegadas de Poisson, atención exponencial, un
# puesto). Para ese caso la espera media en la fila es:
#
#     Wq = ρ / (μ − λ),   con ρ = λ / μ
#
# Si el motor está bien programado, la espera simulada debe coincidir con la
# teórica dentro del intervalo de confianza.

# Este archivo comprueba que el simulador funciona bien.
#  Existe un tipo de fila "base" (un solo puesto, llegadas
# y atenciones totalmente al azar) para la cual hay una fórmula exacta que
# dice cuánto se espera en promedio. Entonces:
#   1) se calcula la espera con la fórmula,
#   2) se simula esa misma fila con el simulador,
#   3) se compara. Si dan parecido, el simulador está bien hecho.

import csv, math, os, statistics as st
from scipy import stats
from generador import LCG
import variables as va
from modelo import simular


R = 20            # réplicas por caso
N = 50_000        # clientes por réplica


def wq_teorica(lam, mu):
    # Calcula con la fórmula exacta la espera promedio en la fila.
    # - lam: cuántos clientes llegan por minuto, en promedio
    # - mu: cuántos clientes puede atender el puesto por minuto, en promedio

    # Qué tan ocupado está el puesto (0,8 = ocupado el 80 % del tiempo)
    rho = lam / mu
    # Fórmula de la espera promedio para este tipo de fila
    return rho / (mu - lam)


def replica_mm1(lam, mu, replica):
    # Simula UNA vez la fila "base" con el motor y devuelve la
    # espera promedio que salió.

    # Un generador para las llegadas y otro para los tiempos de atención.
    # Se usan flujos altos (900 en adelante) para no mezclarlos con los del modelo.
    g_lleg = LCG(777, 900 + 2 * replica)
    g_serv = LCG(777, 901 + 2 * replica)

    # t es el reloj, clientes es la lista que se va armando
    t, clientes = 0.0, []

    for _ in range(N):
        # El siguiente cliente llega un rato (al azar) después del anterior
        t += va.exponencial(g_lleg, 1 / lam)

        # se guarda cuándo llega y cuánto tardarán en atenderlo
        clientes.append({"llegada": t, "servicio": va.exponencial(g_serv, 1 / mu)})

    # Se corre la simulación con un solo puesto abierto desde el principio
    r = simular(clientes, [0.0])                     # un puesto, abierto desde t = 0

    # Espera promedio = (hora en que lo empezaron a atender − hora en que llegó)
    return st.mean(x["inicio"] - x["llegada"] for x in r["atendidos"])


if __name__ == "__main__":
    os.makedirs("resultados", exist_ok=True)
    filas = []
    # Se prueban tres casos, de menos a más cargado: el puesto ocupado
    # el 50 %, el 70 % y el 80 % del tiempo

    for lam, mu in [(0.5, 1.0), (0.7, 1.0), (0.8, 1.0)]:
        # Resultado según la fórmula
        teo = wq_teorica(lam, mu)

        # Resultado según la simulación, repetida R veces
        esperas = [replica_mm1(lam, mu, r) for r in range(R)]

        # Promedio de las repeticiones
        media = st.mean(esperas)

        # Margen de error con 95 % de confianza: 
        semiancho = stats.t.ppf(0.975, R - 1) * st.stdev(esperas) / math.sqrt(R)

        # El valor de la fórmula cae dentro del margen de la simulación?
        dentro = abs(media - teo) <= semiancho

        # Diferencia porcentual entre simulación y fórmula
        error = 100 * (media - teo) / teo

        # Se guarda una fila con todos los datos del caso
        filas.append({"lambda": lam, "mu": mu, "rho": lam / mu,
                      "Wq_teorica": round(teo, 3), "Wq_simulada": round(media, 3),
                      "IC95": round(semiancho, 3), "error_pct": round(error, 2),
                      "teorica_dentro_del_IC": dentro})
        
        # resultado del caso en pantalla
        print(f"ρ={lam/mu:.1f}  Wq teórica={teo:.3f}  simulada={media:.3f} ± {semiancho:.3f}"
              f"  ({error:+.1f} %)  {'✓ dentro del IC' if dentro else '✗ fuera del IC'}")
        
    # se guardan todos los casos en un archivo CSV
    with open("resultados/validacion_mm1.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=filas[0].keys())
        w.writeheader(); w.writerows(filas)
