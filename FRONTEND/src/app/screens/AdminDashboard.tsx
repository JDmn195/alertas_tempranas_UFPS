import { useState, useRef } from 'react';
import { Link } from 'react-router';
import { Upload, FileText, AlertCircle, CheckCircle } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

const importHistory = [
  {
    id: '1',
    date: '2026-04-07 14:30',
    reportType: 'Registros Académicos - Semestre 2026-1',
    totalRecords: 1250,
    errors: 0,
    status: 'success',
  },
  {
    id: '2',
    date: '2026-04-05 09:15',
    reportType: 'Datos de Matrícula de Estudiantes',
    totalRecords: 2890,
    errors: 15,
    status: 'error',
  },
  {
    id: '3',
    date: '2026-04-03 16:45',
    reportType: 'Reporte de Terminación de Cursos',
    totalRecords: 580,
    errors: 0,
    status: 'success',
  },
  {
    id: '4',
    date: '2026-04-01 11:20',
    reportType: 'Actualización Promedio - Todos los Programas',
    totalRecords: 3200,
    errors: 3,
    status: 'error',
  },
];

export default function AdminDashboard() {
  const [dragActive, setDragActive] = useState(false);
  const [importType, setImportType] = useState('general');
  const [validationStatus, setValidationStatus] = useState<'idle' | 'validating' | 'success' | 'error'>('idle');
  const [responseMessage, setResponseMessage] = useState<string>('');
  const [responseErrors, setResponseErrors] = useState<any[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const uploadFile = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    const endpointMap: Record<string, string> = {
      general: "import/students/",
      individual: "import/history/",
      courses: "import/offering/",
      teachers: "import/teachers/",
    };

    const endpoint = endpointMap[importType];

    if (!endpoint) {
      console.error("Tipo de importación inválido");
      setValidationStatus("error");
      return;
    }

    try {
      setValidationStatus("validating");
      setResponseMessage('');
      setResponseErrors([]);

      console.log("Endpoint usado:", endpoint);

      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(
        `${baseUrl}/api/academico/${endpoint}`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();
      console.log("Respuesta backend:", data);

      if (response.ok && (data.status === 'success' || data.status === 'parcial')) {
        setValidationStatus("success");
        setResponseMessage(data.mensaje || "Importación exitosa.");
        setResponseErrors([]);
      } else {
        setValidationStatus("error");
        setResponseMessage(data.mensaje || data.error || "La operación no se pudo completar o está pendiente.");
        setResponseErrors(data.errores || []);
      }
    } catch (error) {
      console.error(error);
      setValidationStatus("error");
      setResponseMessage("Error de conexión con el servidor.");
      setResponseErrors([]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      uploadFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = async (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    if (e.target.files && e.target.files[0]) {
      uploadFile(e.target.files[0]);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page header with red accent */}
      <div className="border-l-4 border-[#C8102E] pl-4">
        <h1 className="text-2xl font-bold text-gray-900">Módulo de Importación de Datos</h1>
        <p className="text-sm text-gray-600 mt-1">
          Importar datos académicos de la fuente institucional DIRPLAN
        </p>
      </div>

      {/* Upload area */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">Proceso de Importación y Validación</h2>

        {/* Formulario de configuración de importación */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            1. Seleccionar Tipo de Información
          </label>
          <select
            value={importType}
            onChange={(e) => setImportType(e.target.value)}
            className="w-full border border-gray-300 rounded-lg p-3 text-gray-900 focus:ring-[#C8102E] focus:border-[#C8102E] outline-none transition-colors"
          >
            <option value="general">Reporte General de Estudiantes (DIRPLAN)</option>
            <option value="individual">Reportes Individuales de Estudiantes</option>
            <option value="courses">Listado de Cursos</option>
            <option value="teachers">Listado de Docentes</option>
          </select>
          <p className="text-sm text-gray-500 mt-2">
            {importType === 'general' && 'Permite consolidar la información académica básica de los estudiantes desde la fuente DIRPLAN.'}
            {importType === 'individual' && 'Construye de manera detallada el historial académico completo de cada estudiante.'}
            {importType === 'courses' && 'Suministra la información requerida (cursos, asignaturas y docentes) para el análisis académico.'}
            {importType === 'teachers' && 'Profesores.'}
          </p>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            2. Carga y Validación Automática
          </label>
          {validationStatus === 'validating' ? (
            <div className="border border-blue-200 bg-blue-50 rounded-lg p-12 text-center flex flex-col items-center justify-center">
              <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-4"></div>
              <h3 className="text-lg font-medium text-blue-900">Validando calidad de los datos...</h3>
              <p className="text-sm text-blue-700 mt-1">Verificando formatos, integridad referencial y detectando valores nulos o inconsistentes.</p>
            </div>
          ) : validationStatus === 'success' ? (
            <div className="border border-green-200 bg-green-50 rounded-lg p-12 text-center flex flex-col items-center justify-center">
              <CheckCircle className="w-14 h-14 text-green-600 mb-4" />
              <h3 className="text-xl font-medium text-green-900">¡Importación Exitosa!</h3>
              <p className="text-sm text-green-700 mt-1">{responseMessage}</p>
              <button
                onClick={() => { setValidationStatus('idle'); setResponseMessage(''); setResponseErrors([]); }}
                className="mt-4 px-4 py-2 text-sm font-medium text-green-700 bg-green-100 rounded-lg hover:bg-green-200 transition-colors"
              >
                Importar otro archivo
              </button>
            </div>
          ) : validationStatus === 'error' ? (
            <div className="border border-red-200 bg-red-50 rounded-lg p-8 flex flex-col items-center justify-center">
              <AlertCircle className="w-14 h-14 text-[#C8102E] mb-4" />
              <h3 className="text-xl font-medium text-red-900">Error en la Importación</h3>
              <p className="text-sm text-red-700 mt-1 mb-4">{responseMessage}</p>
              {responseErrors.length > 0 && (
                <div className="w-full max-h-60 overflow-y-auto border border-red-200 rounded-lg bg-white">
                  <table className="w-full text-sm">
                    <thead className="bg-red-100 sticky top-0">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-red-800">Fila</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-red-800">Campo</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-red-800">Valor</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-red-800">Detalle</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-red-100">
                      {responseErrors.map((err: any, i: number) => (
                        <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-red-50'}>
                          <td className="px-3 py-2 text-red-700">{err.fila}</td>
                          <td className="px-3 py-2 text-red-700">{err.campo}</td>
                          <td className="px-3 py-2 text-red-700 font-mono">{err.valor}</td>
                          <td className="px-3 py-2 text-red-600">{err.mensaje}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <button
                onClick={() => { setValidationStatus('idle'); setResponseMessage(''); setResponseErrors([]); }}
                className="mt-4 px-4 py-2 text-sm font-medium text-red-700 bg-red-100 rounded-lg hover:bg-red-200 transition-colors"
              >
                Intentar de nuevo
              </button>
            </div>
          ) : (
            <div
              className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${dragActive
                ? 'border-[#C8102E] bg-red-50'
                : 'border-gray-300 hover:border-[#C8102E] hover:bg-gray-50'
                }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <div className="flex flex-col items-center">
                <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mb-4">
                  <Upload className="w-8 h-8 text-[#C8102E]" />
                </div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  Arrastra y suelta tu archivo aquí
                </h3>
                <p className="text-sm text-gray-500 mb-4">
                  Formatos soportados: CSV, Excel (.xlsx, .xls)
                </p>
                <label className="cursor-pointer">
                  <span className="inline-flex items-center px-4 py-2 border border-[#C8102E] rounded-lg text-sm font-medium text-[#C8102E] bg-white hover:bg-red-50 transition-colors">
                    Seleccionar Archivo
                  </span>
                  <input ref={fileInputRef} type="file" className="hidden" accept=".csv,.xlsx,.xls" onChange={handleFileSelect} />
                </label>
              </div>
            </div>
          )}
        </div>

        {validationStatus === 'idle' && (
          <div className="flex items-start gap-2 text-sm text-gray-800 bg-gray-50 p-4 rounded-lg border border-gray-200">
            <AlertCircle className="w-5 h-5 text-[#C8102E] flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block mb-1">Nota sobre Validación de Calidad</span>
              <p className="text-gray-600">
                El sistema aplicará reglas de calidad automáticas antes de consolidar la información.
                Cualquier inconsistencia será reportada en el historial de importación para su corrección. Tamaño máximo: 50MB.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Import history */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Historial de Importación</h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#C8102E] text-white">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Fecha y Hora
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Tipo de Reporte
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Total Registros
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Errores
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
              {importHistory.map((record, index) => (
                <tr
                  key={record.id}
                  className={index % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5]'}
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {record.date}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">{record.reportType}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {record.totalRecords.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {record.errors}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {record.status === 'success' ? (
                      <Badge variant="success" size="sm">
                        <CheckCircle className="w-3 h-3 mr-1" />
                        Éxito
                      </Badge>
                    ) : (
                      <Badge variant="error" size="sm">
                        <AlertCircle className="w-3 h-3 mr-1" />
                        Error
                      </Badge>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Link to={`/dashboard/admin/import-log/${record.id}`}>
                      <Button variant="outline" size="sm">
                        Ver Log
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
