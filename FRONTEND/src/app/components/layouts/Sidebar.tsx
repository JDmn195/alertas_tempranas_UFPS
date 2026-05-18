import { Link, useLocation } from 'react-router';
import {BookOpen } from 'lucide-react';
import {
  Upload,
  Users,
  AlertTriangle,
  Settings,
  GraduationCap,
  BarChart3,
  FileDown,
  Shield,
  LogOut,
  FileText,
} from 'lucide-react';

type NavItem = {
  path: string;
  label: string;
  icon: React.ElementType;
  roles?: string[];
};

const navItems: NavItem[] = [
  { path: '/dashboard/admin/import', label: 'Importar Módulo', icon: Upload, roles: ['ADMINISTRADOR'] },
  { path: '/dashboard/admin/risk-rules', label: 'Reglas de Riesgo', icon: Settings, roles: ['ADMINISTRADOR'] },
  { path: '/dashboard/admin/users', label: 'Gestión de Usuarios', icon: Shield, roles: ['ADMINISTRADOR'] },
  { path: '/dashboard/admin/notifications-history', label: 'Historial Notif.', icon: FileText, roles: ['ADMINISTRADOR'] },
  { path: '/dashboard/students', label: 'Estudiantes', icon: Users, roles: ['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR'] },
  { path: '/dashboard/courses', label: 'Cursos', icon: BookOpen, roles: ['ADMINISTRADOR', 'DIRECTOR', 'DOCENTE'] },
  { path: '/dashboard/alerts', label: 'Gestión de Alertas', icon: AlertTriangle, roles: ['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR'] },
  { path: '/dashboard/teacher', label: 'Panel del Docente', icon: GraduationCap, roles: ['DOCENTE'] },
  { path: '/dashboard/director', label: 'Panel Estratégico', icon: BarChart3, roles: ['ADMINISTRADOR'] },
  { path: '/dashboard/reports', label: 'Exportar Reportes', icon: FileDown, roles: ['ADMINISTRADOR', 'BIENESTAR'] },
];

export function Sidebar() {
  const location = useLocation();
  const userJson = localStorage.getItem('user');
  const user = userJson ? JSON.parse(userJson) : null;
  const userRole = user?.rol || '';

  // Filtrar items por rol
  const filteredItems = navItems.filter((item) => 
    !item.roles || item.roles.includes(userRole)
  );

  const handleLogout = () => {
    localStorage.removeItem('user');
    window.location.href = '/login';
  };

  return (
    <div className="w-64 bg-white border-r border-gray-200 h-screen flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#C8102E] rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-xl">U</span>
          </div>
          <div>
            <h1 className="font-bold text-gray-900 text-sm leading-tight">UFPS</h1>
            <p className="text-xs text-gray-500">Alertas Tempranas</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {filteredItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path || location.pathname.startsWith(item.path + '/');

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors relative ${
                isActive
                  ? 'text-[#C8102E] bg-red-50'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              {isActive && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#C8102E] rounded-r" />}
              <Icon className={`w-5 h-5 ${isActive ? 'text-[#C8102E]' : 'text-gray-400'}`} />
              <span className="text-sm font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* User info & Logout */}
      <div className="p-4 border-t border-gray-200 space-y-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-[#C8102E] text-white rounded-full flex items-center justify-center">
            <span className="text-sm font-medium">
              {user?.nombre?.substring(0, 2).toUpperCase() || 'U'}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {user?.nombre || 'Usuario'}
            </p>
            <p className="text-xs text-gray-500 capitalize">{user?.rol?.toLowerCase() || 'Rol'}</p>
          </div>
        </div>
        
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors font-medium"
        >
          <LogOut className="w-4 h-4" />
          Cerrar Sesión
        </button>
      </div>
    </div>
  );
}
