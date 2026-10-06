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

  const response = await fetch(url, {
    ...options,
    headers
  });

  // Token expirado o inválido: cerrar la sesión local y volver al login
  if (response.status === 401 && conToken) {
    cerrarSesionLocal();
    window.location.assign('/login');
  }

  return response;
}
