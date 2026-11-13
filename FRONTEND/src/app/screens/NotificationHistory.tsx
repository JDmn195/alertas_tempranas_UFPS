import { useState, useEffect } from 'react';
import { CintaIndicadores, EncabezadoPagina } from '../components/Panel';
import { Badge } from '../components/ui/Badge';
import { Mail, Bell, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import { apiFetch } from '../../services/apiFetch';

import { CargandoFilas, EstadoVacio } from '../components/Estados';
export default function NotificationHistory() {
  const [history, setHistory] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState({
    resultado: '',
    canal: ''
  });

  const fetchHistory = async () => {
    setIsLoading(true);
    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const params = new URLSearchParams();
      if (filter.resultado) params.append('resultado', filter.resultado);
      if (filter.canal) params.append('canal', filter.canal);
      
      const response = await apiFetch(`${baseUrl}/api/alertas/notificaciones/historial/?${params.toString()}`);
      const data = await response.json();
      setHistory(data.historial || []);
    } catch (error) {
      console.error("Error fetching history:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [filter]);

  const campo = 'h-10 px-3.5 border border-line-strong rounded-[10px] bg-white text-sm text-ink';
  const exitosos = history.filter((r) => r.resultado === 'exitoso').length;
  const fallidos = history.filter((r) => r.resultado === 'fallido').length;
  const pendientes = history.length - exitosos - fallidos;
  const hayFiltros = Boolean(filter.resultado || filter.canal);

  return (
    <div className="space-y-5">
      <EncabezadoPagina
        titulo="Historial de Notificaciones"
        detalle="Auditoría de todas las comunicaciones enviadas por el sistema."
      />

      <CintaIndicadores
        cargando={isLoading && history.length === 0}
        indicadores={[
          { etiqueta: 'Envíos', valor: history.length, detalle: hayFiltros ? 'Con los filtros aplicados' : 'Más recientes' },
          { etiqueta: 'Exitosos', valor: exitosos, tono: 'bien' },
          { etiqueta: 'Fallidos', valor: fallidos, tono: fallidos > 0 ? 'alerta' : undefined, detalle: fallidos > 0 ? 'Revisa el detalle del error' : undefined },
          { etiqueta: 'Pendientes', valor: pendientes, tono: pendientes > 0 ? 'aviso' : undefined },
        ]}
      />

      <div className="bg-white border border-line rounded-[14px] p-3 sm:p-4">
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="hist-estado" className="block text-sm font-medium text-ink-muted mb-1.5">Estado</label>
            <select
              id="hist-estado"
              className={`${campo} w-full`}
              value={filter.resultado}
              onChange={(e) => setFilter({...filter, resultado: e.target.value})}
            >
              <option value="">Todos los estados</option>
              <option value="exitoso">Exitoso</option>
              <option value="fallido">Fallido</option>
              <option value="reintento">Pendiente</option>
            </select>
          </div>
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="hist-canal" className="block text-sm font-medium text-ink-muted mb-1.5">Canal</label>
            <select
              id="hist-canal"
              className={`${campo} w-full`}
              value={filter.canal}
              onChange={(e) => setFilter({...filter, canal: e.target.value})}
            >
              <option value="">Todos los canales</option>
              <option value="EMAIL">Email</option>
              <option value="INTERNA">Notificación Interna</option>
            </select>
          </div>
          {hayFiltros && (
            <button type="button" onClick={() => setFilter({ resultado: '', canal: '' })} className="h-10 px-3 text-sm font-medium text-primary rounded-[10px] hover:bg-primary-tint">
              Limpiar filtros
            </button>
          )}
        </div>
      </div>

      <div className="bg-white border border-line rounded-[14px] overflow-hidden">
        <div className="border-b border-line px-5 py-4">
          <h2 className="text-base font-semibold text-ink">{isLoading && history.length === 0 ? 'Cargando...' : `${history.length} envío${history.length !== 1 ? 's' : ''}`}</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="tabular-nums w-full min-w-[760px]">
            <thead className="bg-paper text-ink-soft border-b border-line">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold">Fecha</th>
                <th className="px-5 py-3 text-left text-xs font-semibold">Estudiante</th>
                <th className="px-5 py-3 text-left text-xs font-semibold">Destinatario</th>
                <th className="px-5 py-3 text-left text-xs font-semibold">Canal</th>
                <th className="px-5 py-3 text-left text-xs font-semibold">Resultado</th>
                <th className="px-5 py-3 text-left text-xs font-semibold">Detalle</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {isLoading ? (
                <CargandoFilas columnas={6} texto="Cargando historial..." />
              ) : history.length === 0 ? (
                <tr><td colSpan={6}><EstadoVacio titulo="No hay registros de notificaciones." detalle="Cuando el sistema envíe avisos a los usuarios, los verás aquí." /></td></tr>
              ) : (
                history.map((record) => (
                  <tr key={record.id} className="hover:bg-paper">
                    <td className="px-5 py-3.5 text-sm text-ink-muted whitespace-nowrap">
                      {new Date(record.fecha_envio).toLocaleString()}
                    </td>
                    <td className="px-5 py-3.5 text-sm font-medium text-ink">
                      {record.estudiante}
                    </td>
                    <td className="px-5 py-3.5 text-sm text-ink-muted">
                      <div>{record.destinatario}</div>
                      <Badge variant="gray" size="sm">{record.rol_destinatario}</Badge>
                    </td>
                    <td className="px-5 py-3.5">
                      {record.canal === 'EMAIL' ? (
                        <div className="flex items-center gap-1 text-sm text-ink-muted">
                          <Mail className="w-4 h-4" /> Email
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 text-sm text-ink-muted">
                          <Bell className="w-4 h-4" /> Interna
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      {record.resultado === 'exitoso' ? (
                        <Badge variant="success" size="sm">
                          <CheckCircle className="w-3 h-3 mr-1" /> Exitoso
                        </Badge>
                      ) : record.resultado === 'fallido' ? (
                        <Badge variant="error" size="sm">
                          <AlertCircle className="w-3 h-3 mr-1" /> Fallido
                        </Badge>
                      ) : (
                        <Badge variant="medium" size="sm">
                          <Clock className="w-3 h-3 mr-1" /> Pendiente
                        </Badge>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-ink-muted max-w-xs truncate" title={record.detalle_error}>
                      {record.detalle_error || '-'}
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
