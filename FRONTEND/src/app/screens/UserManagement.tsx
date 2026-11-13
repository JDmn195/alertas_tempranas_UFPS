import { useState, useEffect, useMemo } from 'react';
import { Plus, X, RefreshCw, AlertTriangle, Edit2, Search } from 'lucide-react';
import { CintaIndicadores, EncabezadoPagina } from '../components/Panel';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { apiFetch } from '../../services/apiFetch';

import { CargandoBloque, EstadoVacio } from '../components/Estados';
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
  // Contraseña temporal del usuario recién creado: el backend solo la devuelve una vez
  const [credencialesNuevas, setCredencialesNuevas] = useState<{ correo: string; contrasena: string } | null>(null);

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
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.error || 'Error al crear usuario');
        }
        setCredencialesNuevas({ correo: formData.correo, contrasena: data.contrasena_temporal });
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
    <div className="space-y-5">
      <EncabezadoPagina titulo="Gestión de Usuarios" detalle="Administra quién accede al sistema, con qué rol y si su cuenta está activa.">
        <Button variant="outline" onClick={fetchUsers}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Actualizar
        </Button>
        <Button onClick={handleOpenCreate}>
          <Plus className="w-4 h-4 mr-2" />
          Nuevo Usuario
        </Button>
      </EncabezadoPagina>

      <CintaIndicadores
        cargando={loading && users.length === 0}
        indicadores={[
          { etiqueta: 'Usuarios', valor: users.length },
          { etiqueta: 'Activos', valor: users.filter((u) => u.activo).length, tono: 'bien' },
          { etiqueta: 'Inactivos', valor: users.filter((u) => !u.activo).length, tono: users.some((u) => !u.activo) ? 'aviso' : undefined },
          { etiqueta: 'Roles en uso', valor: new Set(users.map((u) => u.rol)).size },
        ]}
      />

      {credencialesNuevas && (
        <div className="p-4 bg-green-50 text-green-800 rounded-[10px] border border-green-200 flex items-start justify-between gap-4">
          <div className="text-sm">
            <p className="font-semibold">Usuario creado. Entrégale estas credenciales; la contraseña no se volverá a mostrar.</p>
            <p className="mt-1">Correo: <span className="tabular-nums">{credencialesNuevas.correo}</span></p>
            <p>Contraseña temporal: <span className="tabular-nums select-all">{credencialesNuevas.contrasena}</span></p>
            <p className="mt-1 text-green-700">Deberá cambiarla en su primer inicio de sesión.</p>
          </div>
          <button onClick={() => setCredencialesNuevas(null)} className="text-green-700 hover:text-green-900" aria-label="Cerrar">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-[10px] border border-red-200 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Users table */}
      <div className="bg-white rounded-[14px] border border-line overflow-hidden">
        <div className="border-b border-line px-5 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <h2 className="text-base font-semibold text-ink">
            {filteredUsers.length} usuario{filteredUsers.length !== 1 ? 's' : ''}
          </h2>
          <div className="w-full md:w-72 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint" />
            <input
              type="text"
              placeholder="Buscar por nombre, correo..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full h-10 pl-9 pr-3 border border-line-strong rounded-[10px] bg-white text-sm text-ink"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="tabular-nums w-full">
            <thead className="bg-paper text-ink-soft border-b border-line">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold">
                  Nombre Completo
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold">
                  Correo Electrónico
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold">
                  Rol
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold">
                  Estado
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {loading && users.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-6"><CargandoBloque texto="Cargando usuarios..." filas={5} /></td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={5}><EstadoVacio titulo="No se encontraron usuarios." detalle="Revisa la búsqueda o crea un usuario con «Nuevo Usuario»." /></td>
                </tr>
              ) : (
                filteredUsers.map((user) => (
                  <tr
                    key={user.id}
                    className="hover:bg-paper transition-colors"
                  >
                    <td className="px-5 py-3.5 text-sm font-medium text-ink">
                      {user.nombre}
                    </td>
                    <td className="px-5 py-3.5 text-sm text-ink-muted">{user.correo}</td>
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      <Badge
                        variant="gray"
                        size="sm"
                      >
                        {user.rol}
                      </Badge>
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      <label className="relative inline-flex items-center cursor-pointer" title={user.activo ? 'Activo' : 'Inactivo'}>
                        <input
                          type="checkbox"
                          checked={user.activo}
                          className="sr-only peer"
                          onChange={() => handleToggleStatus(user)}
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-red-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
                      </label>
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap">
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
            className="fixed inset-0 animate-in fade-in duration-150 z-40 transition-opacity"
            style={{ backgroundColor: 'rgba(36, 26, 25, 0.5)' }}
            onClick={() => !formLoading && setShowDrawer(false)}
          />
          <div className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-white shadow-2xl z-50 overflow-y-auto transform transition-transform">
            <div className="bg-white text-ink border-b border-line px-5 py-3.5 flex items-center justify-between sticky top-0 z-10">
              <h2 className="text-xl font-semibold">{editingUser ? 'Editar Usuario' : 'Crear Nuevo Usuario'}</h2>
              <button
                onClick={() => !formLoading && setShowDrawer(false)}
                className="text-ink-muted hover:text-ink hover:bg-wash rounded-[10px] p-1"
                disabled={formLoading}
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-6">
              {formError && (
                <div className="p-3 bg-red-50 text-red-700 text-sm rounded-[10px] border border-red-200">
                  {formError}
                </div>
              )}

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Nombre Completo *
                </label>
                <input
                  type="text"
                  required
                  value={formData.nombre}
                  onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                  className="w-full px-3.5 py-2.5 border border-line-strong rounded-[10px] bg-white text-sm text-ink focus:outline-none focus:border-primary"
                  placeholder="e.g., Juan Carlos Pérez"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Correo Electrónico *
                </label>
                <input
                  type="email"
                  required
                  disabled={!!editingUser}
                  value={formData.correo}
                  onChange={(e) => setFormData({ ...formData, correo: e.target.value })}
                  className="w-full px-3.5 py-2.5 border border-line-strong rounded-[10px] bg-white text-sm text-ink focus:outline-none focus:border-primary disabled:bg-gray-100 disabled:text-gray-500"
                  placeholder="usuario@ufps.edu.co"
                />
                {editingUser && (
                  <p className="text-xs text-gray-400 mt-1">El correo no se puede modificar.</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Rol Asignado *
                </label>
                <select
                  required
                  value={formData.rol}
                  // HU-37: las cuentas de estudiante no cambian de rol
                  disabled={formData.rol === 'ESTUDIANTE'}
                  onChange={(e) => setFormData({ ...formData, rol: e.target.value })}
                  className="w-full px-3.5 py-2.5 border border-line-strong rounded-[10px] bg-white text-sm text-ink focus:outline-none focus:border-primary bg-white"
                >
                  <option value="DOCENTE">Docente</option>
                  <option value="DIRECTOR">Director Académico</option>
                  <option value="BIENESTAR">Personal de Bienestar</option>
                  <option value="ADMINISTRADOR">Administrador</option>
                  {formData.rol === 'ESTUDIANTE' && <option value="ESTUDIANTE">Estudiante</option>}
                </select>
              </div>

              {!editingUser && (
                <div className="bg-amber-50 border border-amber-200 p-4 rounded-[10px]">
                  <p className="text-sm text-amber-800 font-medium">Información sobre la contraseña</p>
                  <p className="text-xs text-amber-700 mt-1">
                    Al crear el usuario se genera una contraseña temporal que verás una sola vez. El usuario deberá cambiarla en su primer inicio de sesión.
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
