# Bloqueo de inicio de sesión · SDAT-326

El contador identifica la combinación de IP y correo normalizado. Cinco intentos incorrectos bloquean esa combinación durante quince minutos. Otra IP puede iniciar sesión en la misma cuenta; otro correo desde el mismo origen mantiene su contador independiente. Un inicio correcto o el restablecimiento de contraseña limpia el contador del origen correspondiente.

En Render se toma `CF-Connecting-IP`, validada como IPv4 o IPv6, cuando existe el hostname automático de Render. Esto depende de que el tráfico público pase por Cloudflare, como documenta Render. Fuera de Render se usa `REMOTE_ADDR` y se ignoran cabeceras reenviadas del cliente. Las direcciones IPv6 se normalizan para que representaciones equivalentes no creen contadores distintos. `X-Forwarded-For` no se usa para el bloqueo.

La caché compartida de producción se configura en SDAT-300. Este control no sustituye una protección adicional contra ataques distribuidos. Las pruebas locales no certifican el despliegue ni el funcionamiento de las cabeceras del servicio publicado.

Referencias: [tráfico de Render y Cloudflare](https://render.com/articles/how-render-handles-ddos-attacks), [cabeceras de Cloudflare](https://developers.cloudflare.com/fundamentals/reference/http-headers/).
