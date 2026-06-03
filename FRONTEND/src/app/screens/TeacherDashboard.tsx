import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router';
import {
  AlertTriangle, BookOpen, Users, ChevronLeft, ChevronRight,
  RefreshCw, X, TrendingUp, CheckCircle2, BarChart2,
  Activity, BookX, ExternalLink,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { apiFetch } from '../../services/apiFetch';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ─── Interfaces ───────────────────────────────────────────────────────────────

interface EstudianteRiesgo {
  codigo: string;
  nombre: string;
  curso: string;
  nivel_riesgo: 'high' | 'medium';
  alertas_activas: number;
}

interface CursoDoc {
  curso_id: number;
  materia: string;
  codigo: string;
  grupo: string;
  matriculados: number;
  reprobados: number;
  tasa_reprobacion: number;
  promedio_curso: number | null;
  en_riesgo: number;
  estado: string;
}

interface MateriaCritica {
  materia: string;
  reprobaciones: number;
}

interface DistribucionRiesgo {
  high: number;
  medium: number;
  low: number;
  unknown: number;
}

interface DashboardData {
  nombre_docente: string;
  cursos: CursoDoc[];
  estudiantes_en_riesgo: EstudianteRiesgo[];
  total_en_riesgo: number;
  total_alertas_activas: number;
  total_estudiantes: number;
  promedio_general: number | null;
  tasa_aprobacion: number;
  materias_criticas: MateriaCritica[];
  distribucion_riesgo: DistribucionRiesgo;
  cursos_criticos: number;
  page: number;
  pages: number;
  page_size: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const estadoBadgeClass = (estado: string) => {
  if (estado === 'CRÍTICO')         return 'bg-red-100 text-red-800 border border-red-200';
  if (estado === 'EN OBSERVACIÓN')  return 'bg-amber-100 text-amber-800 border border-amber-200';
  if (estado === 'ESTABLE')         return 'bg-green-100 text-green-800 border border-green-200';
  return 'bg-gray-100 text-gray-600 border border-gray-200';
};

// ─── Componente ───────────────────────────────────────────────────────────────

export default function TeacherDashboard() {
  const navigate = useNavigate();

  const userJson = localStorage.getItem('user');
  const user = userJson ? JSON.parse(userJson) : null;

  const [data, setData]     = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  // Modal: detalle de curso
  const [selectedCurso, setSelectedCurso]   = useState<CursoDoc | null>(null);
  const [modalStudents, setModalStudents]   = useState<EstudianteRiesgo[]>([]);
  const [modalPage, setModalPage]           = useState(1);
  const [modalPages, setModalPages]         = useState(1);
  const [modalTotal, setModalTotal]         = useState(0);
  const [modalLoading, setModalLoading]     = useState(false);
  const [modalError, setModalError]         = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fix 6.2: una sola request, el backend hace las queries optimizadas
      const res = await apiFetch(`${BASE_URL}/api/academico/teacher/dashboard/?page=1&page_size=100`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Error al cargar el panel del docente');
      }
      const json: DashboardData = await res.json();
      setData(json);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchCursoStudents = useCallback(async (cursoId: number, currentPage: number) => {
    setModalLoading(true);
    setModalError(null);
    try {
      const res = await apiFetch(
        `${BASE_URL}/api/academico/teacher/course/${cursoId}/students/?page=${currentPage}&page_size=5`
      );
      if (!res.ok) throw new Error('Error al cargar estudiantes del curso');
      const json = await res.json();
      setModalStudents(json.estudiantes);
      setModalPages(json.pages);
      setModalTotal(json.total);
    } catch (e: any) {
      setModalError(e.message);
    } finally {
      setModalLoading(false);
    }
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  useEffect(() => {
    if (selectedCurso) fetchCursoStudents(selectedCurso.curso_id, modalPage);
  }, [selectedCurso, modalPage, fetchCursoStudents]);

  // ─── KPI Cards ─────────────────────────────────────────────────────────────

  const kpis = [
    {
      label: 'Mis Estudiantes',
      value: data?.total_estudiantes ?? 0,
      icon: Users,
      color: 'blue',
      sublabel: 'Total en todos mis cursos',
      onClick: undefined as (() => void) | undefined,
    },
    {
      label: 'Estudiantes en Riesgo',
      value: data?.total_en_riesgo ?? 0,
      icon: AlertTriangle,
      color: 'amber',
      sublabel: 'Riesgo alto o medio',
      onClick: undefined as (() => void) | undefined,
    },
    {
      // 6.3: Alertas activas con navegación
      label: 'Alertas Activas',
      value: data?.total_alertas_activas ?? 0,
      icon: Activity,
      color: 'red',
      sublabel: 'Clic para ver en gestión',
      onClick: () => navigate('/dashboard/alerts'),
    },
    {
      label: 'Promedio General',
      value: data?.promedio_general != null ? data.promedio_general.toFixed(2) : '—',
      icon: BarChart2,
      color: 'green',
      sublabel: 'PPA de mis estudiantes',
      onClick: undefined,
    },
    {
      label: 'Tasa de Aprobación',
      value: data?.tasa_aprobacion != null ? `${data.tasa_aprobacion}%` : '—',
      icon: CheckCircle2,
      color: 'teal',
      sublabel: 'Notas ≥ 3.0 en mis cursos',
      onClick: undefined,
    },
    {
      label: 'Cursos Críticos',
      value: data?.cursos_criticos ?? 0,
      icon: BookX,
      color: 'orange',
      sublabel: 'CRÍTICO o EN OBSERVACIÓN',
      onClick: undefined,
    },
  ] as const;

  const colorMap: Record<string, string> = {
    blue:   'bg-blue-50 border-blue-200 text-blue-600',
    amber:  'bg-amber-50 border-amber-200 text-amber-600',
    red:    'bg-red-50 border-red-200 text-red-600',
    green:  'bg-green-50 border-green-200 text-green-600',
    teal:   'bg-teal-50 border-teal-200 text-teal-600',
    orange: 'bg-orange-50 border-orange-200 text-orange-600',
  };

  // Datos para la gráfica de distribución de riesgo
  const distData = data
    ? [
        { nivel: 'Alto', value: data.distribucion_riesgo.high, fill: '#C8102E' },
        { nivel: 'Medio', value: data.distribucion_riesgo.medium, fill: '#f59e0b' },
        { nivel: 'Bajo', value: data.distribucion_riesgo.low, fill: '#22c55e' },
      ]
    : [];

  return (
    <div className="space-y-6">
      {/* ── Banner de bienvenida ─────────────────────────────── */}
      <div className="bg-[#C8102E] text-white rounded-xl p-6 flex items-center justify-between shadow-md">
        <div>
          <h1 className="text-2xl font-bold mb-1">
            Bienvenido, Prof. {data?.nombre_docente || user?.nombre || 'Docente'}
          </h1>
          <p className="text-sm opacity-80">
            Panel de seguimiento · Cursos y estudiantes en riesgo asignados
          </p>
        </div>
        <button
          onClick={fetchDashboard}
          disabled={loading}
          className="p-2.5 rounded-xl bg-white/10 hover:bg-white/20 transition-colors disabled:opacity-50"
          title="Actualizar"
        >
          <RefreshCw className={`w-5 h-5 text-white ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-xl border border-red-200 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* ── 6.3/6.4: KPI Grid ───────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {kpis.map(({ label, value, icon: Icon, color, sublabel, onClick }) => (
          <div
            key={label}
            onClick={!loading && onClick ? onClick : undefined}
            className={`rounded-xl border p-4 flex flex-col items-center text-center gap-2 transition-all ${
              colorMap[color].split(' ').slice(0, 2).join(' ')
            } ${!loading && onClick ? 'cursor-pointer hover:shadow-md hover:scale-[1.03] active:scale-[0.98]' : ''}`}
          >
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${colorMap[color].split(' ').slice(0, 2).join(' ')}`}>
              <Icon className={`w-5 h-5 ${colorMap[color].split(' ')[2]}`} />
            </div>
            {loading ? (
              <div className="w-10 h-7 bg-gray-100 rounded animate-pulse" />
            ) : (
              <span className="text-xl font-black text-gray-800">{value}</span>
            )}
            <div>
              <p className="text-xs font-bold text-gray-600 leading-tight">{label}</p>
              <p className="text-[10px] text-gray-400 mt-0.5">{sublabel}</p>
            </div>
            {!loading && onClick && (
              <ExternalLink className="w-3 h-3 text-gray-300 mt-auto" />
            )}
          </div>
        ))}
      </div>

      {/* ── Gráficas: distribución riesgo + materias críticas ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 6.4: Distribución de riesgo */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-[#C8102E]" />
            Distribución de Riesgo de Mis Estudiantes
          </h2>
          {loading ? (
            <div className="h-48 bg-gray-100 rounded-lg animate-pulse" />
          ) : distData.every(d => d.value === 0) ? (
            <div className="h-48 flex items-center justify-center text-gray-400 text-sm border-2 border-dashed border-gray-100 rounded-xl">
              Sin datos de riesgo aún
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={distData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                <XAxis dataKey="nivel" axisLine={false} tickLine={false} tick={{ fontSize: 11, fontWeight: 600 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ borderRadius: '10px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', fontSize: '12px' }}
                />
                <Bar dataKey="value" name="Estudiantes" radius={[6, 6, 0, 0]}>
                  {distData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* 6.4: Top materias más reprobadas */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
            <BookX className="w-4 h-4 text-[#C8102E]" />
            Materias con Más Reprobaciones
          </h2>
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-10 bg-gray-100 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : !data?.materias_criticas?.length ? (
            <div className="h-48 flex items-center justify-center text-gray-400 text-sm border-2 border-dashed border-gray-100 rounded-xl">
              Sin reprobaciones registradas
            </div>
          ) : (
            <div className="space-y-3">
              {data.materias_criticas.map((m, i) => {
                const maxRep = data.materias_criticas[0]?.reprobaciones || 1;
                const pct = Math.round((m.reprobaciones / maxRep) * 100);
                return (
                  <div key={i} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-gray-700 truncate max-w-[70%]">{m.materia}</span>
                      <span className="text-xs font-bold text-red-600">{m.reprobaciones} reprobaciones</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-[#C8102E] h-2 rounded-full transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Mis Cursos ──────────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
        <div className="border-b border-gray-100 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-[#C8102E]" />
            <h2 className="text-base font-bold text-gray-900">Mis Cursos</h2>
          </div>
          {data && (
            <span className="text-xs font-bold px-2 py-1 rounded-full bg-gray-100 text-gray-600">
              {data.cursos.length} cursos
            </span>
          )}
        </div>

        {loading && !data ? (
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-32 bg-gray-100 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : !data?.cursos.length ? (
          <div className="px-6 py-12 text-center text-gray-400 text-sm">
            No tienes cursos asignados.
          </div>
        ) : (
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.cursos.map((curso) => (
              <div
                key={curso.curso_id}
                onClick={() => { setSelectedCurso(curso); setModalPage(1); setModalStudents([]); }}
                className="p-5 border border-gray-200 rounded-xl hover:shadow-md hover:border-[#C8102E]/30 transition-all cursor-pointer flex flex-col gap-3 group"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-[10px] font-mono text-gray-400 mb-1">
                      {curso.codigo} · Grupo {curso.grupo}
                    </p>
                    <h3 className="font-bold text-gray-900 text-sm line-clamp-2 group-hover:text-[#C8102E] transition-colors">
                      {curso.materia}
                    </h3>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold whitespace-nowrap flex-shrink-0 ${estadoBadgeClass(curso.estado)}`}>
                    {curso.estado}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-100 text-xs text-gray-600">
                  <div className="flex items-center gap-1">
                    <Users className="w-3.5 h-3.5 text-gray-400" />
                    <span>{curso.matriculados} inscritos</span>
                  </div>
                  <div className="flex items-center gap-1 text-red-600 font-semibold">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>{curso.en_riesgo} en riesgo</span>
                  </div>
                  {curso.tasa_reprobacion > 0 && (
                    <div className="flex items-center gap-1 text-orange-600 col-span-2">
                      <BookX className="w-3.5 h-3.5" />
                      <span>{curso.tasa_reprobacion}% reprobación</span>
                    </div>
                  )}
                  {curso.promedio_curso != null && (
                    <div className="flex items-center gap-1 text-green-600 col-span-2">
                      <BarChart2 className="w-3.5 h-3.5" />
                      <span>Promedio: {curso.promedio_curso.toFixed(2)}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Modal: Estudiantes en riesgo del curso ────────────── */}
      {selectedCurso && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/50"
            onClick={() => setSelectedCurso(null)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
              <div className="bg-[#C8102E] text-white px-6 py-4 flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold">{selectedCurso.materia}</h2>
                  <p className="text-xs opacity-80">{selectedCurso.codigo} · Grupo {selectedCurso.grupo}</p>
                </div>
                <button onClick={() => setSelectedCurso(null)} className="p-1.5 rounded-lg hover:bg-white/20 transition-colors">
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="p-6 overflow-y-auto flex-1 space-y-4">
                {modalLoading && modalStudents.length === 0 ? (
                  <div className="py-12 text-center text-gray-400">Cargando estudiantes en riesgo...</div>
                ) : modalError ? (
                  <div className="p-4 bg-red-50 text-red-700 rounded-xl border border-red-200 flex items-center gap-2 text-sm">
                    <AlertTriangle className="w-4 h-4" /> {modalError}
                  </div>
                ) : modalStudents.length === 0 ? (
                  <div className="py-12 text-center text-gray-400">No hay estudiantes en riesgo en este curso.</div>
                ) : (
                  <>
                    <div className="overflow-x-auto border border-gray-200 rounded-xl">
                      <table className="w-full text-sm">
                        <thead className="bg-[#C8102E] text-white">
                          <tr>
                            {['Estudiante', 'Código', 'Nivel Riesgo', 'Alertas', 'Acciones'].map(h => (
                              <th key={h} className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {modalStudents.map((est, idx) => (
                            <tr key={est.codigo} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/50 hover:bg-red-50/30 transition-colors'}>
                              <td className="px-4 py-3 font-semibold text-gray-900">{est.nombre}</td>
                              <td className="px-4 py-3 text-gray-500 font-mono text-xs">{est.codigo}</td>
                              <td className="px-4 py-3">
                                {est.nivel_riesgo === 'high'   && <Badge variant="high">ALTO</Badge>}
                                {est.nivel_riesgo === 'medium' && <Badge variant="medium">MEDIO</Badge>}
                              </td>
                              <td className="px-4 py-3">
                                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#C8102E] text-white text-xs font-bold">
                                  {est.alertas_activas}
                                </span>
                              </td>
                              <td className="px-4 py-3">
                                <Link to={`/dashboard/students/${est.codigo}`}>
                                  <Button variant="outline" size="sm">Ver perfil</Button>
                                </Link>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {modalPages > 1 && (
                      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                        <p className="text-xs text-gray-500">
                          Página {modalPage} de {modalPages} · {modalTotal} estudiantes
                        </p>
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm" onClick={() => setModalPage(p => Math.max(1, p - 1))} disabled={modalPage <= 1 || modalLoading}>
                            <ChevronLeft className="w-4 h-4 mr-1" /> Anterior
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => setModalPage(p => p + 1)} disabled={modalPage >= modalPages || modalLoading}>
                            Siguiente <ChevronRight className="w-4 h-4 ml-1" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
