# TFI Modelos y Simulación — Check-in de un vuelo

Simulación de eventos discretos de los mostradores de check-in de un vuelo
de 180 asientos, para evaluar cuántos puestos abrir, a qué hora abrirlos y el
efecto del check-in web.

## Requisitos
Python 3.10+ con `scipy` y `matplotlib`:
```
python -m pip install scipy matplotlib
```
El generador de números aleatorios y las variables aleatorias son propios;
`scipy` solo se usa para valores críticos y p-valores de las pruebas.

## Cómo reproducir (desde la carpeta tfi_checkin, en este orden)
```
python generador.py      # pruebas del generador  → resultados/pruebas_generador.csv
python validacion.py     # comparación con M/M/1  → resultados/validacion_mm1.csv
python experimentos.py   # escenarios + gráficos  → resultados/*.csv, figuras/*.png
```
`variables.py` y `modelo.py` no se ejecutan solos: los usan los otros.
La semilla es fija (12345), así que siempre se obtienen los mismos resultados.

## Archivos
| Archivo | Contenido | Unidad |
|---|---|---|
| `generador.py` | Generador congruencial multiplicativo (a = 16807, m = 2³¹−1) con flujos separados; pruebas de promedios, chi-cuadrado, Kolmogorov-Smirnov y series | 2 |
| `variables.py` | Transformada inversa: triangular, discreta empírica, exponencial, Bernoulli | 3 |
| `modelo.py` | Simulación por planificación de eventos, reloj variable, fila única | 1 y 4 |
| `validacion.py` | Comparación con la fórmula de la cola M/M/1 | 4 |
| `experimentos.py` | 14 escenarios × 100 réplicas, intervalos de confianza del 95 %, gráficos | 4 |

## Supuestos (`PARAMETROS_BASE` en `modelo.py`)
- 180 asientos; cada uno tiene pasajero con probabilidad 0,85.
- Llegada: triangular (30; 100; 180) minutos antes de la salida.
- Check-in abre 120 min antes y cierra 40 min antes; quien llega después del cierre no es aceptado.
- 20 % hizo check-in web: si no lleva valija no pasa por el mostrador; si lleva, solo despacha.
- Valijas: 0 (30 %), 1 (55 %), 2 (15 %).
- Atención (triangular, min): check-in completo (0,7; 1,2; 3,0); solo despacho (0,4; 0,7; 1,5); + (0,2; 0,4; 0,9) por valija.
