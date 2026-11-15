# Sesiones de ocho horas y revocación · SDAT-323

Los nuevos JWT duran ocho horas e incluyen `version_sesion`. `POST /api/usuarios/logout/`, autenticado y disponible para los cinco roles, incrementa esa versión de forma atómica y registra LOGOUT en auditoría. Todos los tokens de una versión anterior quedan rechazados, incluidas las sesiones abiertas en otros dispositivos. Un nuevo login emite un token de la versión vigente.

La migración `usuarios.0015_version_sesion` añade el campo con valor inicial cero y registra el nuevo tipo de auditoría. Conserva usuarios, roles, contraseñas y asociaciones. Los tokens emitidos antes del cambio se interpretan como versión cero: conservan su expiración original hasta caducar o hasta el primer logout, que también los revoca. No se reescriben los tokens ya entregados.

Despliegue: aplicar primero la migración y completar el despliegue de todos los procesos del backend; después desplegar el frontend que llama a logout. Un proceso antiguo no conoce la revocación. La interfaz espera la respuesta del servidor antes de limpiar la sesión; ante un fallo informa y permite reintentar. Un 401 permite cerrar localmente una sesión ya inválida.

Reversión: se puede revertir el frontend conservando el backend y la columna. Volver a un backend anterior que ignore la versión volvería a aceptar tokens revocados aún no caducados; requiere invalidar previamente todas las sesiones mediante una rotación de la clave de firma autorizada por el responsable. No se realiza esa rotación ni se modifica el entorno como parte de esta tarea. La reversión de esquema se prueba solo en una base de pruebas, conservando los datos anteriores; eliminar la columna no conserva el estado de revocación.
