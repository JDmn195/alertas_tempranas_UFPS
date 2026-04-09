import { Link, useLocation } from 'react-router';
import {
  LayoutDashboard,
  Upload,
  Users,
  AlertTriangle,
  Settings,
  FileText,
  GraduationCap,
  BarChart3,
  FileDown,
  Shield,
} from 'lucide-react';

type NavItem = {
  path: string;
  label: string;
  icon: React.ElementType;
  role?: string[];
};

const navItems: NavItem[] = [
  { path: '/dashboard/admin/import', label: 'Importar Módulo', icon: Upload, role: ['admin'] },
  { path: '/dashboard/admin/risk-rules', label: 'Reglas de Riesgo', icon: Settings, role: ['admin'] },
  { path: '/dashboard/admin/users', label: 'Gestión de Usuarios', icon: Shield, role: ['admin'] },
  { path: '/dashboard/students', label: 'Estudiantes', icon: Users },
  { path: '/dashboard/alerts', label: 'Gestión de Alertas', icon: AlertTriangle, role: ['coordinator', 'director'] },
  { path: '/dashboard/teacher', label: 'Panel del Docente', icon: GraduationCap, role: ['teacher'] },
  { path: '/dashboard/director', label: 'Panel Estratégico', icon: BarChart3, role: ['director'] },
  { path: '/dashboard/reports', label: 'Exportar Reportes', icon: FileDown },
];

export function Sidebar() {
  const location = useLocation();

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
        {navItems.map((item) => {
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

      {/* User info */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center">
            <span className="text-gray-600 text-sm font-medium">AD</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">Usuario Admin</p>
            <p className="text-xs text-gray-500">Administrador</p>
          </div>
        </div>
      </div>
    </div>
  );
}
