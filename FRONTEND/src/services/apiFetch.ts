// src/services/apiFetch.ts

export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const userStr = localStorage.getItem('user');
  const headers = new Headers(options.headers || {});
  
  if (userStr) {
    try {
      const user = JSON.parse(userStr);
      if (user && user.token) {
        headers.set('Authorization', `Bearer ${user.token}`);
      } else if (user && user.id) {
        // Fallback temporal si el token no existe
        headers.set('X-User-Id', String(user.id));
      }
    } catch (e) {
      console.error('Error parsing user from localStorage', e);
    }
  }

  // Si no se definió Content-Type y hay un body que no es FormData, asumimos JSON
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  return fetch(url, {
    ...options,
    headers
  });
}
