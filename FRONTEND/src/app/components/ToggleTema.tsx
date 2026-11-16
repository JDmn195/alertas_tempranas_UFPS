import { useSyncExternalStore } from 'react';
import { Moon, Sun } from 'lucide-react';

const CLAVE = 'tema';
const EVENTO = 'tema-cambiado';

function leerGuardado(): 'claro' | 'oscuro' | null {
  try {
    const v = localStorage.getItem(CLAVE);
    return v === 'oscuro' || v === 'claro' ? v : null;
  } catch {
    return null;
  }
}

function esOscuro(): boolean {
  return document.documentElement.classList.contains('dark');
}

/** Aplica el tema guardado (o el del sistema) antes del primer render. */
export function iniciarTema(): void {
  const guardado = leerGuardado();
  const oscuro = guardado ? guardado === 'oscuro' : window.matchMedia?.('(prefers-color-scheme: dark)').matches;
  document.documentElement.classList.toggle('dark', !!oscuro);
}

function suscribir(cb: () => void) {
  window.addEventListener(EVENTO, cb);
  return () => window.removeEventListener(EVENTO, cb);
}

/** true si el modo oscuro está activo. */
export function useModoOscuro(): boolean {
  return useSyncExternalStore(suscribir, esOscuro, () => false);
}

function alternar() {
  const oscuro = !esOscuro();
  document.documentElement.classList.toggle('dark', oscuro);
  try {
    localStorage.setItem(CLAVE, oscuro ? 'oscuro' : 'claro');
  } catch {
    /* sin almacenamiento: el cambio vale solo para esta sesión */
  }
  window.dispatchEvent(new Event(EVENTO));
}

/** Botón de la barra superior para alternar entre modo claro y oscuro. */
export function ToggleTema() {
  const oscuro = useModoOscuro();
  const Icono = oscuro ? Sun : Moon;
  return (
    <button
      type="button"
      onClick={alternar}
      aria-label={oscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
      aria-pressed={oscuro}
      data-testid="toggle-tema"
      className="min-h-11 min-w-11 flex items-center justify-center p-2 rounded-full border border-line bg-white text-ink-soft hover:border-line-strong hover:text-ink"
    >
      <Icono className="w-4 h-4" aria-hidden="true" />
    </button>
  );
}
