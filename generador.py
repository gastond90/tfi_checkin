# Generador de números pseudoaleatorios propio.
#
# Se implementa un generador congruencial MULTIPLICATIVO de Lehmer / Park-Miller
# ("estándar mínimo"):
#
#     X_i = (a * X_{i-1}) mod m,   a = 16807 = 7^5,   m = 2^31 - 1 (primo)
#     U_i = X_i / m  ∈ (0, 1)
#
#
# FLUJOS (streams): para que cada fuente de aleatoriedad del modelo (llegadas,
# atributos de pasajeros, tiempos de servicio) use su propia secuencia
# independiente, cada flujo arranca en un punto distinto del mismo ciclo,
# separado por SALTO valores. 
# Esto permite usar números aleatorios comunes entre escenarios.

# En resumen:
#   1) Se fabrican números "al azar" entre 0 y 1 con una fórmula propia. 
#      En realidad no son al azar de verdad: siguen
#      una receta fija, pero se ven y se comportan como si lo fueran.
#   2) Revisa con pruebas estadísticas que esos números realmente se
#      comporten como azar (que estén bien repartidos y no tengan patrones).

import math

# Constantes de la fórmula del generador.
# A es el "multiplicador": cada número nuevo se obtiene multiplicando el
# anterior por este valor.
A = 16807
# M es el "módulo": después de multiplicar, nos quedamos con el resto de
# dividir por este número. Así los valores nunca crecen sin límite.
M = 2**31 - 1
# Distancia (en cantidad de números) entre el punto de partida de un flujo y
# el siguiente. Así cada flujo usa su propio "tramo" de números sin pisarse.
SALTO = 2_000_000           # distancia entre flujos (≈1000 flujos sin solaparse)


class LCG:
    # Generador congruencial multiplicativo con soporte de flujos
    # Cada objeto LCG es un generador independiente que recuerda en qué número va.

    def __init__(self, semilla=12345, flujo=0):
        # Se ejecuta al crear un generador nuevo.
        # - semilla: número de arranque. Misma semilla = misma secuencia,
        #   lo cual permite repetir exactamente un experimento.
        # - flujo: qué "tramo" de la secuencia usar (0, 1, 2, ...).

        # La semilla tiene que ser mayor que 0 y menor que M;
        if not (0 < semilla < M):
            raise ValueError("la semilla debe estar en (0, m)")
        
        # Se calcula directamente dónde arranca este flujo sin tener que generar
        # todos los números intermedios.
        # salto de flujo:
        self.x = (pow(A, flujo * SALTO, M) * semilla) % M

        # Se guardan la semilla y el flujo
        self.semilla = semilla
        self.flujo = flujo

    def random(self):
        # Devuelve U ~ U(0,1) (nunca 0 ni 1).
        # Paso de la receta: multiplicar el número actual por A
        self.x = (A * self.x) % M
        # dividir por M para que quede entre 0 y 1
        return self.x / M

    def muestra(self, n):
        # Devuelve una lista con n números al azar seguidos
        return [self.random() for _ in range(n)]


# Pruebas estadísticas sobre la secuencia
# Las siguientes funciones verifican que los números generados se comporten
# como azar real. Cada prueba devuelve:
#   - el valor calculado de la prueba (estadistico),
#   - el p-valor: cuanto más chico, más sospechoso es el resultado,
#   - si se rechaza la hipótesis de que los números son buenos
#     (cuando el p-valor es menor que alfa = 5 %).

from scipy import stats

def prueba_promedios(u, alfa=0.05):
    # H0: E[U] = 1/2. Estadístico Z = (ū - 1/2) / sqrt(1/(12 n)).
    # Si los números están bien repartidos entre 0 y 1, su promedio debería
    # dar muy cerca de 0,5. Esta prueba mide qué tan lejos de 0,5 quedó.

    # Cantidad de números
    n = len(u)
    # Promedio de los números
    media = sum(u) / n
    # Distancia entre el promedio y 0,5, en relación a lo que
    # sería esperable que se aleje solo por casualidad
    z = (media - 0.5) / math.sqrt(1 / (12 * n))
    # Probabilidad de obtener una diferencia así de grande por pura casualidad
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    return {"prueba": "Promedios", "estadistico": z, "p_valor": p,
            "rechaza_H0": p < alfa}


def prueba_chi2(u, k=10, alfa=0.05):
    # Frecuencias en k intervalos iguales. H0: uniformidad.
    # Se divide el rango de 0 a 1 en k cajones iguales y se cuenta cuántos números caen en cada uno.
    # Si el generador es bueno todos los cajones deberían tener más o menos la misma cantidad.

    n = len(u)
    # Contador de números por cajón, todos empiezan en cero
    obs = [0] * k
    for x in u:
        # Se calcula a qué cajón pertenece el número y se le suma uno
        obs[min(int(x * k), k - 1)] += 1
    # Cantidad esperada en cada cajón si todo fuera perfectamente parejo
    esp = n / k
    # Se suma qué tan lejos está cada cajón de lo esperado
    chi2 = sum((o - esp) ** 2 / esp for o in obs)
    # Probabilidad de ver diferencias así de grandes por casualidad
    p = 1 - stats.chi2.cdf(chi2, k - 1)
    return {"prueba": f"Chi-cuadrado (k={k})", "estadistico": chi2,
            "p_valor": p, "rechaza_H0": p < alfa}


def prueba_ks(u, alfa=0.05):
    # Kolmogorov-Smirnov contra U(0,1): D = max |F_n(x) - x|.
    # Se ordenen los números de menor a mayor y se compara cómo se van
    # acumulando contra cómo deberían acumularse si fueran perfectamente
    # parejos. Se elige la mayor diferencia encontrada (D).

    n = len(u)
    # Números ordenados de menor a mayor
    s = sorted(u)
    # Mayor diferencia por arriba entre lo observado y lo ideal
    d_mas = max((i + 1) / n - s[i] for i in range(n))
    # Mayor diferencia por abajo
    d_menos = max(s[i] - i / n for i in range(n))
    # La peor de las dos
    d = max(d_mas, d_menos)
    # Probabilidad de que una diferencia así aparezca por casualidad
    p = stats.kstwo.sf(d, n)
    return {"prueba": "Kolmogorov-Smirnov", "estadistico": d, "p_valor": p,
            "rechaza_H0": p < alfa}


def prueba_series(u, k=5, alfa=0.05):
    # Pares no solapados (u_2i, u_2i+1) en una grilla k×k. H0: independencia.
    # Esta prueba busca patrones entre números consecutivos. Toma los
    # números de a pares y los ubica en una
    # grilla de k×k casilleros. Si no hay relación entre
    # un número y el siguiente, todos los casilleros deberían llenarse parejo.

    # Pares: (posiciones pares, posiciones impares)
    pares = list(zip(u[0::2], u[1::2]))
    n = len(pares)
    # Tablero de k×k casilleros, todos en cero
    obs = [[0] * k for _ in range(k)]
    for a, b in pares:
        # El primer número indica la fila y el segundo la columna
        obs[min(int(a * k), k - 1)][min(int(b * k), k - 1)] += 1
    # Cantidad esperada por casillero si todo fuera parejo
    esp = n / k**2
    # Qué tan lejos está cada casillero de lo esperado, sumado
    chi2 = sum((o - esp) ** 2 / esp for fila in obs for o in fila)
    p = 1 - stats.chi2.cdf(chi2, k**2 - 1)
    return {"prueba": f"Series ({k}x{k})", "estadistico": chi2, "p_valor": p,
            "rechaza_H0": p < alfa}


def bateria(u, alfa=0.05):
    # Corre las cuatro pruebas juntas sobre la misma lista de números
    # y devuelve todos los resultados
    return [prueba_promedios(u, alfa), prueba_chi2(u, 10, alfa),
            prueba_ks(u, alfa), prueba_series(u, 5, alfa)]

if __name__ == "__main__":
    import csv, os
    os.makedirs("resultados", exist_ok=True)
    filas = []
    # Se prueban los tres flujos que usa el modelo (uno para cada tipo de azar)
    for flujo, nombre in [(0, "llegadas"), (1, "atributos"), (2, "servicio")]:
        # generador de ese flujo
        g = LCG(semilla=12345, flujo=flujo)
        # 10.000 números al azar
        u = g.muestra(10_000)
        # se les aplican todas las pruebas
        for r in bateria(u):
            # se agrega al resultado el nombre del flujo probado
            r = {"flujo": f"{flujo} ({nombre})", **r}
            filas.append(r)
            # resultado en pantalla
            print(f"{r['flujo']:15s} {r['prueba']:22s} est={r['estadistico']:9.4f}"
                  f"  p={r['p_valor']:.4f}  {'RECHAZA' if r['rechaza_H0'] else 'no rechaza'} H0")
            
    # Se comprueba que dos flujos distintos no estén relacionados entre sí
    # correlación entre flujos (deben ser independientes)
    g0, g2 = LCG(12345, 0).muestra(10_000), LCG(12345, 2).muestra(10_000)
    # r cerca de 0 significa que no hay relación entre ambos flujos
    r, p = stats.pearsonr(g0, g2)
    print(f"Correlación flujo 0 vs flujo 2: r={r:.4f} (p={p:.3f})")

    with open("resultados/pruebas_generador.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=filas[0].keys())
        w.writeheader(); w.writerows(filas)
