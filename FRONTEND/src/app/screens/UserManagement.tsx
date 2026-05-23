import { useState, useEffect, useCallback } from 'react';
import { Plus, X, AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

interface User {
  id: string;
  nombre: string;
  correo: string;
  roles: string[];
  activo: boolean;
}

const ROLE_LABELS: Record<string, string> = {
  ADMINISTRADOR: 'Administrador',
  DIRECTOR: 'Director de Programa',
  BIENESTAR: 'Personal de Bienestar',
  DOCENTE: 'Docente',
};

const AVAILABLE_ROLES = [
  { id: 'ADMINISTRADOR', label: 'Administrador' },
  { id: 'DIRECTOR', label: 'Director de Programa' },
  { id: 'BIENESTAR', label: 'Personal de Bienestar' },
  { id: 'DOCENTE', label: 'Docente' },
];

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showDrawer, setShowDrawer] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  
  // Form states
  const [formName, setFormName] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formPassword, setFormPassword] = useState('');
  const [formRoles, setFormRoles] = useState<string[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Fetch users
  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await fetch(`${baseUrl}/api/usuarios/`);
      if (!res.ok) throw new Error('Error al cargar la lista de usuarios');
      const data = await res.json();
      setUsers(data.usuarios);
    } catch (err: any) {
      setError(err.message || 'Error al conectar con el servidor.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleOpenCreate = () => {
    setSelectedUser(null);
    setFormName('');
    setFormEmail('');
    setFormPassword('');
    setFormRoles([]);
    setFormError(null);
    setShowDrawer(true);
  };

  const handleOpenEdit = (user: User) => {
    setSelectedUser(user);
    setFormName(user.nombre);
    setFormEmail(user.correo);
    setFormPassword('');
    setFormRoles(user.roles);
    setFormError(null);
    setShowDrawer(true);
  };

  const handleRoleToggle = (roleId: string) => {
    setFormRoles((prev) =>
      prev.includes(roleId)
        ? prev.filter((r) => r !== roleId)
        : [...prev, roleId]
    );
  };

  const handleSave = async () => {
    setFormError(null);

    // Validations
    if (!formName.trim()) {
      setFormError('El nombre completo es obligatorio.');
      return;
    }
    if (!formEmail.trim()) {
      setFormError('El correo electrónico es obligatorio.');
      return;
    }

    // Escenario 3: No permitir guardar usuario sin roles
    if (formRoles.length === 0) {
      setFormError('El usuario debe tener al menos un rol asignado.');
      return;
    }

    if (!selectedUser && !formPassword) {
      setFormError('La contraseña inicial es obligatoria.');
      return;
    }

    setSaving(true);
    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const url = selectedUser
        ? `${baseUrl}/api/usuarios/${selectedUser.id}/`
        : `${baseUrl}/api/usuarios/`;
      const method = selectedUser ? 'PUT' : 'POST';

      const payload: any = {
        nombre: formName.trim(),
        correo: formEmail.trim(),
        roles: formRoles,
      };

      if (!selectedUser) {
        payload.contrasena = formPassword;
      }

      const res = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Error al guardar el usuario.');
      }

      // Close drawer & refresh list
      setShowDrawer(false);
      fetchUsers();
    } catch (err: any) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleStatus = async (user: User) => {
    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await fetch(`${baseUrl}/api/usuarios/${user.id}/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          activo: !user.activo,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Error al cambiar estado del usuario.');
      }
      fetchUsers();
    } catch (err: any) {
      alert(err.message);
    }
  };

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
        <Button onClick={handleOpenCreate}>
          <Plus className="w-4 h-4 mr-2" />
          Nuevo Usuario
        </Button>
      </div>

      {/* Main Content */}
      {loading ? (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <RefreshCw className="w-10 h-10 text-[#C8102E] animate-spin" />
          <p className="text-gray-500 animate-pulse">Cargando usuarios...</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border-l-4 border-red-500 p-6 rounded-lg text-center max-w-xl mx-auto">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-3" />
          <p className="text-sm text-red-700 font-semibold">{error}</p>
          <Button className="mt-4" variant="outline" onClick={fetchUsers}>
            Reintentar
          </Button>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Usuarios Registrados ({users.length})
            </h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[#C8102E] text-white">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider">
                    Nombre Completo
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider">
                    Correo Electrónico
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider">
                    Roles Asignados
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider">
                    Estado
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider">
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
                    <td className="px-6 py-4 text-sm font-semibold text-gray-900">
                      {user.nombre}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-800 font-mono">
                      {user.correo}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {user.roles.map((role) => (
                          <Badge
                            key={role}
                            variant={
                              role === 'ADMINISTRADOR'
                                ? 'high'
                                : role === 'DIRECTOR'
                                ? 'medium'
                                : 'gray'
                            }
                            size="sm"
                          >
                            {ROLE_LABELS[role] || role}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={user.activo}
                          onChange={() => handleToggleStatus(user)}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-red-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#C8102E]"></div>
                      </label>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => handleOpenEdit(user)}>
                          Editar
                        </Button>
                        <Button
                          variant={user.activo ? 'secondary' : 'default'}
                          size="sm"
                          onClick={() => handleToggleStatus(user)}
                        >
                          {user.activo ? 'Desactivar' : 'Activar'}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* User Drawer */}
      {showDrawer && (
        <>
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-40"
            onClick={() => setShowDrawer(false)}
          />
          <div className="fixed right-0 top-0 bottom-0 w-[600px] bg-white shadow-2xl z-50 overflow-y-auto">
            {/* Drawer header */}
            <div className="bg-[#C8102E] text-white px-6 py-4 flex items-center justify-between sticky top-0 z-10">
              <h2 className="text-xl font-bold">
                {selectedUser ? 'Editar Roles del Usuario' : 'Crear Nuevo Usuario'}
              </h2>
              <button
                onClick={() => setShowDrawer(false)}
                className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg p-1"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Drawer content */}
            <div className="p-6 space-y-6">
              {/* Form Error Message */}
              {formError && (
                <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-md flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-700 font-semibold">{formError}</p>
                </div>
              )}

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Nombre Completo *
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent text-sm"
                  placeholder="e.g., Juan Carlos Pérez"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Correo Electrónico *
                </label>
                <input
                  type="email"
                  value={formEmail}
                  onChange={(e) => setFormEmail(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent text-sm font-mono"
                  placeholder="usuario@ufps.edu.co"
                />
              </div>

              {/* Multiple Roles Checkbox Group */}
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Roles Asignados *
                </label>
                <div className="space-y-3 border border-gray-200 rounded-lg p-4 bg-gray-50/50">
                  {AVAILABLE_ROLES.map((r) => {
                    const isChecked = formRoles.includes(r.id);
                    return (
                      <label key={r.id} className="flex items-center cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleRoleToggle(r.id)}
                          className="w-4 h-4 text-[#C8102E] border-gray-300 rounded focus:ring-[#C8102E]"
                        />
                        <span className="ml-2.5 text-sm font-medium text-gray-800">
                          {r.label}
                        </span>
                      </label>
                    );
                  })}
                </div>
                <p className="text-xs text-gray-500 mt-1.5">
                  Seleccione uno o más roles para este usuario
                </p>
              </div>

              {!selectedUser && (
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Contraseña Inicial *
                  </label>
                  <input
                    type="password"
                    value={formPassword}
                    onChange={(e) => setFormPassword(e.target.value)}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent text-sm"
                    placeholder="••••••••"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    El usuario deberá cambiar la contraseña en su primer ingreso
                  </p>
                </div>
              )}
            </div>

            {/* Drawer footer */}
            <div className="border-t border-gray-200 px-6 py-4 bg-gray-50 sticky bottom-0 flex items-center justify-end gap-3 z-10">
              <Button variant="secondary" onClick={() => setShowDrawer(false)} disabled={saving}>
                Cancelar
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? 'Guardando...' : selectedUser ? 'Guardar Cambios' : 'Crear Usuario'}
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
