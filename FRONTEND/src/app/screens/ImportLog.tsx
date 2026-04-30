import { useParams, Link } from 'react-router';
import { useState, useEffect } from 'react';
import { ArrowLeft, CheckCircle, XCircle } from 'lucide-react';
import { Button } from '../components/ui/Button';


export default function ImportLog() {
  const { id } = useParams();
  const [logData, setLogData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchLog = async () => {
      try {
        const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const response = await fetch(`${baseUrl}/api/academico/bitacora/${id}/`);
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
        <div className="w-12 h-12 border-4 border-[#C8102E] border-t-transparent rounded-full animate-spin mb-4"></div>
        <p className="text-gray-600 font-medium">Cargando detalles del log...</p>
      </div>
    );
  }

  if (!logData) {
    return (
      <div className="p-10 text-center">
        <h2 className="text-xl font-bold text-gray-900">Bitácora no encontrada</h2>
        <Link to="/dashboard/admin/import" className="text-[#C8102E] hover:underline mt-4 inline-block">
          Volver al módulo de importación
        </Link>
      </div>
    );
  }

  const errorRecords = logData.detalles_errores || [];

  return (
    <div className="space-y-6">
      {/* Back button */}
      <Link to="/dashboard/admin/import">
        <Button variant="secondary" size="sm">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Volver al Módulo de Importación
        </Button>
      </Link>

      {/* Summary card with red accent */}
      <div className="bg-white rounded-lg border border-gray-200 border-l-4 border-l-[#C8102E] p-6">
        <h1 className="text-xl font-bold text-gray-900 mb-4">
          Detalles de Importación - {logData.archivo_nombre}
        </h1>

        <div className="grid grid-cols-4 gap-6">
          <div>
            <p className="text-sm text-gray-500 mb-1">Total Procesado</p>
            <p className="text-2xl font-bold text-gray-900">{logData.total_procesados.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500 mb-1">Exitosos</p>
            <div className="flex items-center gap-2">
               <CheckCircle className="w-5 h-5 text-green-600" />
               <p className="text-2xl font-bold text-green-600">{(logData.total_procesados - logData.total_errores).toLocaleString()}</p>
            </div>
          </div>
          <div>
            <p className="text-sm text-gray-500 mb-1">Errores</p>
            <div className="flex items-center gap-2">
              <XCircle className="w-5 h-5 text-red-600" />
              <p className="text-2xl font-bold text-red-600">{logData.total_errores.toLocaleString()}</p>
            </div>
          </div>
          <div>
            <p className="text-sm text-gray-500 mb-1">Fecha de Importación</p>
            <p className="text-lg font-semibold text-gray-900">{logData.fecha.split(' ')[0]}</p>
            <p className="text-sm text-gray-500">{logData.fecha.split(' ')[1]}</p>
          </div>
        </div>
      </div>

      {/* Error details table */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Detalles del Error</h2>
          <p className="text-sm text-gray-500 mt-1">
            Registros que fallaron la validación durante la importación
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#C8102E] text-white">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Número de Fila
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Campo
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Descripción del Error
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Valor Encontrado
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {errorRecords.map((error, index) => (
                <tr
                  key={index}
                  className={`${index % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5]'} bg-[#FDECEA]`}
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {error.fila || 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <code className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                      {error.campo || 'General'}
                    </code>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">{error.mensaje || error.error}</td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    <code className="px-2 py-1 bg-white border border-gray-200 rounded text-xs font-mono">
                      {error.valor || error.value || 'N/A'}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="border-t border-gray-200 px-6 py-4 bg-gray-50">
          <div className="flex justify-between items-center">
            <p className="text-sm text-gray-600">
              Mostrando {errorRecords.length} registros de error
            </p>
            <Button variant="outline" size="sm">
              Exportar Reporte de Errores
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
