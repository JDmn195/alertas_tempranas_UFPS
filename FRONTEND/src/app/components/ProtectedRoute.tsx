import { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router';
import { type ResultadoSesion, sesionVerificada, verificarSesion } from '../../services/session';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: string[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const location = useLocation();
  const [sesion, setSesion] = useState<ResultadoSesion | undefined>(sesionVerificada);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let activo = true;
    verificarSesion().then((resultado) => {
      if (activo) setSesion(resultado);
    });
    return () => {
      activo = false;
    };
  }, [intento]);

  if (!sesion) {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-gray-500">
        Verificando sesión…
      </div>
    );
  }

  if (sesion.estado === 'error') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-sm text-gray-600">
        <p>No se pudo verificar la sesión con el servidor.</p>
        <button
          onClick={() => { setSesion(undefined); setIntento((n) => n + 1); }}
          className="px-4 py-2 rounded-lg bg-[#C8102E] text-white"
        >
          Reintentar
        </button>
      </div>
    );
  }

  if (sesion.estado === 'sin-sesion') {
    // Sin token o token inválido/expirado: volver al login
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles) {
    // El rol viene del servidor, no de localStorage
    const userRoles = sesion.usuario.rol ? sesion.usuario.rol.split(',') : [];
    const hasAccess = allowedRoles.some(role => userRoles.includes(role));
    if (!hasAccess) {
      // Si ningún rol está permitido, redirigir al dashboard principal del usuario
      console.warn(`Acceso denegado para los roles: ${sesion.usuario.rol}`);
      return <Navigate to="/dashboard" replace />;
    }
  }

  return <>{children}</>;
}
