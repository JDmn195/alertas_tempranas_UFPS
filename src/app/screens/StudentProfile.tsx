import { useParams, Link } from 'react-router';
import { ArrowLeft, TrendingDown, TrendingUp } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

const academicHistory = [
  { subject: 'Cálculo Diferencial', semester: '2024-1', grade: 4.2, status: 'Aprobado' },
  { subject: 'Física I', semester: '2024-1', grade: 3.8, status: 'Aprobado' },
  { subject: 'Programación I', semester: '2024-1', grade: 4.5, status: 'Aprobado' },
  { subject: 'Álgebra Lineal', semester: '2024-1', grade: 3.5, status: 'Aprobado' },
  { subject: 'Cálculo Integral', semester: '2024-2', grade: 3.2, status: 'Aprobado' },
  { subject: 'Física II', semester: '2024-2', grade: 2.8, status: 'Reprobado' },
  { subject: 'Programación II', semester: '2024-2', grade: 4.0, status: 'Aprobado' },
  { subject: 'Estructuras Discretas', semester: '2024-2', grade: 3.3, status: 'Aprobado' },
  { subject: 'Ecuaciones Diferenciales', semester: '2025-1', grade: 2.9, status: 'Reprobado' },
  { subject: 'Base de Datos I', semester: '2025-1', grade: 3.6, status: 'Aprobado' },
  { subject: 'Estructuras de Datos', semester: '2025-1', grade: 3.8, status: 'Aprobado' },
  { subject: 'Electiva I', semester: '2025-1', grade: 4.1, status: 'Aprobado' },
];

const gpaEvolution = [
  { semester: '2024-1', gpa: 4.0 },
  { semester: '2024-2', gpa: 3.3 },
  { semester: '2025-1', gpa: 3.6 },
  { semester: '2025-2', gpa: 3.4 },
  { semester: '2026-1', gpa: 3.2 },
];

export default function StudentProfile() {
  const { id } = useParams();

  return (
    <div className="space-y-6">
      {/* Back button */}
      <Link to="/dashboard/students">
        <Button variant="secondary" size="sm">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Volver a Estudiantes
        </Button>
      </Link>

      {/* Student header card - red background */}
      <div className="bg-[#C8102E] text-white rounded-lg p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold mb-2">María Alejandra Ramírez González</h1>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
              <div>
                <span className="opacity-90">Código del Estudiante:</span>
                <span className="font-semibold ml-2">1151234</span>
              </div>
              <div>
                <span className="opacity-90">Semestre Actual:</span>
                <span className="font-semibold ml-2">5to</span>
              </div>
              <div>
                <span className="opacity-90">Cohorte:</span>
                <span className="font-semibold ml-2">2024-1</span>
              </div>
              <div>
                <span className="opacity-90">Promedio Acumulado:</span>
                <span className="font-semibold ml-2">3.2</span>
              </div>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm opacity-90 mb-2">Nivel de Riesgo</p>
            <div className="inline-block">
              <div className="bg-white text-[#C8102E] px-4 py-2 rounded-lg border-2 border-white font-bold">
                ALTO
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Academic history table */}
        <div className="col-span-2 bg-white rounded-lg border border-gray-200">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Historial Académico</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[#C8102E] text-white">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                    Materia
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                    Semestre
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                    Nota
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                    Estado
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {academicHistory.map((record, index) => (
                  <tr
                    key={index}
                    className={index % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5]'}
                  >
                    <td className="px-6 py-4 text-sm text-gray-900">{record.subject}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {record.semester}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                      {record.grade.toFixed(1)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {record.status === 'Aprobado' ? (
                        <Badge variant="success" size="sm">
                          Aprobado
                        </Badge>
                      ) : (
                        <Badge variant="error" size="sm">
                          Reprobado
                        </Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* GPA evolution chart */}
        <div className="col-span-2 bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Evolución del Promedio</h2>
              <p className="text-sm text-gray-500 mt-1">Promedio acumulado por semestre</p>
            </div>
            <div className="flex items-center gap-2">
              <TrendingDown className="w-5 h-5 text-red-600" />
              <span className="text-sm font-medium text-red-600">Tendencia decreciente</span>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={gpaEvolution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="semester"
                stroke="#666"
                style={{ fontSize: '12px' }}
              />
              <YAxis
                domain={[0, 5]}
                stroke="#666"
                style={{ fontSize: '12px' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                }}
              />
              <Line
                type="monotone"
                dataKey="gpa"
                stroke="#C8102E"
                strokeWidth={3}
                dot={{ fill: '#C8102E', r: 5 }}
                activeDot={{ r: 7 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
