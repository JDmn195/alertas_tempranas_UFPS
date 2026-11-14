# Configuración de producción · SDAT-300

Con `DEBUG=False`, fuera de pruebas y E2E, el servidor redirige a HTTPS, envía HSTS durante un año y marca las cookies de sesión y CSRF como seguras. Render termina TLS: Django reconoce HTTPS mediante `X-Forwarded-Proto`. El backend debe permanecer detrás de ese proxy de confianza.

La caché de producción usa la tabla `sat_cache` en la base de datos. Los procesos de Gunicorn consultan el mismo contador de intentos. `build.sh` ejecuta `python manage.py createcachetable` después de las migraciones; el comando conserva la tabla si ya existe. En un despliegue manual también debe ejecutarse ese comando antes de servir tráfico.

La ruta del administrador se obtiene de `ADMIN_URL`. Sin definirla, producción usa `/gestion-interna/`; desarrollo, pruebas y E2E conservan `/admin/`. Una ruta vacía impide iniciar el servidor. Cambiar la ruta no sustituye la autenticación ni los permisos de Django.

Esta modificación añade los valores predeterminados en código. No modifica archivos `.env` ni variables de Render. La verificación local no acredita que producción ya se haya desplegado o que la tabla exista en Neon; eso debe comprobarse durante el despliegue autorizado.
