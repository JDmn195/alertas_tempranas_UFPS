// src/services/apiFetch.ts
import { cerrarSesionLocal } from './session';

export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const userStr = localStorage.getItem('user');
  const headers = new Headers(options.headers || {});
  let conToken = false;

  if (userStr) {
    try {
      const user = JSON.parse(userStr);
      if (user && user.token) {
        headers.set('Authorization', `Bearer ${user.token}`);
        conToken = true;
      }
    } catch (e) {
      console.error('Error parsing user from localStorage', e);
    }
  }

  // Si no se definió Content-Type y hay un body que no es FormData, asumimos JSON
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new Error('No se pudo conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.');
  }

  // Token expirado o inválido: cerrar la sesión local y volver al login
  if (response.status === 401 && conToken) {
    cerrarSesionLocal();
    window.location.assign('/login');
  }

  // SDAT-308: el proxy de Render puede responder HTML mientras despierta.
  // Conservamos JSON y descargas; un error HTML nunca llega a response.json().
  const tipo = response.headers.get('Content-Type') || '';
  if ((!response.ok || tipo.includes('text/html')) && !tipo.includes('json') && response.status !== 204) {
    // SDAT-346: solo 429, 502, 503 y 504 indican que Render está despertando; un 500 es un error al procesar.
    const esperando = [429, 502, 503, 504].includes(response.status) || response.ok;
    const escritura = !['GET', 'HEAD'].includes((options.method || 'GET').toUpperCase());
    return new Response(JSON.stringify({
      error: esperando
        ? 'El servidor está iniciando o no está disponible. Espera un momento e inténtalo de nuevo.'
        : response.status >= 500
          ? (escritura ? 'No pudimos guardar. Inténtalo de nuevo.' : 'No pudimos completar la solicitud. Inténtalo de nuevo.')
          : 'No se pudo completar la solicitud. Inténtalo de nuevo.',
    }), {
      status: response.ok ? 503 : response.status,
      headers: { 'Content-Type': 'application/json', ...(response.headers.has('Retry-After') ? { 'Retry-After': response.headers.get('Retry-After')! } : {}) },
    });
  }
  return response;
}
