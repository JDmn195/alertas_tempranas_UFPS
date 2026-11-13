import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router';
import { EncabezadoPagina } from '../components/Panel';
import { Button } from '../components/ui/Button';
import { Users, TrendingUp, AlertCircle, BookX, RefreshCw, ArrowUpRight } from 'lucide-react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
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

// ─── Estilo común de gráficos ────────────────────────────────────────────────

const COLOR_ALTO = '#B02A2B';
const COLOR_MEDIO = '#C98A12';
const COLOR_BAJO = '#2F8F6B';

function TooltipLimpio({ active, payload, label }: { active?: boolean; payload?: any[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-[10px] border border-line bg-white px-3 py-2 text-sm">
      <p className="font-semibold text-ink mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2 text-ink-soft tabular-nums">
          <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: p.color }} />
          {p.name}: <span className="font-semibold text-ink">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

function SinDatos({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-[280px] flex items-center justify-center text-center px-6 text-sm text-ink-muted rounded-[10px] bg-paper border border-dashed border-line-strong">
      {children}
    </div>
  );
}

const entrada = (i: number) => ({ animationDelay: `${i * 70}ms`, animationFillMode: 'backwards' as const });

// ─── Componente ───────────────────────────────────────────────────────────────

export default function DirectorDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refreshing, setRefreshing] = useState(false); // 5.1

  const fetchIndicadores = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
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
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchIndicadores();
  }, [fetchIndicadores]);

  // ── Helpers de renderizado ────────────────────────────────────────────────

  const kpiValue = (value: number | undefined, formatter?: (v: number) => string) => {
    if (loading) {
      return <span className="inline-block h-9 w-24 bg-line rounded-[10px] animate-pulse align-middle" />;
    }
    if (error || value === undefined) return '—';
    return formatter ? formatter(value) : value.toLocaleString('es-CO');
  };

  const pctRiesgo = Math.min(Math.max(data?.porcentaje_riesgo ?? 0, 0), 100);
  const tarjeta = '';

  return (
    <div className="space-y-5">
      <EncabezadoPagina
        titulo="Panel Estratégico"
        detalle="Analíticas académicas e indicadores de riesgo - Programa de Ingeniería de Sistemas"
      >
        <Button
          variant="outline"
          onClick={() => fetchIndicadores(true)}
          disabled={loading || refreshing}
          title="Actualizar datos del panel"
          className="gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} aria-hidden="true" />
          {refreshing ? 'Actualizando...' : 'Actualizar datos'}
        </Button>
      </EncabezadoPagina>

      {/* Banner de error de conexión */}
      {error && (
        <div role="alert" className="px-4 py-3 bg-amber-50 border border-amber-200 rounded-[10px] flex items-center gap-2 text-sm text-amber-800">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <div>No se pudo conectar al servidor. Intente nuevamente en unos minutos. Si el problema continúa, comuníquese con el administrador.</div>
        </div>
      )}

      {/* El dato que guía al programa: qué parte de los estudiantes está en riesgo */}
      <section className="bg-white border border-line rounded-[14px] grid lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]" aria-label="Indicadores del programa">
        <div className="p-5 sm:p-7">
          <p className="text-sm font-medium text-ink-muted">Estudiantes en Riesgo</p>
          <p className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-6xl font-semibold text-ink leading-none tracking-[-0.04em]">
              {loading ? <span className="inline-block h-14 w-36 bg-wash rounded-[10px] animate-pulse align-middle" /> : kpiValue(data?.porcentaje_riesgo, (v) => `${v.toFixed(1)}%`)}
            </span>
            <span className="text-ink-muted">de los estudiantes activos tiene riesgo alto o medio</span>
          </p>
          <div className="mt-6" aria-hidden="true">
            <div className="h-3 rounded-full bg-wash overflow-hidden">
              <div className="h-full rounded-full bg-riesgo-critico transition-[width] duration-500 ease-out" style={{ width: loading ? '0%' : `${pctRiesgo}%` }} />
            </div>
            <div className="mt-1.5 flex justify-between text-xs text-ink-muted tabular-nums">
              <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
            </div>
          </div>
        </div>

        <dl className="border-t lg:border-t-0 lg:border-l border-line divide-y divide-line">
          <div className="px-5 sm:px-6 py-4 flex items-center justify-between gap-4">
            <dt className="flex items-center gap-2.5 text-sm text-ink-soft">
              <Users className="w-4 h-4 text-ink-faint" aria-hidden="true" />
              Total de Estudiantes Activos
            </dt>
            <dd className="text-2xl font-semibold text-ink">{kpiValue(data?.total_estudiantes_activos)}</dd>
          </div>
          <Link to="/dashboard/alerts" className="group px-5 sm:px-6 py-4 flex items-center justify-between gap-4 hover:bg-paper">
            <dt className="flex items-center gap-2.5 text-sm text-ink-soft">
              <AlertCircle className="w-4 h-4 text-riesgo-critico" aria-hidden="true" />
              Total Alertas Activas
              <ArrowUpRight className="w-4 h-4 text-ink-faint group-hover:text-ink" aria-hidden="true" />
            </dt>
            <dd className="text-2xl font-semibold text-ink">{kpiValue(data?.alertas_activas)}</dd>
          </Link>
          <Link to="/dashboard/courses" className="group px-5 sm:px-6 py-4 flex items-center justify-between gap-4 hover:bg-paper lg:rounded-br-[14px]">
            <dt className="flex items-center gap-2.5 text-sm text-ink-soft">
              <BookX className="w-4 h-4 text-riesgo-alto" aria-hidden="true" />
              Cursos Críticos (≥30% Reprobación)
              <ArrowUpRight className="w-4 h-4 text-ink-faint group-hover:text-ink" aria-hidden="true" />
            </dt>
            <dd className="text-2xl font-semibold text-ink">{kpiValue(data?.cursos_alta_reprobacion)}</dd>
          </Link>
        </dl>
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Distribución de riesgo por semestre */}
        <div className="bg-white rounded-[14px] border border-line p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Distribución de Riesgo por Semestre</h2>
          {loading ? (
            <div className="h-[280px] bg-wash rounded-[10px] animate-pulse" />
          ) : (data?.distribucion_riesgo ?? []).length === 0 ? (
            <SinDatos>Todavía no hay estudiantes clasificados por riesgo. Cuando se importen historiales, aquí verás cómo se reparten por semestre.</SinDatos>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={data?.distribucion_riesgo ?? []} barCategoryGap="30%">
                <CartesianGrid strokeDasharray="3 3" stroke="#F3E4E1" vertical={false} />
                <XAxis dataKey="semester" stroke="#9C8D8A" tickLine={false} axisLine={{ stroke: '#E8D6D2' }} style={{ fontSize: '12px' }} />
                <YAxis stroke="#9C8D8A" tickLine={false} axisLine={false} allowDecimals={false} style={{ fontSize: '12px' }} />
                <Tooltip content={<TooltipLimpio />} cursor={{ fill: '#FAF1EF' }} />
                <Legend iconType="square" wrapperStyle={{ fontSize: '12px', paddingTop: 8 }} />
                <Bar dataKey="high" stackId="a" fill={COLOR_ALTO} name="Riesgo Alto" />
                <Bar dataKey="medium" stackId="a" fill={COLOR_MEDIO} name="Riesgo Medio" />
                <Bar dataKey="low" stackId="a" fill={COLOR_BAJO} name="Riesgo Bajo" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Tendencia del promedio por cohorte */}
        <div className="bg-white rounded-[14px] border border-line p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Tendencia Promedio Académico por Cohorte</h2>
          {loading ? (
            <div className="h-[280px] bg-wash rounded-[10px] animate-pulse" />
          ) : (data?.tendencia_gpa ?? []).length === 0 ? (
            <SinDatos>Aún no hay promedios por cohorte. Aparecerán al registrar notas de al menos un periodo.</SinDatos>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={data?.tendencia_gpa ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F3E4E1" vertical={false} />
                <XAxis dataKey="cohort" stroke="#9C8D8A" tickLine={false} axisLine={{ stroke: '#E8D6D2' }} style={{ fontSize: '12px' }} />
                <YAxis domain={[0, 5]} stroke="#9C8D8A" tickLine={false} axisLine={false} style={{ fontSize: '12px' }} />
                <Tooltip content={<TooltipLimpio />} cursor={{ stroke: '#D5BFBA' }} />
                <Line
                  type="monotone"
                  dataKey="gpa"
                  name="Promedio"
                  stroke="#C8102E"
                  strokeWidth={2}
                  dot={{ fill: '#fff', stroke: '#C8102E', strokeWidth: 2, r: 4 }}
                  activeDot={{ r: 6, fill: '#C8102E', stroke: '#fff', strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Cursos críticos */}
      <div className="bg-white rounded-[14px] border border-line overflow-hidden">
        <div className="border-b border-line px-5 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Cursos Críticos - Alta Tasa de Reprobación</h2>
            <p className="text-sm text-gray-500 mt-0.5">Cursos que requieren atención e intervención inmediata</p>
          </div>
          <Link to="/dashboard/courses" className="text-sm font-semibold text-primary hover:underline">Ver todos los cursos</Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px]">
            <thead className="bg-paper text-ink-soft border-b border-line">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold">Nombre del Curso</th>
                <th className="px-6 py-3 text-left text-xs font-semibold">Inscritos</th>
                <th className="px-6 py-3 text-left text-xs font-semibold">Reprobados</th>
                <th className="px-6 py-3 text-left text-xs font-semibold">Tasa de Reprobación</th>
                <th className="px-6 py-3 text-left text-xs font-semibold">Tendencia</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-wash">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 5 }).map((_, j) => (
                      <td key={j} className="px-6 py-4">
                        <div className="h-4 bg-line rounded animate-pulse" style={{ width: `${50 + (j * 15) % 40}%` }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : (data?.cursos_criticos ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-sm text-ink-muted">
                    {error
                      ? 'No se pudo cargar la información. Verifique la conexión con el servidor.'
                      : 'No hay cursos con tasa de reprobación superior al 20%.'}
                  </td>
                </tr>
              ) : (
                (data?.cursos_criticos ?? []).map((course, index) => {
                  const critico = course.failureRate >= 30;
                  const color = critico ? '#B02A2B' : '#C98A12';
                  return (
                    <tr key={index} className="transition-colors hover:bg-paper">
                      <td className="px-6 py-3.5 text-sm font-semibold text-ink">{course.course}</td>
                      <td className="px-6 py-3.5 whitespace-nowrap text-sm text-ink-soft tabular-nums">{course.enrolled}</td>
                      <td className="px-6 py-3.5 whitespace-nowrap text-sm text-ink-soft tabular-nums">{course.failed}</td>
                      <td className="px-6 py-3.5 whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold tabular-nums ${critico ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-700'}`}>
                            {course.failureRate}%
                          </span>
                          <div className="flex-1 max-w-[120px] bg-wash rounded-full h-2 overflow-hidden">
                            <div className="h-2 rounded-full transition-all duration-700" style={{ width: `${Math.min(course.failureRate, 100)}%`, background: color }} />
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-3.5 whitespace-nowrap">
                        <span className="text-xs text-gray-500">—</span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
