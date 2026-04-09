import { useParams, Link } from 'react-router';
import { ArrowLeft, CheckCircle, XCircle } from 'lucide-react';
import { Button } from '../components/ui/Button';

const errorRecords = [
  {
    rowNumber: 45,
    field: 'student_code',
    error: 'Formato de código de estudiante inválido',
    value: '123ABC',
  },
  {
    rowNumber: 128,
    field: 'gpa',
    error: 'Valor de promedio fuera de rango (0-5)',
    value: '6.2',
  },
  {
    rowNumber: 203,
    field: 'enrollment_date',
    error: 'Formato de fecha inválido',
    value: '32/13/2026',
  },
  {
    rowNumber: 267,
    field: 'course_code',
    error: 'Código de curso no existe en el catálogo',
    value: 'MAT-999',
  },
  {
    rowNumber: 312,
    field: 'credits',
    error: 'Créditos deben ser un entero positivo',
    value: '-2',
  },
  {
    rowNumber: 445,
    field: 'student_code',
    error: 'Código de estudiante duplicado en el lote',
    value: '1151234',
  },
  {
    rowNumber: 556,
    field: 'semester',
    error: 'Formato de semestre inválido',
    value: '2026-3',
  },
  {
    rowNumber: 678,
    field: 'grade',
    error: 'Valor de nota fuera de rango (0-5)',
    value: '5.8',
  },
  {
    rowNumber: 789,
    field: 'program_code',
    error: 'Código de programa no encontrado',
    value: 'ING-ZZZ',
  },
  {
    rowNumber: 890,
    field: 'email',
    error: 'Formato de correo inválido',
    value: 'student@invalid',
  },
  {
    rowNumber: 945,
    field: 'phone',
    error: 'El número de teléfono debe tener 10 dígitos',
    value: '123',
  },
  {
    rowNumber: 1023,
    field: 'cohort',
    error: 'Año de cohorte debe estar entre 2000-2030',
    value: '1999',
  },
  {
    rowNumber: 1150,
    field: 'status',
    error: 'Estado de estudiante inválido',
    value: 'UNKNOWN',
  },
  {
    rowNumber: 1267,
    field: 'gpa',
    error: 'El promedio no puede ser nulo para estudiantes activos',
    value: 'NULL',
  },
  {
    rowNumber: 1389,
    field: 'student_code',
    error: 'El código de estudiante ya existe en la base de datos',
    value: '1151567',
  },
];

export default function ImportLog() {
  const { id } = useParams();

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
          Detalles del Registro de Importación - Sesión #{id}
        </h1>

        <div className="grid grid-cols-4 gap-6">
          <div>
            <p className="text-sm text-gray-500 mb-1">Total Procesado</p>
            <p className="text-2xl font-bold text-gray-900">2,890</p>
          </div>
          <div>
            <p className="text-sm text-gray-500 mb-1">Exitosos</p>
            <div className="flex items-center gap-2">
               <CheckCircle className="w-5 h-5 text-green-600" />
               <p className="text-2xl font-bold text-green-600">2,875</p>
            </div>
          </div>
          <div>
            <p className="text-sm text-gray-500 mb-1">Errores</p>
            <div className="flex items-center gap-2">
              <XCircle className="w-5 h-5 text-red-600" />
              <p className="text-2xl font-bold text-red-600">15</p>
            </div>
          </div>
          <div>
            <p className="text-sm text-gray-500 mb-1">Fecha de Importación</p>
            <p className="text-lg font-semibold text-gray-900">2026-04-05</p>
            <p className="text-sm text-gray-500">09:15 AM</p>
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
                    {error.rowNumber}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <code className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                      {error.field}
                    </code>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">{error.error}</td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    <code className="px-2 py-1 bg-white border border-gray-200 rounded text-xs font-mono">
                      {error.value}
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
