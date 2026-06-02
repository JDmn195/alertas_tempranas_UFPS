import { useState, useEffect } from 'react';
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
import { apiFetch } from '../../services/apiFetch';

// ─── Interfaces ───────────────────────────────────────────────────────────────

interface RiskDistributionItem {
  semester: string;
  low: number;
  medium: number;
  high: number;
}

interface GpaTrendItem {
  cohort: string;
  gpa: number;
}

interface CriticalCourse {
  course: string;
  failureRate: number;
  enrolled: number;
  failed: number;
}

interface DashboardData {
  total_estudiantes_activos: number;
  porcentaje_riesgo: number;
  alertas_activas: number;
  cursos_alta_reprobacion: number;
  distribucion_riesgo: RiskDistributionItem[];
  tendencia_gpa: GpaTrendItem[];
  cursos_criticos: CriticalCourse[];
}

// ─── Componente ───────────────────────────────────────────────────────────────

export default function DirectorDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetchIndicadores = async () => {
      setLoading(true);
      setError(false);
      try {
        const baseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
        const res = await apiFetch(`${baseUrl}/api/academico/indicadores/`);
        if (!res.ok) {
          const errBody = await res.text();
          throw new Error(`HTTP ${res.status}: ${errBody}`);
        }
        const json: DashboardData = await res.json();
        setData(json);
      } catch (err) {
        console.error('Error al cargar indicadores del director:', err);
        setError(true);
      } finally {
        setLoading(false);
      }
    };
    fetchIndicadores();
  }, []);

  // ── Helpers de renderizado ────────────────────────────────────────────────

  const kpiValue = (value: number | undefined, formatter?: (v: number) => string) => {
    if (loading) {
      return (
        <span className="inline-block h-9 w-24 bg-white/30 rounded animate-pulse" />
      );
    }
    if (error || value === undefined) return '—';
    return formatter ? formatter(value) : value.toLocaleString('es-CO');
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="border-l-4 border-[#C8102E] pl-4">
        <h1 className="text-2xl font-bold text-gray-900">Panel Estratégico</h1>
        <p className="text-sm text-gray-600 mt-1">
          Analíticas académicas e indicadores de riesgo - Programa de Ingeniería de Sistemas
        </p>
      </div>

      {/* Banner de error de conexión */}
      {error && (
        <div className="px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2 text-sm text-amber-700">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>No se pudo conectar al servidor. Verifique que el backend esté en ejecución en <code className="font-mono text-xs bg-amber-100 px-1 rounded">localhost:8000</code>.</span>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-6">
        <div className="bg-[#C8102E] text-white rounded-lg p-6">
          <div className="flex items-start justify-between mb-4">
            <Users className="w-8 h-8 opacity-90" />
          </div>
          <p className="text-3xl font-bold mb-1">
            {kpiValue(data?.total_estudiantes_activos)}
          </p>
          <p className="text-sm opacity-90">Total de Estudiantes Activos</p>
        </div>

        <div className="bg-[#C8102E] text-white rounded-lg p-6">
          <div className="flex items-start justify-between mb-4">
            <TrendingUp className="w-8 h-8 opacity-90" />
          </div>
          <p className="text-3xl font-bold mb-1">
            {kpiValue(data?.porcentaje_riesgo, (v) => `${v.toFixed(1)}%`)}
          </p>
          <p className="text-sm opacity-90">Estudiantes en Riesgo</p>
        </div>

        <div className="bg-[#C8102E] text-white rounded-lg p-6">
          <div className="flex items-start justify-between mb-4">
            <AlertCircle className="w-8 h-8 opacity-90" />
          </div>
          <p className="text-3xl font-bold mb-1">
            {kpiValue(data?.alertas_activas)}
          </p>
          <p className="text-sm opacity-90">Total Alertas Activas</p>
        </div>

        <div className="bg-[#C8102E] text-white rounded-lg p-6">
          <div className="flex items-start justify-between mb-4">
            <BookX className="w-8 h-8 opacity-90" />
          </div>
          <p className="text-3xl font-bold mb-1">
            {kpiValue(data?.cursos_alta_reprobacion)}
          </p>
          <p className="text-sm opacity-90">Cursos Críticos (≥30% Reprobación)</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Risk distribution by semester */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Distribución de Riesgo por Semestre
          </h2>
          {loading ? (
            <div className="h-[300px] bg-gray-100 rounded animate-pulse" />
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data?.distribucion_riesgo ?? []}>
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
          )}
        </div>

        {/* GPA trend by cohort */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Tendencia Promedio Académico por Cohorte
          </h2>
          {loading ? (
            <div className="h-[300px] bg-gray-100 rounded animate-pulse" />
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={data?.tendencia_gpa ?? []}>
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
          )}
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
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5]'}>
                    {Array.from({ length: 5 }).map((_, j) => (
                      <td key={j} className="px-6 py-4">
                        <div className="h-4 bg-gray-200 rounded animate-pulse" style={{ width: `${50 + (j * 15) % 40}%` }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : (data?.cursos_criticos ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-gray-400 text-sm">
                    {error
                      ? 'No se pudo cargar la información. Verifique la conexión con el servidor.'
                      : 'No hay cursos con tasa de reprobación superior al 20%.'}
                  </td>
                </tr>
              ) : (
                (data?.cursos_criticos ?? []).map((course, index) => (
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
                            style={{ width: `${Math.min(course.failureRate, 100)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-xs text-gray-500">—</span>
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
