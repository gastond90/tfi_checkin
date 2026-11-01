# TFI Modelos y Simulación — Check-in de un vuelo

Simulación de eventos discretos de los mostradores de check-in de un vuelo
de 180 asientos, para evaluar cuántos puestos abrir, cuándo abrirlos, qué
disciplina de cola usar y el efecto del check-in web.

## Requisitos
Python 3.10+ con `scipy` y `matplotlib` (`pip install scipy matplotlib`).
El generador de números aleatorios y las variables aleatorias son propios;
`scipy` solo se usa para valores críticos y p-valores.

## Cómo reproducir
```bash
python generador.py      # pruebas del generador  → resultados/pruebas_generador.csv
python validacion.py     # validación vs. M/M/c   → resultados/validacion_mmc.csv
python experimentos.py   # escenarios + gráficos  → resultados/*.csv, figuras/*.png
```
Los resultados son reproducibles: misma semilla (12345) → mismos números.

## Archivos
| Archivo | Contenido | Unidad |
|---|---|---|
| `generador.py` | Generador congruencial multiplicativo (Park-Miller, a=16807, m=2³¹−1) con flujos independientes; pruebas de promedios, χ², Kolmogorov-Smirnov y series | 2 |
| `variables.py` | Transformada inversa (exponencial, triangular, discreta empírica), Box-Muller, aceptación-rechazo (normal truncada), binomial | 3 |
| `modelo.py` | Motor de simulación por planificación de eventos, reloj variable, cola única o múltiple | 1 y 4 |
| `validacion.py` | Comparación con la fórmula de Erlang C (M/M/c) y la ley de Little | 4 |
| `experimentos.py` | 26 escenarios × 100 réplicas, IC 95 %, comparaciones pareadas, cálculo de réplicas necesarias, gráficos | 4 |

## Supuestos principales (`PARAMETROS_BASE` en `modelo.py`)
- 180 asientos; cada uno se presenta con prob. 0,85 (Binomial).
- Anticipación de llegada ~ Normal(100, 25) min antes de la salida, truncada a [25, 180].
- Check-in abre 120 min antes y cierra 40 min antes; quien llega después del cierre es rechazado.
- 20 % hizo check-in web: si no lleva valija no pasa por el mostrador; si lleva, solo despacha.
- Valijas: 0 (30 %), 1 (55 %), 2 (15 %).
- Servicio (triangular, min): check-in completo (0,7; 1,2; 3,0); solo despacho (0,4; 0,7; 1,5); + (0,2; 0,4; 0,9) por valija.
