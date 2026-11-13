import { useParams, Link } from 'react-router';
import { useState, useEffect } from 'react';
import { ArrowLeft } from 'lucide-react';
import { CintaIndicadores, EncabezadoPagina } from '../components/Panel';
import { Button } from '../components/ui/Button';
import { apiFetch } from '../../services/apiFetch';


export default function ImportLog() {
  const { id } = useParams();
  const [logData, setLogData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchLog = async () => {
      try {
        const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const response = await apiFetch(`${baseUrl}/api/academico/bitacora/${id}/`);
        const result = await response.json();
        if (result.status === 'success') {
          setLogData(result.data);
        }
      } catch (error) {
        console.error("Error fetching log:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchLog();
  }, [id]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-20">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
        <p className="text-ink-muted font-medium">Cargando detalles del log...</p>
      </div>
    );
  }

  if (!logData) {
    return (
      <div className="p-10 text-center">
        <h2 className="text-xl font-semibold text-ink">Bitácora no encontrada</h2>
        <Link to="/dashboard/admin/import" className="text-primary hover:underline mt-4 inline-block">
          Volver al módulo de importación
        </Link>
      </div>
    );
  }

  const errorRecords = logData.detalles_errores || [];

  return (
    <div className="space-y-5">
      <EncabezadoPagina
        titulo={<>Importación: <span className="break-all">{logData.archivo_nombre}</span></>}
        detalle={`Realizada el ${logData.fecha.split(' ')[0]} a las ${logData.fecha.split(' ')[1] ?? ''} por ${logData.usuario || 'un usuario desconocido'}.`}
      >
        <Link to="/dashboard/admin/import">
          <Button variant="secondary" size="sm">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Volver al Módulo de Importación
          </Button>
        </Link>
      </EncabezadoPagina>

      <CintaIndicadores
        indicadores={[
          { etiqueta: 'Total procesado', valor: logData.total_procesados.toLocaleString() },
          { etiqueta: 'Exitosos', valor: Math.max(0, logData.total_procesados - logData.total_errores).toLocaleString(), tono: 'bien' },
          { etiqueta: 'Errores', valor: logData.total_errores.toLocaleString(), tono: logData.total_errores > 0 ? 'alerta' : undefined },
        ]}
      />

      <div className="bg-white rounded-[14px] border border-line overflow-hidden">
        <div className="border-b border-line px-5 py-4">
          <h2 className="text-base font-semibold text-ink">Detalle de errores</h2>
          <p className="text-sm text-ink-muted mt-0.5">Registros que fallaron la validación durante la importación.</p>
        </div>

        {errorRecords.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-ink-muted">Esta importación no registró errores.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="tabular-nums w-full min-w-[640px]">
              <thead className="bg-paper text-ink-soft border-b border-line">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-semibold">Fila</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold">Campo</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold">Descripción del error</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold">Valor encontrado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {errorRecords.map((error: any, index: number) => (
                  <tr key={index} className="hover:bg-paper">
                    <td className="px-5 py-3.5 whitespace-nowrap text-sm font-medium text-ink">{error.fila || 'N/A'}</td>
                    <td className="px-5 py-3.5 whitespace-nowrap text-sm text-ink">
                      <code className="px-2 py-1 bg-wash rounded text-xs tabular-nums">{error.campo || 'General'}</code>
                    </td>
                    <td className="px-5 py-3.5 text-sm text-ink">{error.mensaje || error.error}</td>
                    <td className="px-5 py-3.5 text-sm text-ink">
                      <code className="px-2 py-1 bg-white border border-line rounded text-xs tabular-nums">{error.valor || error.value || 'N/A'}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="border-t border-line px-5 py-3 bg-paper">
          <p className="text-sm text-ink-muted">Mostrando {errorRecords.length} registro{errorRecords.length !== 1 ? 's' : ''} de error</p>
        </div>
      </div>
    </div>
  );
}
