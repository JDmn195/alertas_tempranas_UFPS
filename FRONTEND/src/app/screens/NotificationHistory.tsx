import { useState, useEffect } from 'react';
import { Badge } from '../components/ui/Badge';
import { Mail, Bell, CheckCircle, AlertCircle, Clock } from 'lucide-react';

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
      
      const response = await fetch(`${baseUrl}/api/alertas/notificaciones/historial/?${params.toString()}`);
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

  return (
    <div className="space-y-6">
      <div className="border-l-4 border-[#C8102E] pl-4">
        <h1 className="text-2xl font-bold text-gray-900">Historial de Notificaciones</h1>
        <p className="text-sm text-gray-600 mt-1">
          Auditoría de todas las comunicaciones enviadas por el sistema
        </p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex gap-4 mb-6">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Estado</label>
            <select 
              className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              value={filter.resultado}
              onChange={(e) => setFilter({...filter, resultado: e.target.value})}
            >
              <option value="">Todos los estados</option>
              <option value="exitoso">Exitoso</option>
              <option value="fallido">Fallido</option>
              <option value="reintento">Pendiente</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Canal</label>
            <select 
              className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              value={filter.canal}
              onChange={(e) => setFilter({...filter, canal: e.target.value})}
            >
              <option value="">Todos los canales</option>
              <option value="EMAIL">Email</option>
              <option value="INTERNA">Notificación Interna</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#C8102E] text-white">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase">Fecha</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase">Estudiante</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase">Destinatario</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase">Canal</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase">Resultado</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase">Detalle</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {isLoading ? (
                <tr><td colSpan={6} className="text-center py-10">Cargando historial...</td></tr>
              ) : history.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-10 text-gray-500">No hay registros de notificaciones.</td></tr>
              ) : (
                history.map((record) => (
                  <tr key={record.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                      {new Date(record.fecha_envio).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {record.estudiante}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      <div>{record.destinatario}</div>
                      <Badge variant="gray" size="sm">{record.rol_destinatario}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      {record.canal === 'EMAIL' ? (
                        <div className="flex items-center gap-1 text-sm text-gray-600">
                          <Mail className="w-4 h-4" /> Email
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 text-sm text-gray-600">
                          <Bell className="w-4 h-4" /> Interna
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
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
                    <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate" title={record.detalle_error}>
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
