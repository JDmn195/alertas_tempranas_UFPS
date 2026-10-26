import { Outlet, useLocation, useNavigate } from 'react-router';
import { Info, X } from 'lucide-react';

/**
 * Layout del portal del estudiante (EP-09). Va dentro de MainLayout (Sidebar y
 * TopNav comunes) y muestra el aviso cuando ProtectedRoute devuelve al
 * estudiante desde una ruta del personal.
 */
export function PortalLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const aviso = (location.state as { aviso?: string } | null)?.aviso;

  const cerrarAviso = () => navigate(location.pathname, { replace: true, state: null });

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {aviso && (
        <div role="alert" className="flex items-start gap-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-xl px-4 py-3">
          <Info className="w-5 h-5 mt-0.5 shrink-0" />
          <p className="flex-1 text-sm">{aviso}</p>
          <button onClick={cerrarAviso} aria-label="Cerrar aviso" className="text-amber-600 hover:text-amber-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      <Outlet />
    </div>
  );
}
