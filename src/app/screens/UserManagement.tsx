import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

const users = [
  {
    id: '1',
    name: 'Juan Carlos Pérez Gómez',
    email: 'juan.perez@ufps.edu.co',
    role: 'Docente',
    status: true,
    lastLogin: '2026-04-08 14:30',
  },
  {
    id: '2',
    name: 'María Fernanda García López',
    email: 'maria.garcia@ufps.edu.co',
    role: 'Docente',
    status: true,
    lastLogin: '2026-04-07 16:45',
  },
  {
    id: '3',
    name: 'Carlos Alberto Ruiz Sánchez',
    email: 'carlos.ruiz@ufps.edu.co',
    role: 'Director Académico',
    status: true,
    lastLogin: '2026-04-08 09:15',
  },
  {
    id: '4',
    name: 'Ana Patricia López Martínez',
    email: 'ana.lopez@ufps.edu.co',
    role: 'Docente',
    status: true,
    lastLogin: '2026-04-06 11:20',
  },
  {
    id: '5',
    name: 'Diego Alejandro Mendoza Cruz',
    email: 'diego.mendoza@ufps.edu.co',
    role: 'Tutor',
    status: true,
    lastLogin: '2026-04-08 08:30',
  },
  {
    id: '6',
    name: 'Laura Valentina Torres Silva',
    email: 'laura.torres@ufps.edu.co',
    role: 'Personal de Bienestar',
    status: true,
    lastLogin: '2026-04-05 15:10',
  },
  {
    id: '7',
    name: 'Roberto José Castillo Díaz',
    email: 'roberto.castillo@ufps.edu.co',
    role: 'Docente',
    status: false,
    lastLogin: '2026-03-20 10:00',
  },
  {
    id: '8',
    name: 'Isabella Sofía Rodríguez Vargas',
    email: 'isabella.rodriguez@ufps.edu.co',
    role: 'Administrador',
    status: true,
    lastLogin: '2026-04-08 13:00',
  },
];

export default function UserManagement() {
  const [showDrawer, setShowDrawer] = useState(false);
  const [newUser, setNewUser] = useState({
    name: '',
    email: '',
    role: 'Docente',
    courses: [] as string[],
  });

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="border-l-4 border-[#C8102E] pl-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Gestión de Usuarios</h1>
          <p className="text-sm text-gray-600 mt-1">
            Gestionar usuarios, roles y permisos del sistema
          </p>
        </div>
        <Button onClick={() => setShowDrawer(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Nuevo Usuario
        </Button>
      </div>

      {/* Users table */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Usuarios Activos ({users.filter((u) => u.status).length})
          </h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#C8102E] text-white">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Nombre Completo
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Correo Electrónico
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Rol
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Estado
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Último Ingreso
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {users.map((user, index) => (
                <tr
                  key={user.id}
                  className={index % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5]'}
                >
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">
                    {user.name}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">{user.email}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Badge
                      variant={
                        user.role === 'Administrador'
                          ? 'high'
                          : user.role === 'Director Académico'
                          ? 'medium'
                          : 'gray'
                      }
                      size="sm"
                    >
                      {user.role}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={user.status}
                        className="sr-only peer"
                        readOnly
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-red-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#C8102E]"></div>
                    </label>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {user.lastLogin}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm">
                        Editar
                      </Button>
                      <Button variant="secondary" size="sm">
                        {user.status ? 'Desactivar' : 'Activar'}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* New User Drawer */}
      {showDrawer && (
        <>
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-40"
            onClick={() => setShowDrawer(false)}
          />
          <div className="fixed right-0 top-0 bottom-0 w-[600px] bg-white shadow-2xl z-50 overflow-y-auto">
            {/* Drawer header */}
            <div className="bg-[#C8102E] text-white px-6 py-4 flex items-center justify-between sticky top-0">
              <h2 className="text-xl font-bold">Crear Nuevo Usuario</h2>
              <button
                onClick={() => setShowDrawer(false)}
                className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg p-1"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Drawer content */}
            <div className="p-6 space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Nombre Completo *
                </label>
                <input
                  type="text"
                  value={newUser.name}
                  onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                  placeholder="e.g., Juan Carlos Pérez"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Correo Electrónico *
                </label>
                <input
                  type="email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                  placeholder="usuario@ufps.edu.co"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Rol *
                </label>
                <select
                  value={newUser.role}
                  onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                >
                  <option value="Docente">Docente</option>
                  <option value="Director Académico">Director Académico</option>
                  <option value="Tutor">Tutor</option>
                  <option value="Personal de Bienestar">Personal de Bienestar</option>
                  <option value="Administrador">Administrador</option>
                </select>
              </div>

              {(newUser.role === 'Docente' || newUser.role === 'Tutor') && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Cursos Asignados
                  </label>
                  <div className="space-y-2 max-h-48 overflow-y-auto border border-gray-200 rounded-lg p-3">
                    {[
                      'Base de Datos I',
                      'Programación II',
                      'Estructuras de Datos',
                      'Cálculo Diferencial',
                      'Física II',
                      'Álgebra Lineal',
                    ].map((course) => (
                      <label key={course} className="flex items-center">
                        <input
                          type="checkbox"
                          className="w-4 h-4 text-[#C8102E] border-gray-300 rounded focus:ring-[#C8102E]"
                        />
                        <span className="ml-2 text-sm text-gray-700">{course}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Contraseña Inicial *
                </label>
                <input
                  type="password"
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                  placeholder="••••••••"
                />
                <p className="text-xs text-gray-500 mt-1">
                  El usuario deberá cambiar la contraseña en su primer ingreso
                </p>
              </div>

              <div className="border-t border-gray-200 pt-4">
                <h3 className="text-sm font-medium text-gray-700 mb-3">Permisos</h3>
                <div className="space-y-2">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      className="w-4 h-4 text-[#C8102E] border-gray-300 rounded focus:ring-[#C8102E]"
                      defaultChecked
                    />
                    <span className="ml-2 text-sm text-gray-700">
                      Ver perfiles de estudiantes
                    </span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      className="w-4 h-4 text-[#C8102E] border-gray-300 rounded focus:ring-[#C8102E]"
                      defaultChecked
                    />
                    <span className="ml-2 text-sm text-gray-700">
                      Registrar intervenciones
                    </span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      className="w-4 h-4 text-[#C8102E] border-gray-300 rounded focus:ring-[#C8102E]"
                    />
                    <span className="ml-2 text-sm text-gray-700">Generar reportes</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      className="w-4 h-4 text-[#C8102E] border-gray-300 rounded focus:ring-[#C8102E]"
                    />
                    <span className="ml-2 text-sm text-gray-700">
                      Modificar reglas de riesgo
                    </span>
                  </label>
                </div>
              </div>
            </div>

            {/* Drawer footer */}
            <div className="border-t border-gray-200 px-6 py-4 bg-gray-50 sticky bottom-0 flex items-center justify-end gap-3">
              <Button variant="secondary" onClick={() => setShowDrawer(false)}>
                Cancelar
              </Button>
              <Button onClick={() => setShowDrawer(false)}>
                Crear Usuario
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
