import { Users, TrendingUp, AlertCircle, BookX } from 'lucide-react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const riskDistribution = [
  { semester: '1er', low: 120, medium: 45, high: 15 },
  { semester: '2do', low: 110, medium: 50, high: 20 },
  { semester: '3er', low: 95, medium: 55, high: 30 },
  { semester: '4to', low: 85, medium: 48, high: 25 },
  { semester: '5to', low: 90, medium: 42, high: 22 },
  { semester: '6to+', low: 105, medium: 38, high: 18 },
];

const gpaTrend = [
  { cohort: '2022-1', gpa: 3.8 },
  { cohort: '2022-2', gpa: 3.7 },
  { cohort: '2023-1', gpa: 3.6 },
  { cohort: '2023-2', gpa: 3.5 },
  { cohort: '2024-1', gpa: 3.4 },
  { cohort: '2024-2', gpa: 3.5 },
  { cohort: '2025-1', gpa: 3.6 },
];

const criticalCourses = [
  { course: 'Cálculo Diferencial', failureRate: 32, enrolled: 180, failed: 58 },
  { course: 'Física II', failureRate: 28, enrolled: 150, failed: 42 },
  { course: 'Ecuaciones Diferenciales', failureRate: 25, enrolled: 120, failed: 30 },
  { course: 'Álgebra Lineal', failureRate: 22, enrolled: 165, failed: 36 },
  { course: 'Programación Avanzada', failureRate: 20, enrolled: 140, failed: 28 },
];

export default function DirectorDashboard() {
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="border-l-4 border-[#C8102E] pl-4">
        <h1 className="text-2xl font-bold text-gray-900">Panel Estratégico</h1>
        <p className="text-sm text-gray-600 mt-1">
          Analíticas académicas e indicadores de riesgo - Programa de Ingeniería de Sistemas
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-6">
        <div className="bg-[#C8102E] text-white rounded-lg p-6">
          <div className="flex items-start justify-between mb-4">
            <Users className="w-8 h-8 opacity-90" />
          </div>
          <p className="text-3xl font-bold mb-1">1,247</p>
          <p className="text-sm opacity-90">Total de Estudiantes Activos</p>
        </div>

        <div className="bg-[#C8102E] text-white rounded-lg p-6">
          <div className="flex items-start justify-between mb-4">
            <TrendingUp className="w-8 h-8 opacity-90" />
          </div>
          <p className="text-3xl font-bold mb-1">23.4%</p>
          <p className="text-sm opacity-90">Estudiantes en Riesgo</p>
        </div>

        <div className="bg-[#C8102E] text-white rounded-lg p-6">
          <div className="flex items-start justify-between mb-4">
            <AlertCircle className="w-8 h-8 opacity-90" />
          </div>
          <p className="text-3xl font-bold mb-1">87</p>
          <p className="text-sm opacity-90">Alertas Activas de Deserción</p>
        </div>

        <div className="bg-[#C8102E] text-white rounded-lg p-6">
          <div className="flex items-start justify-between mb-4">
            <BookX className="w-8 h-8 opacity-90" />
          </div>
          <p className="text-3xl font-bold mb-1">12</p>
          <p className="text-sm opacity-90">Cursos de Alta Tasa Reprobación</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Risk distribution by semester */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Distribución de Riesgo por Semestre
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={riskDistribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="semester" stroke="#666" style={{ fontSize: '12px' }} />
              <YAxis stroke="#666" style={{ fontSize: '12px' }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                }}
              />
              <Bar dataKey="high" stackId="a" fill="#C8102E" name="Riesgo Alto" />
              <Bar dataKey="medium" stackId="a" fill="#E57373" name="Riesgo Medio" />
              <Bar dataKey="low" stackId="a" fill="#FDECEA" name="Riesgo Bajo" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* GPA trend by cohort */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Tendencia Promedio Académico por Cohorte
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={gpaTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="cohort"
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

      {/* Critical courses table */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Cursos Críticos - Alta Tasa de Reprobación
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Cursos que requieren atención e intervención inmediata
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#C8102E] text-white">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Nombre del Curso
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Inscritos
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Reprobados
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Tasa de Reprobación
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Tendencia
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {criticalCourses.map((course, index) => (
                <tr
                  key={index}
                  className={index % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5]'}
                >
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">
                    {course.course}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {course.enrolled}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {course.failed}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-[#C8102E]">
                        {course.failureRate}%
                      </span>
                      <div className="flex-1 max-w-[120px] bg-gray-200 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-[#C8102E] h-2 rounded-full"
                          style={{ width: `${course.failureRate}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-xs text-gray-500">+3% vs sem. ant.</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Power BI embed placeholder */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="bg-[#C8102E] text-white px-6 py-3">
          <h2 className="text-lg font-semibold">Panel de Analíticas - Integración Power BI</h2>
        </div>
        <div className="aspect-video bg-gray-100 flex items-center justify-center">
          <div className="text-center">
            <div className="w-16 h-16 bg-white rounded-lg flex items-center justify-center mx-auto mb-3 shadow-sm">
              <svg
                className="w-8 h-8 text-[#C8102E]"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
            </div>
            <p className="text-sm font-medium text-gray-900">Panel Power BI</p>
            <p className="text-xs text-gray-500 mt-1">
              Analíticas integradas y visualizaciones avanzadas
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
