import { useState, useEffect, useMemo } from 'react';
import { Plus, X, RefreshCw, AlertTriangle, Edit2, Search } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { apiFetch } from '../../services/apiFetch';

interface User {
  id: string;
  nombre: string;
  correo: string;
  rol: string;
  activo: boolean;
}

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  
  const [showDrawer, setShowDrawer] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formData, setFormData] = useState({
    nombre: '',
    correo: '',
    rol: 'DOCENTE',
  });
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`${baseUrl}/api/usuarios/`);
      if (!res.ok) throw new Error('Error al cargar usuarios');
      const data = await res.json();
      setUsers(data.usuarios || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const filteredUsers = useMemo(() => {
    if (!searchTerm.trim()) return users;
    const term = searchTerm.toLowerCase();
    return users.filter(
      (user) =>
        user.nombre.toLowerCase().includes(term) ||
        user.correo.toLowerCase().includes(term) ||
        user.rol.toLowerCase().includes(term)
    );
  }, [users, searchTerm]);

  const handleOpenCreate = () => {
    setEditingUser(null);
    setFormData({ nombre: '', correo: '', rol: 'DOCENTE' });
    setFormError(null);
    setShowDrawer(true);
  };

  const handleOpenEdit = (user: User) => {
    setEditingUser(user);
    setFormData({ nombre: user.nombre, correo: user.correo, rol: user.rol });
    setFormError(null);
    setShowDrawer(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormLoading(true);
    setFormError(null);

    try {
      if (editingUser) {
        // Actualizar
        const res = await apiFetch(`${baseUrl}/api/usuarios/${editingUser.id}/actualizar/`, {
          method: 'PATCH',
          body: JSON.stringify(formData),
        });
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.error || 'Error al actualizar usuario');
        }
      } else {
        // Crear
        const res = await apiFetch(`${baseUrl}/api/usuarios/crear/`, {
          method: 'POST',
          body: JSON.stringify(formData),
        });
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.error || 'Error al crear usuario');
        }
      }
      setShowDrawer(false);
      fetchUsers();
    } catch (err: any) {
      setFormError(err.message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleToggleStatus = async (user: User) => {
    if (!window.confirm(`¿Estás seguro de que quieres ${user.activo ? 'desactivar' : 'activar'} a este usuario?`)) {
      return;
    }
    
    try {
      const res = await apiFetch(`${baseUrl}/api/usuarios/${user.id}/desactivar/`, {
        method: 'POST',
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Error al cambiar estado');
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
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchUsers}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Actualizar
          </Button>
          <Button onClick={handleOpenCreate}>
            <Plus className="w-4 h-4 mr-2" />
            Nuevo Usuario
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-lg border border-red-200 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Users table */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 px-6 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Usuarios Registrados ({filteredUsers.length})
          </h2>
          <div className="w-full md:w-72 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar por nombre, correo..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
            />
          </div>
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
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading && users.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                    Cargando usuarios...
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                    No se encontraron usuarios.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((user, index) => (
                  <tr
                    key={user.id}
                    className={index % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5] hover:bg-gray-50 transition-colors'}
                  >
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">
                      {user.nombre}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">{user.correo}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge
                        variant={
                          user.rol === 'ADMINISTRADOR'
                            ? 'high'
                            : user.rol === 'DIRECTOR'
                            ? 'medium'
                            : 'gray'
                        }
                        size="sm"
                      >
                        {user.rol}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <label className="relative inline-flex items-center cursor-pointer" title={user.activo ? 'Activo' : 'Inactivo'}>
                        <input
                          type="checkbox"
                          checked={user.activo}
                          className="sr-only peer"
                          onChange={() => handleToggleStatus(user)}
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-red-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#C8102E]"></div>
                      </label>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => handleOpenEdit(user)}>
                          <Edit2 className="w-3 h-3 mr-1" /> Editar
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Drawer */}
      {showDrawer && (
        <>
          <div
            className="fixed inset-0 z-40 transition-opacity"
            style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
            onClick={() => !formLoading && setShowDrawer(false)}
          />
          <div className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-white shadow-2xl z-50 overflow-y-auto transform transition-transform">
            <div className="bg-[#C8102E] text-white px-6 py-4 flex items-center justify-between sticky top-0 z-10">
              <h2 className="text-xl font-bold">{editingUser ? 'Editar Usuario' : 'Crear Nuevo Usuario'}</h2>
              <button
                onClick={() => !formLoading && setShowDrawer(false)}
                className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg p-1"
                disabled={formLoading}
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-6">
              {formError && (
                <div className="p-3 bg-red-50 text-red-700 text-sm rounded-lg border border-red-200">
                  {formError}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Nombre Completo *
                </label>
                <input
                  type="text"
                  required
                  value={formData.nombre}
                  onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
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
                  required
                  disabled={!!editingUser}
                  value={formData.correo}
                  onChange={(e) => setFormData({ ...formData, correo: e.target.value })}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent disabled:bg-gray-100 disabled:text-gray-500"
                  placeholder="usuario@ufps.edu.co"
                />
                {editingUser && (
                  <p className="text-xs text-gray-400 mt-1">El correo no se puede modificar.</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Rol *
                </label>
                <select
                  required
                  value={formData.rol}
                  onChange={(e) => setFormData({ ...formData, rol: e.target.value })}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent bg-white"
                >
                  <option value="DOCENTE">Docente</option>
                  <option value="DIRECTOR">Director Académico</option>
                  <option value="BIENESTAR">Personal de Bienestar</option>
                  <option value="ADMINISTRADOR">Administrador</option>
                </select>
              </div>

              {!editingUser && (
                <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-lg">
                  <p className="text-sm text-yellow-800 font-medium">Información sobre la contraseña</p>
                  <p className="text-xs text-yellow-700 mt-1">
                    Al crear el usuario, la contraseña inicial será igual al correo electrónico. El usuario deberá cambiarla en su primer inicio de sesión.
                  </p>
                </div>
              )}

              <div className="border-t border-gray-200 pt-6 mt-6 flex items-center justify-end gap-3 sticky bottom-0 bg-white">
                <Button type="button" variant="secondary" onClick={() => setShowDrawer(false)} disabled={formLoading}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={formLoading}>
                  {formLoading ? 'Guardando...' : (editingUser ? 'Guardar Cambios' : 'Crear Usuario')}
                </Button>
              </div>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
