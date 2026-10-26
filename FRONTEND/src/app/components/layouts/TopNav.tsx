import { Bell } from 'lucide-react';
import { Link } from 'react-router';

export function TopNav() {
  const userJson = localStorage.getItem('user');
  const esEstudiante = (userJson ? JSON.parse(userJson) : null)?.rol === 'ESTUDIANTE';

  return (
    <div className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">{esEstudiante ? 'Portal del Estudiante' : 'Panel de Control'}</h2>
        <p className="text-sm text-gray-500">Universidad Francisco de Paula Santander</p>
      </div>

      {/* Las notificaciones internas son del personal; el portal no tiene acceso a ellas */}
      {!esEstudiante && (
        <div className="flex items-center gap-4">
          <Link to="/dashboard/notifications" className="relative p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-50">
            <Bell className="w-5 h-5" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-[#C8102E] rounded-full"></span>
          </Link>
        </div>
      )}
    </div>
  );
}
