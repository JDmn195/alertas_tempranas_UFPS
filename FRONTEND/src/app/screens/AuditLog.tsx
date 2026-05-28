import { useState, useEffect } from 'react';
import { ShieldAlert, RefreshCw, Search, Calendar, Filter } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { apiFetch } from '../../services/apiFetch';

interface AuditRecord {
  id: number;
  usuario_nombre: string;
  usuario_correo: string;
  fecha_hora: string;
  tipo_accion: string;
  tipo_accion_display: string;
  detalle: string;
}

export default function AuditLog() {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const [filterAction, setFilterAction] = useState('');
  const [filterStartDate, setFilterStartDate] = useState('');
  const [filterEndDate, setFilterEndDate] = useState('');

  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchAuditLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filterAction) params.append('tipo_accion', filterAction);
      if (filterStartDate) params.append('fecha_inicio', filterStartDate);
      if (filterEndDate) params.append('fecha_fin', filterEndDate);

      const res = await apiFetch(`${baseUrl}/api/usuarios/auditoria/?${params.toString()}`);
      if (!res.ok) throw new Error('Error al cargar registros de auditoría');
      
      const data = await res.json();
      setRecords(data.registros || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditLogs();
  }, [filterAction, filterStartDate, filterEndDate]);

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString('es-CO', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    });
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="border-l-4 border-[#C8102E] pl-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Registro de Auditoría</h1>
          <p className="text-sm text-gray-600 mt-1">
            Monitoreo y trazabilidad de las acciones críticas del sistema
          </p>
        </div>
        <Button variant="outline" onClick={fetchAuditLogs}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Actualizar
        </Button>
      </div>

      {/* Filtros */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Tipo de Acción
            </label>
            <select
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm bg-white"
            >
              <option value="">Todas las acciones</option>
              <option value="CREAR_USUARIO">Crear Usuario</option>
              <option value="EDITAR_ROL">Editar Rol</option>
              <option value="DESACTIVAR_USUARIO">Desactivar Usuario</option>
              <option value="IMPORTACION">Importación de Datos</option>
              <option value="CREAR_REGLA">Crear Regla</option>
              <option value="MODIFICAR_REGLA">Modificar Regla</option>
              <option value="DESACTIVAR_REGLA">Desactivar Regla</option>
              <option value="GENERAR_ALERTAS">Generar Alertas</option>
              <option value="CERRAR_ALERTA">Cerrar Alerta</option>
              <option value="REGISTRAR_INTERVENCION">Registrar Intervención</option>
              <option value="CONCLUIR_INTERVENCION">Concluir Intervención</option>
              <option value="LOGIN">Inicio de Sesión</option>
              <option value="ACCESO_DENEGADO">Acceso Denegado (403)</option>
            </select>
          </div>
          
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Fecha Inicio
            </label>
            <input
              type="date"
              value={filterStartDate}
              onChange={(e) => setFilterStartDate(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>

          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Fecha Fin
            </label>
            <input
              type="date"
              value={filterEndDate}
              onChange={(e) => setFilterEndDate(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-lg border border-red-200 flex items-center gap-2">
          <ShieldAlert className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Tabla */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 text-gray-600 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider">
                  Fecha y Hora
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider">
                  Usuario
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider">
                  Acción
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider">
                  Detalle
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading && records.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-gray-500">
                    Cargando registros...
                  </td>
                </tr>
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-gray-500">
                    Sin registros para los filtros seleccionados.
                  </td>
                </tr>
              ) : (
                records.map((record) => (
                  <tr key={record.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 text-sm text-gray-600 whitespace-nowrap">
                      {formatDate(record.fecha_hora)}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      <div className="font-medium">{record.usuario_nombre}</div>
                      <div className="text-xs text-gray-500">{record.usuario_correo}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                        record.tipo_accion === 'ACCESO_DENEGADO' ? 'bg-red-100 text-red-800' :
                        record.tipo_accion.includes('CREAR') ? 'bg-green-100 text-green-800' :
                        record.tipo_accion.includes('DESACTIVAR') ? 'bg-orange-100 text-orange-800' :
                        'bg-blue-100 text-blue-800'
                      }`}>
                        {record.tipo_accion_display}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {record.detalle || '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
