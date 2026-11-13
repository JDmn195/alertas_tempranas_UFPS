import { useState, useEffect } from 'react';
import { ShieldAlert, RefreshCw, Search, Calendar, Filter } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { apiFetch } from '../../services/apiFetch';

import { CargandoBloque, EstadoVacio } from '../components/Estados';
import { CintaIndicadores, EncabezadoPagina } from '../components/Panel';
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

  const campo = 'h-10 px-3.5 border border-line-strong rounded-[10px] bg-white text-sm text-ink';
  const hayFiltros = Boolean(filterAction || filterStartDate || filterEndDate);
  const denegados = records.filter((r) => r.tipo_accion === 'ACCESO_DENEGADO').length;
  const usuariosDistintos = new Set(records.map((r) => r.usuario_correo)).size;

  return (
    <div className="space-y-5">
      <EncabezadoPagina
        titulo="Registro de Auditoría"
        detalle="Trazabilidad de las acciones críticas del sistema: quién hizo qué y cuándo."
      >
        <Button variant="outline" onClick={fetchAuditLogs}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Actualizar
        </Button>
      </EncabezadoPagina>

      <CintaIndicadores
        cargando={loading && records.length === 0}
        indicadores={[
          { etiqueta: 'Registros', valor: records.length, detalle: hayFiltros ? 'Con los filtros aplicados' : 'Más recientes' },
          { etiqueta: 'Accesos denegados', valor: denegados, tono: denegados > 0 ? 'alerta' : undefined, detalle: 'Intentos sin permiso (403)' },
          { etiqueta: 'Usuarios distintos', valor: usuariosDistintos, detalle: 'Con actividad en la lista' },
        ]}
      />

      {/* Filtros */}
      <div className="bg-white border border-line rounded-[14px] p-3 sm:p-4">
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="auditoria-accion" className="block text-sm font-medium text-ink-muted mb-1.5">
              Tipo de acción
            </label>
            <select
              id="auditoria-accion"
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              className={`${campo} w-full`}
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
              <option value="CREAR_CUENTA_ESTUDIANTE">Crear Cuenta de Estudiante</option>
              <option value="ASOCIAR_CUENTA_ESTUDIANTE">Asociar Cuenta de Estudiante</option>
              <option value="SOLICITAR_ACOMPANAMIENTO">Solicitar Acompañamiento</option>
              <option value="CANCELAR_SOLICITUD">Cancelar Solicitud de Acompañamiento</option>
              <option value="GESTIONAR_SOLICITUD">Gestionar Solicitud de Acompañamiento</option>
            </select>
          </div>
          
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="auditoria-desde" className="block text-sm font-medium text-ink-muted mb-1.5">
              Desde
            </label>
            <input
              id="auditoria-desde"
              type="date"
              value={filterStartDate}
              onChange={(e) => setFilterStartDate(e.target.value)}
              className={`${campo} w-full`}
            />
          </div>

          <div className="flex-1 min-w-[200px]">
            <label htmlFor="auditoria-hasta" className="block text-sm font-medium text-ink-muted mb-1.5">
              Hasta
            </label>
            <input
              id="auditoria-hasta"
              type="date"
              value={filterEndDate}
              onChange={(e) => setFilterEndDate(e.target.value)}
              className={`${campo} w-full`}
            />
          </div>

          {hayFiltros && (
            <button
              type="button"
              onClick={() => { setFilterAction(''); setFilterStartDate(''); setFilterEndDate(''); }}
              className="h-10 px-3 text-sm font-medium text-primary rounded-[10px] hover:bg-primary-tint"
            >
              Limpiar filtros
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-[10px] border border-red-200 flex items-center gap-2">
          <ShieldAlert className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Tabla */}
      <div className="bg-white border border-line rounded-[14px] overflow-hidden">
        <div className="border-b border-line px-5 py-4">
          <h2 className="text-base font-semibold text-ink">
            {loading && records.length === 0 ? 'Cargando...' : `${records.length} registro${records.length !== 1 ? 's' : ''}`}
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="tabular-nums w-full min-w-[720px]">
            <thead className="bg-paper text-ink-soft border-b border-line">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold">Fecha y hora</th>
                <th className="px-5 py-3 text-left text-xs font-semibold">Usuario</th>
                <th className="px-5 py-3 text-left text-xs font-semibold">Acción</th>
                <th className="px-5 py-3 text-left text-xs font-semibold">Detalle</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading && records.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-6"><CargandoBloque texto="Cargando registros..." filas={5} /></td>
                </tr>
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={4}><EstadoVacio titulo="Sin registros para los filtros seleccionados." detalle="Amplía el rango de fechas o quita algún filtro." /></td>
                </tr>
              ) : (
                records.map((record) => (
                  <tr key={record.id} className="hover:bg-paper transition-colors">
                    <td className="px-5 py-3.5 text-sm text-ink-muted whitespace-nowrap">
                      {formatDate(record.fecha_hora)}
                    </td>
                    <td className="px-5 py-3.5 text-sm text-ink">
                      <div className="font-medium">{record.usuario_nombre}</div>
                      <div className="text-xs text-ink-muted">{record.usuario_correo}</div>
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                        record.tipo_accion === 'ACCESO_DENEGADO' ? 'bg-riesgo-critico text-white' : 'bg-wash text-ink-soft'
                      }`}>
                        {record.tipo_accion_display}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-sm text-ink-muted">
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
