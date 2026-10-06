// src/services/session.ts
//
// El usuario guardado en localStorage se puede modificar desde el navegador, así
// que el rol que decide qué pantallas se muestran es el que devuelve el backend
// a partir del JWT (GET /api/usuarios/me/). Se verifica una vez por carga de la
// página y por token. La protección real de los datos está en el backend.

const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface UsuarioSesion {
  id: number;
  nombre: string;
  correo: string;
  rol: string;
}

export type ResultadoSesion =
  | { estado: 'ok'; usuario: UsuarioSesion }
  | { estado: 'sin-sesion' }
  | { estado: 'error' };

let cache: { token: string; promesa: Promise<ResultadoSesion>; resultado?: ResultadoSesion } | null = null;

function tokenGuardado(): string | null {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    return user && typeof user.token === 'string' ? user.token : null;
  } catch {
    return null;
  }
}

export function cerrarSesionLocal() {
  localStorage.removeItem('user');
  cache = null;
}

/** Resultado ya verificado para el token actual, si lo hay (para no mostrar "cargando" de nuevo). */
export function sesionVerificada(): ResultadoSesion | undefined {
  const token = tokenGuardado();
  return token && cache?.token === token ? cache.resultado : undefined;
}

async function consultarServidor(token: string): Promise<ResultadoSesion> {
  try {
    const res = await fetch(`${baseUrl}/api/usuarios/me/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401) {
      cerrarSesionLocal();
      return { estado: 'sin-sesion' };
    }
    if (!res.ok) throw new Error(`Error ${res.status}`);
    const usuario: UsuarioSesion = await res.json();
    // Corrige cualquier dato alterado en localStorage con lo que dice el servidor
    const guardado = JSON.parse(localStorage.getItem('user') || '{}');
    localStorage.setItem('user', JSON.stringify({ ...guardado, ...usuario }));
    return { estado: 'ok', usuario };
  } catch {
    return { estado: 'error' };
  }
}

export function verificarSesion(): Promise<ResultadoSesion> {
  const token = tokenGuardado();
  if (!token) {
    return Promise.resolve({ estado: 'sin-sesion' });
  }
  if (cache?.token === token) {
    return cache.promesa;
  }

  const entrada: NonNullable<typeof cache> = { token, promesa: consultarServidor(token) };
  cache = entrada;
  entrada.promesa.then((resultado) => {
    if (cache !== entrada) return;
    if (resultado.estado === 'error') {
      cache = null; // permitir reintentar
    } else {
      entrada.resultado = resultado;
    }
  });
  return entrada.promesa;
}
