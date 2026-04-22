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

  if (allowedRoles && !allowedRoles.includes(user.rol)) {
    // Si el rol no está permitido, redirigir al dashboard principal del usuario
    // o a una página de acceso denegado. Por ahora, al dashboard base.
    console.warn(`Acceso denegado para el rol: ${user.rol}`);
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
