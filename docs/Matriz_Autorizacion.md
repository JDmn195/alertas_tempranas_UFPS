# Matriz de autorización por rol y ruta

Generada a partir de la tabla `MATRIZ` de `BACKEND/alertas_tempranas_ufps/pruebas_integracion/test_matriz_roles.py`, que la integración continua verifica en cada pull request.

La prueba recorre todas las rutas declaradas bajo `/api/` y comprueba, para cada una:

- sin sesión responde 401;
- un rol no permitido recibe 403 y el intento queda en auditoría como `ACCESO_DENEGADO`;
- un rol permitido no recibe 401 ni 403;
- una ruta nueva sin fila en la tabla hace fallar la prueba.

Convenciones: **Sí** = permitido; **—** = 403. «Pública» no pide sesión. «Cron» solo acepta el encabezado `X-Cron-Token`. «Sesión» acepta a cualquier usuario autenticado.

El acceso por objeto (un docente solo ve sus cursos, un estudiante solo sus datos) se verifica aparte; ver la última sección.

## /api/usuarios/

| Ruta | Admin. | Director | Bienestar | Docente | Estudiante |
| --- | :---: | :---: | :---: | :---: | :---: |
| `/api/usuarios/` | Sí | — | — | — | — |
| `/api/usuarios/auditoria/` | Sí | — | — | — | — |
| `/api/usuarios/cambiar-password/` | Pública | Pública | Pública | Pública | Pública |
| `/api/usuarios/crear/` | Sí | — | — | — | — |
| `/api/usuarios/estudiantes/{id}/cuenta/` | Sí | — | — | — | — |
| `/api/usuarios/login/` | Pública | Pública | Pública | Pública | Pública |
| `/api/usuarios/logout/` | Sesión | Sesión | Sesión | Sesión | Sesión |
| `/api/usuarios/me/` | Sesión | Sesión | Sesión | Sesión | Sesión |
| `/api/usuarios/recuperar-password/` | Pública | Pública | Pública | Pública | Pública |
| `/api/usuarios/resumen/` | Sí | — | — | — | — |
| `/api/usuarios/{id}/actualizar/` | Sí | — | — | — | — |
| `/api/usuarios/{id}/desactivar/` | Sí | — | — | — | — |

## /api/academico/

| Ruta | Admin. | Director | Bienestar | Docente | Estudiante |
| --- | :---: | :---: | :---: | :---: | :---: |
| `/api/academico/bitacora/` | Sí | — | — | — | — |
| `/api/academico/bitacora/{id}/` | Sí | — | — | — | — |
| `/api/academico/courses/indicators/` | Sí | Sí | Sí | Sí | — |
| `/api/academico/courses/{id}/detail/` | Sí | Sí | Sí | Sí | — |
| `/api/academico/cursos/{id}/asistencia/` | Sí | — | — | Sí | — |
| `/api/academico/cursos/{id}/inasistencia/` | Sí | Sí | Sí | Sí | — |
| `/api/academico/cursos/{id}/umbral-inasistencia/` | Sí | — | — | — | — |
| `/api/academico/import/asistencia/` | Sí | — | — | Sí | — |
| `/api/academico/import/history/` | Sí | — | — | — | — |
| `/api/academico/import/offering/` | Sí | — | — | — | — |
| `/api/academico/import/pensum/` | Sí | — | — | — | — |
| `/api/academico/import/students/` | Sí | — | — | — | — |
| `/api/academico/import/teachers/` | Sí | — | — | — | — |
| `/api/academico/indicadores/` | Sí | Sí | — | — | — |
| `/api/academico/students/` | Sí | Sí | Sí | Sí | — |
| `/api/academico/students/{id}/` | Sí | Sí | Sí | Sí | — |
| `/api/academico/students/{id}/asistencia/` | Sí | Sí | Sí | Sí | — |
| `/api/academico/students/{id}/history/` | Sí | Sí | Sí | Sí | — |
| `/api/academico/students/{id}/indicators/` | Sí | Sí | Sí | Sí | — |
| `/api/academico/students/{id}/intervenciones/` | Sí | Sí | Sí | Sí | — |
| `/api/academico/students/{id}/notas-corte/` | Sí | Sí | Sí | Sí | — |
| `/api/academico/teacher/course/{id}/students/` | — | — | — | Sí | — |
| `/api/academico/teacher/dashboard/` | — | — | — | Sí | — |

## /api/alertas/

| Ruta | Admin. | Director | Bienestar | Docente | Estudiante |
| --- | :---: | :---: | :---: | :---: | :---: |
| `/api/alertas/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/anotaciones/{id}/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/corte/evaluar/` | Sí | Sí | — | — | — |
| `/api/alertas/estudiantes/{id}/recalcular/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/evidencias/{id}/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/generar/` | Sí | — | Sí | Sí | — |
| `/api/alertas/intervenciones/{id}/anotaciones/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/intervenciones/{id}/concluir/` | Sí | — | Sí | Sí | — |
| `/api/alertas/intervenciones/{id}/evidencias/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/intervenciones/{id}/evidencias/upload/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/migrar-riesgo-periodos/` | Sí | — | — | — | — |
| `/api/alertas/notificaciones/historial/` | Sí | — | — | — | — |
| `/api/alertas/notificaciones/internas/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/notificaciones/internas/{id}/leer/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/recordatorios/` | Sí | Sí | — | — | — |
| `/api/alertas/recordatorios/casos-sin-seguimiento/` | Sí | Sí | — | — | — |
| `/api/alertas/recordatorios/configuracion/` | Sí | Sí | — | — | — |
| `/api/alertas/recordatorios/ejecutar/` | Sí | Sí | — | — | — |
| `/api/alertas/recordatorios/programada/` | Cron | Cron | Cron | Cron | Cron |
| `/api/alertas/reevaluacion/ejecuciones/` | Sí | Sí | — | — | — |
| `/api/alertas/reevaluacion/ejecuciones/{id}/` | Sí | Sí | — | — | — |
| `/api/alertas/reevaluacion/ejecutar/` | Sí | — | — | — | — |
| `/api/alertas/reevaluacion/programada/` | Cron | Cron | Cron | Cron | Cron |
| `/api/alertas/reevaluar/` | Sí | — | — | — | — |
| `/api/alertas/reglas/` | Sí | Sí | Sí | — | — |
| `/api/alertas/reglas/{id}/` | Sí | Sí | Sí | — | — |
| `/api/alertas/reportes/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/reportes/exportar/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/solicitudes/` | Sí | Sí | Sí | — | — |
| `/api/alertas/solicitudes/{id}/` | Sí | Sí | Sí | — | — |
| `/api/alertas/{id}/cerrar/` | Sí | — | Sí | Sí | — |
| `/api/alertas/{id}/intervenciones/` | Sí | Sí | Sí | Sí | — |
| `/api/alertas/{id}/intervenciones/registrar/` | Sí | — | Sí | Sí | — |

## /api/portal/

| Ruta | Admin. | Director | Bienestar | Docente | Estudiante |
| --- | :---: | :---: | :---: | :---: | :---: |
| `/api/portal/alertas/` | — | — | — | — | Sí |
| `/api/portal/alertas/{id}/` | — | — | — | — | Sí |
| `/api/portal/asistencia/` | — | — | — | — | Sí |
| `/api/portal/evolucion/` | — | — | — | — | Sí |
| `/api/portal/intervenciones/` | — | — | — | — | Sí |
| `/api/portal/intervenciones/{id}/` | — | — | — | — | Sí |
| `/api/portal/riesgo/` | — | — | — | — | Sí |
| `/api/portal/solicitudes/` | — | — | — | — | Sí |
| `/api/portal/solicitudes/{id}/cancelar/` | — | — | — | — | Sí |

## Acceso por objeto (acceso horizontal)

| Control | Prueba |
| --- | --- |
| El estudiante solo obtiene su propio riesgo aunque envíe el código de otro | `pruebas_integracion/test_flujo_portal.py`, `portal/tests.py` |
| Alerta, intervención o solicitud de otro estudiante: 404 y auditoría | `portal/tests_alertas.py`, `portal/tests_intervenciones.py`, `portal/tests_solicitudes.py` |
| Evolución y asistencia: solo las propias | `portal/tests_evolucion.py`, `portal/tests_asistencia.py` |
| El estudiante recibe 403 en las rutas del personal, incluso con su propio código | `academico/tests_acceso_estudiante.py` |
| El docente no ve estudiantes, cursos, anotaciones ni evidencias ajenos | `alertas/tests.py`, `alertas/tests_alcance_docente.py`, `alertas/tests_evidencias.py`, `academico/tests_asistencia.py`, `academico/tests_inasistencia.py` |
| El director consulta pero no cierra ni edita | `alertas/tests_director_lectura.py` |
