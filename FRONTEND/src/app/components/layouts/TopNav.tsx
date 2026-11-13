import { useEffect, useState } from 'react';
import { Bell, ChevronRight, Menu } from 'lucide-react';
import { Link, useLocation } from 'react-router';
import { ubicacionDePagina } from './Sidebar';
import { apiFetch } from '../../../services/apiFetch';

/** Avisos internos sin leer del usuario (mismo endpoint de la bandeja). */
function useAvisosSinLeer(pathname: string): number {
  const [sinLeer, setSinLeer] = useState(0);
  useEffect(() => {
    let vigente = true;
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    apiFetch(`${baseUrl}/api/alertas/notificaciones/internas/`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!vigente || !data) return;
        setSinLeer((data.notificaciones || []).filter((n: { leida?: boolean }) => !n.leida).length);
      })
      .catch(() => { /* la campana queda sin contador */ });
    return () => { vigente = false; };
  }, [pathname]);
  return sinLeer;
}

/** Barra superior del personal: dónde estoy, fecha y avisos. */
export function TopNav({ onMenu }: { onMenu?: () => void }) {
  const location = useLocation();
  const { section, label } = ubicacionDePagina(location.pathname);
  const sinLeer = useAvisosSinLeer(location.pathname);
  const hoy = new Date().toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' });
  const enAvisos = location.pathname.startsWith('/dashboard/notifications');

  return (
    <header className="h-14 shrink-0 flex items-center justify-between gap-3 px-3 sm:px-5 lg:px-7 border-b border-line">
      <div className="flex items-center gap-2 min-w-0">
        <button onClick={onMenu} aria-label="Abrir menú" className="lg:hidden p-2 -ml-1 rounded-[10px] text-ink-soft hover:bg-wash">
          <Menu className="w-5 h-5" />
        </button>
        <img src="/logo-ufps.svg" alt="" className="h-7 w-auto lg:hidden" aria-hidden="true" />
        <p className="flex items-center gap-1.5 text-sm min-w-0" aria-label="Ubicación">
          {section && (
            <>
              <span className="hidden sm:inline text-ink-muted truncate">{section}</span>
              <ChevronRight className="hidden sm:inline w-3.5 h-3.5 text-ink-faint shrink-0" aria-hidden="true" />
            </>
          )}
          <span className="font-semibold text-ink truncate">{label}</span>
        </p>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <p className="hidden md:block text-sm text-ink-muted first-letter:uppercase">{hoy}</p>
        <Link
          to="/dashboard/notifications"
          aria-label={sinLeer > 0 ? `Notificaciones, ${sinLeer} sin leer` : 'Notificaciones'}
          aria-current={enAvisos ? 'page' : undefined}
          className={`relative flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium ${
            enAvisos ? 'border-primary bg-primary-tint text-primary-strong' : 'border-line bg-white text-ink-soft hover:border-line-strong hover:text-ink'
          }`}
        >
          <Bell className="w-4 h-4" aria-hidden="true" />
          <span className="hidden sm:inline">Avisos</span>
          {sinLeer > 0 && (
            <span className="min-w-5 h-5 px-1.5 rounded-full bg-riesgo-critico text-white text-xs font-semibold flex items-center justify-center" aria-hidden="true">
              {sinLeer > 99 ? '99+' : sinLeer}
            </span>
          )}
        </Link>
      </div>
    </header>
  );
}
