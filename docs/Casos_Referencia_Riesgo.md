# Casos de referencia del riesgo académico

Este documento responde a la pregunta «¿el sistema clasifica bien?», no solo «¿el sistema responde?». Cada caso es un estudiante ficticio con el resultado que **debe** obtenerse, calculado a mano antes de ejecutar el sistema. La prueba automática `BACKEND/alertas_tempranas_ufps/alertas/tests_casos_referencia.py` compara esos resultados con el cálculo real en cada pull request; las tablas de este documento se generan a partir de esa misma prueba.

**Resultado al 16/11/2026: los 45 casos coinciden con el sistema.**

**Estado de la validación académica: pendiente.** Los umbrales y los resultados esperados los definió el equipo de desarrollo. Falta el visto bueno de la dirección del programa o de un docente; ver la sección 7.

## 1. Reglas generales de riesgo

Son las que carga el comando `reset_reglas`. El nivel del estudiante es el más alto entre las reglas que se cumplen. Si ninguna se cumple, el nivel es Bajo. Sin notas y sin promedio, el nivel es «Sin datos»: no se asume riesgo ni ausencia de riesgo.

| Regla | Indicador | Condición | Nivel |
| --- | --- | --- | --- |
| Promedio Crítico | Promedio acumulado (PPA) | < 2,5 | Alto |
| Promedio Bajo | Promedio acumulado (PPA) | < 3,0 | Medio |
| Promedio En Riesgo | Promedio acumulado (PPA) | < 3,5 | Bajo |
| Múltiples Reprobadas Crítico | Materias reprobadas pendientes | >= 4 | Alto |
| Reprobadas Moderado | Materias reprobadas pendientes | >= 2 | Medio |
| Una Reprobada | Materias reprobadas pendientes | >= 1 | Bajo |
| Atraso Severo | Materias de línea atrasadas | >= 3 | Alto |
| Atraso Moderado | Materias de línea atrasadas | >= 2 | Medio |
| Atraso Leve | Materias de línea atrasadas | >= 1 | Bajo |

Definiciones:

- **PPA:** suma de (definitiva × créditos) entre la suma de créditos, con las materias que tienen definitiva. Dos decimales.
- **Reprobadas pendientes:** materias perdidas que el estudiante aún no ha aprobado, ni directamente ni por una materia equivalente. Una materia perdida varias veces cuenta una vez.
- **Atraso:** materias de tipo «línea» de semestres anteriores al semestre del estudiante que no ha aprobado. Las materias de otros tipos no cuentan.

## 2. Casos de riesgo general

Pensum de referencia, todas las materias de 3 créditos: L11 y L12 (línea, semestre 1), L21 y L22 (línea, semestre 2), L31 (línea, semestre 3), P11 (profesional, semestre 1) y E11 (equivalente a L11). Todos los estudiantes están en tercer semestre.

| Caso | Situación | Notas (materia: definitiva) | PPA | Reprobadas | Atraso | Nivel | Reglas que aplican |
| --- | --- | --- | :---: | :---: | :---: | :---: | --- |
| R01 | Buen rendimiento | L11: 4,0, L12: 4,0, L21: 4,0, L22: 4,0 | 4,0 | 0 | 0 | Bajo | ninguna |
| R02 | Promedio 3.40: por debajo de 3.5 | L11: 3,4, L12: 3,4, L21: 3,4, L22: 3,4 | 3,4 | 0 | 0 | Bajo | Promedio En Riesgo |
| R03 | Límite: promedio exactamente 3.50 no dispara la regla | L11: 3,5, L12: 3,5, L21: 3,5, L22: 3,5 | 3,5 | 0 | 0 | Bajo | ninguna |
| R04 | Promedio 2.95 con una materia de línea perdida | L11: 3,0, L12: 3,0, L21: 2,8, L22: 3,0 | 2,95 | 1 | 1 | Medio | Promedio Bajo, Promedio En Riesgo, Una Reprobada, Atraso Leve |
| R05 | Promedio 2.45, tres perdidas y tres materias de línea atrasadas | L11: 2,0, L12: 2,0, L21: 3,0, L22: 2,8 | 2,45 | 3 | 3 | Alto | Promedio Crítico, Promedio Bajo, Promedio En Riesgo, Reprobadas Moderado, Una Reprobada, Atraso Severo, Atraso Moderado, Atraso Leve |
| R06 | Sin historial y sin promedio: no hay datos | ninguna | — | — | — | Sin datos | ninguna |
| R07 | Sin historial, con promedio importado 2.40 | ninguna (promedio importado 2,4) | 2,4 | — | — | Alto | Promedio Crítico, Promedio Bajo, Promedio En Riesgo |
| R08 | Perdió L11 y la recuperó: ya no está pendiente | L11: 2,0, L11: 3,5, L12: 4,0, L21: 4,0, L22: 4,0 | 3,5 | 0 | 0 | Bajo | ninguna |
| R09 | No ha cursado las dos materias de línea de segundo semestre | L11: 4,0, L12: 4,0 | 4,0 | 0 | 2 | Medio | Atraso Moderado, Atraso Leve |
| R10 | Una materia que no es de línea sin cursar no cuenta como atraso | L11: 4,0, L12: 4,0, L21: 4,0, L22: 4,0 | 4,0 | 0 | 0 | Bajo | ninguna |
| R11 | Materia en curso sin definitiva: ni suma al promedio ni cuenta como perdida | L11: 4,0, L12: 4,0, L21: 4,0, L22: 4,0, L31: en curso | 4,0 | 0 | 0 | Bajo | ninguna |
| R12 | Perdió L11 y aprobó su equivalente E11 | L11: 2,0, E11: 4,0, L12: 4,0, L21: 4,0, L22: 4,0 | 3,6 | 0 | 0 | Bajo | ninguna |
| R13 | Cuatro materias perdidas con promedio 2.90 | L11: 2,9, L12: 2,9, L21: 2,9, L22: 2,9 | 2,9 | 4 | 4 | Alto | Promedio Bajo, Promedio En Riesgo, Múltiples Reprobadas Crítico, Reprobadas Moderado, Una Reprobada, Atraso Severo, Atraso Moderado, Atraso Leve |
| R14 | Buen promedio (3.70) con dos perdidas: el riesgo no depende solo del promedio | L11: 2,9, L12: 2,9, L21: 4,5, L22: 4,5 | 3,7 | 2 | 2 | Medio | Reprobadas Moderado, Una Reprobada, Atraso Moderado, Atraso Leve |

Cómo se calculó cada uno:

- **R02 y R03** fijan el límite de la regla de promedio: 3,40 la dispara y 3,50 exacto no, porque la condición es «menor que 3,5».
- **R04:** (3,0 + 3,0 + 2,8 + 3,0) / 4 = 2,95. Perdió L21, que es de línea y de un semestre anterior: una reprobada y una atrasada. El nivel Medio lo da el promedio.
- **R05:** (2,0 + 2,0 + 3,0 + 2,8) / 4 = 2,45. Tres perdidas, las tres de línea: atraso 3, que por sí solo ya es Alto.
- **R06 y R07** cubren los datos faltantes. Sin historial no se inventan reprobadas ni atraso; si existe un promedio importado, solo se evalúan las reglas de promedio.
- **R08:** las dos notas de L11 cuentan en el promedio, (2,0 + 3,5 + 4,0 + 4,0 + 4,0) / 5 = 3,50, pero la materia ya no está pendiente.
- **R09:** no perder materias no basta: no haber cursado dos materias de línea de un semestre anterior es atraso.
- **R10:** P11 no se ha cursado, pero no es de línea.
- **R11:** una materia en curso, sin definitiva, no baja el promedio ni cuenta como perdida.
- **R12:** aprobar la materia equivalente cubre la del pensum: (2,0 + 4,0 + 4,0 + 4,0 + 4,0) / 5 = 3,60.
- **R13:** cuatro perdidas con 2,9. El promedio daría Medio; las cuatro reprobadas lo suben a Alto.
- **R14:** promedio 3,70 y, aun así, nivel Medio por dos materias perdidas. El riesgo no depende solo del promedio.

**Datos que cambian.** El caso R04 recupera L21 con 3,5 en un periodo posterior: el promedio pasa a (3,0 + 3,0 + 2,8 + 3,0 + 3,5) / 5 = 3,06, sin reprobadas ni atraso, y el nivel baja de Medio a Bajo. El sistema lo recalcula con los datos nuevos.

## 3. Nota definitiva

Definitiva = promedio de los tres cortes × 0,7 + examen final × 0,3, con redondeo a un decimal (la mitad sube). Solo se calcula con las cuatro notas.

| Corte 1 | Corte 2 | Corte 3 | Examen | Definitiva esperada |
| :---: | :---: | :---: | :---: | :---: |
| 3,0 | 3,0 | 3,0 | 3,0 | 3,0 |
| 4,0 | 3,5 | 3,0 | 2,0 | 3,1 |
| 2,0 | 2,5 | 3,0 | 4,0 | 3,0 |
| 1,0 | 2,0 | 3,0 | 5,0 | 2,9 |
| 3,3 | 3,3 | 3,4 | 2,2 | 3,0 |
| 5,0 | 5,0 | 5,0 | 5,0 | 5,0 |
| 0,0 | 0,0 | 0,0 | 0,0 | 0,0 |

El tercer caso merece atención del programa: 2,95 se redondea a 3,0 y el estudiante aprueba.

## 4. Nota necesaria en el examen

Nota necesaria = (3,0 − promedio de los cortes × 0,7) / 0,3, con dos decimales.

| Corte 1 | Corte 2 | Corte 3 | Nota necesaria en el examen |
| :---: | :---: | :---: | :---: |
| 3,0 | 3,0 | 3,0 | 3,00 |
| 1,5 | 2,0 | 2,5 | 5,33 |
| 2,0 | 2,2 | 2,2 | 5,02 |
| 2,0 | 2,0 | 2,5 | 4,94 |
| 2,5 | 2,6 | 2,6 | 4,01 |
| 2,6 | 2,6 | 2,6 | 3,93 |
| 5,0 | 5,0 | 5,0 | -1,67 |

## 5. Alertas por corte

Solo se evalúan en el periodo más reciente. Las alertas de corte no cambian el nivel de riesgo del estudiante.

| Clave | Condición | Nivel |
| --- | --- | --- |
| C1 | Corte 1 menor que 2,0 | Medio |
| C2A | Corte 2 menor que 3,0 y corte 1 menor que 3,0 | Alto |
| C2B | Corte 2 menor que 3,0 y corte 1 de 3,0 o más (caída de rendimiento) | Bajo |
| C3 | Tres cortes y nota necesaria en el examen mayor que 4,0 | Alto |
| C4 | Tres cortes y nota necesaria mayor que 5,0 (materia perdida). Tiene prioridad sobre C3 | Alto |

| Caso | Corte 1 | Corte 2 | Corte 3 | Examen | Alertas abiertas esperadas |
| --- | :---: | :---: | :---: | :---: | --- |
| C01 | 1,9 | — | — | — | C1 |
| C02 | 2,0 | — | — | — | ninguna |
| C03 | 2,5 | 2,9 | — | — | C2A |
| C04 | 3,0 | 2,9 | — | — | C2B |
| C05 | 3,0 | 3,0 | — | — | ninguna |
| C06 | 1,5 | 2,0 | — | — | C1, C2A |
| C07 | 1,5 | 2,0 | 2,5 | — | C1, C2A, C4 |
| C08 | 2,0 | 2,5 | 2,5 | — | C2A, C3 |
| C09 | 2,6 | 2,6 | 2,6 | — | C2A |
| C10 | 3,5 | 3,5 | 3,5 | — | ninguna |
| C11 | 1,5 | 2,0 | 2,5 | 5,0 | C1, C2A |

Además se comprueba que evaluar dos veces la misma nota no duplica la alerta y que, si el corte 1 se corrige de 1,9 a 3,0, la alerta se cierra sola con `cierre_automatico` y su motivo.

## 6. Inasistencia

Porcentaje = faltas sin justificar / clases registradas × 100. Las faltas justificadas cuentan como clase, no como falta. El umbral general es 20 % y no se evalúa con menos de 4 clases registradas. La condición es «mayor que»: 20,00 % exacto no genera alerta.

| Caso | Asistió | Faltas | Justificadas | Clases | Porcentaje | ¿Supera el 20 %? |
| --- | :---: | :---: | :---: | :---: | :---: | --- |
| I01 | 7 | 2 | 1 | 10 | 20,00 | No |
| I02 | 11 | 3 | 0 | 14 | 21,43 | Sí |
| I03 | 0 | 0 | 0 | 0 | — | No se evalúa |
| I04 | 2 | 1 | 0 | 3 | 33,33 | No se evalúa |
| I05 | 2 | 0 | 2 | 4 | 0,00 | No |
| I06 | 3 | 1 | 0 | 4 | 25,00 | Sí |

## 7. Validación por el programa

Preguntas concretas para la dirección del programa o un docente:

1. ¿Los umbrales de promedio (2,5, 3,0 y 3,5) corresponden a lo que el programa considera riesgo alto, medio y bajo?
2. ¿Es correcto que un estudiante con promedio 3,70 y dos materias perdidas quede en riesgo Medio (R14)?
3. ¿Es correcto que no haber cursado materias de línea de semestres anteriores cuente como atraso aunque no se hayan perdido (R09)?
4. ¿El 20 % de inasistencia y el mínimo de 4 clases son los valores del reglamento?
5. ¿Está de acuerdo con que 2,95 se redondee a 3,0 y la materia se apruebe?

| Revisó | Cargo | Fecha | Observaciones |
| --- | --- | --- | --- |
| | | | |

## 8. Lo que estos casos no demuestran

- No miden si las alertas predicen la deserción o la pérdida de materias: para eso hacen falta datos históricos de varias cohortes.
- En producción las reglas activas pueden diferir de las de referencia; se consultan en la pantalla «Reglas de riesgo».
- El 16/11/2026 se corrigió en producción el tipo de 104 materias del pensum (SDAT-343). Antes de esa corrección ninguna materia de línea tenía semestre asignado y la regla de atraso no podía aplicarse bien. El cálculo no cambió; cambió el dato de entrada. Por eso el atraso depende de que el pensum esté bien tipificado.
- Que una solicitud de acompañamiento no se duplique y conserve su historial se verifica en `portal/tests_solicitudes.py` y `portal/tests_contrato.py`.
