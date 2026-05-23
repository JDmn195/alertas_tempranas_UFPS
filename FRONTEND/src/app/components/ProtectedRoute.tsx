import { Navigate, useLocation } from 'react-router';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: string[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const location = useLocation();
  const userJson = localStorage.getItem('user');
  
  if (!userJson) {
    // Si no hay usuario, redirigir a login
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  const user = JSON.parse(userJson);

  if (allowedRoles) {
    const userRoles = user.rol ? user.rol.split(',') : [];
    const hasAccess = allowedRoles.some(role => userRoles.includes(role));
    if (!hasAccess) {
      // Si ningún rol está permitido, redirigir al dashboard principal del usuario
      console.warn(`Acceso denegado para los roles: ${user.rol}`);
      return <Navigate to="/dashboard" replace />;
    }
  }

  return <>{children}</>;
}
