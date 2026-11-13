import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router';
import {
  AlertTriangle, BookOpen, Users, ChevronLeft, ChevronRight,
  RefreshCw, X, TrendingUp, CheckCircle2, BarChart2,
  Activity, BookX, ExternalLink, CheckSquare, CalendarX,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { apiFetch } from '../../services/apiFetch';
import AttendanceModal from '../components/AttendanceModal';
import AttendanceImport from '../components/AttendanceImport';
import { BarraDistribucion, CintaIndicadores, EncabezadoPagina, Seccion } from '../components/Panel';


const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ─── Interfaces ───────────────────────────────────────────────────────────────

interface EstudianteRiesgo {
  codigo: string;
  nombre: string;
  curso: string;
  nivel_riesgo: 'high' | 'medium';
  alertas_activas: number;
  porcentaje_inasistencia?: number | null;    // HU-34, solo en la lista del curso
  supera_umbral_inasistencia?: boolean | null;  // HU-35: null sin umbral configurado
  cerca_umbral_inasistencia?: boolean | null;   // se aproxima al umbral sin superarlo
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
  inasistencia_sobre_umbral: number | null;    // HU-34; HU-35: null sin umbral configurado
  inasistencia_cerca_umbral: number | null;    // estudiantes que se aproximan al umbral
  umbral_inasistencia: number | null;          // HU-35: umbral efectivo del curso
  origen_umbral_inasistencia: 'curso' | 'general' | null;
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
  umbral_inasistencia: number | null;          // HU-35: umbral general
  page: number;
  pages: number;
  page_size: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const estadoBadgeClass = (estado: string) => {
  if (estado === 'CRÍTICO')         return 'bg-red-50 text-red-600 border border-red-200';
  if (estado === 'EN OBSERVACIÓN')  return 'bg-amber-50 text-amber-700 border border-amber-200';
  if (estado === 'ESTABLE')         return 'bg-green-50 text-green-700 border border-green-200';
  return 'bg-gray-100 text-gray-600 border border-gray-200';
};

const colorEstado = (estado: string) =>
  estado === 'CRÍTICO' ? '#B02A2B' : estado === 'EN OBSERVACIÓN' ? '#C98A12' : estado === 'ESTABLE' ? '#2F8F6B' : '#D5BFBA';

const entrada = (i: number) => ({ animationDelay: `${i * 60}ms`, animationFillMode: 'backwards' as const });

function TooltipLimpio({ active, payload, label }: { active?: boolean; payload?: any[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-[10px] border border-line bg-white px-3 py-2 text-sm">
      <p className="font-semibold text-ink mb-0.5">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="text-ink-soft tabular-nums">
          {p.name}: <span className="font-semibold text-ink">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

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
  
  // Modal: toma de asistencia
  const [attendanceCurso, setAttendanceCurso] = useState<CursoDoc | null>(null);

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

  // Icono y tinte de cada indicador (el borde y el fondo de la tarjeta son neutros)
  const colorMap: Record<string, string> = {
    blue:   'bg-blue-50 text-blue-600',
    amber:  'bg-amber-50 text-amber-600',
    red:    'bg-red-50 text-red-600',
    green:  'bg-green-50 text-green-600',
    teal:   'bg-teal-50 text-teal-600',
    orange: 'bg-orange-50 text-orange-600',
  };

  // Datos para la gráfica de distribución de riesgo
  const distData = data
    ? [
        { nivel: 'Alto', value: data.distribucion_riesgo.high, fill: '#B02A2B' },
        { nivel: 'Medio', value: data.distribucion_riesgo.medium, fill: '#C98A12' },
        { nivel: 'Bajo', value: data.distribucion_riesgo.low, fill: '#2F8F6B' },
      ]
    : [];

  const enRiesgo = data?.total_en_riesgo ?? 0;

  return (
    <div className="space-y-6">
      {/* ── Saludo y estado del día ───────────────────────────── */}
      <EncabezadoPagina
        titulo={<>Bienvenido, Prof. {data?.nombre_docente || user?.nombre || 'Docente'}</>}
        detalle="Tus cursos y los estudiantes que conviene acompañar esta semana."
      >
        <Button variant="outline" onClick={fetchDashboard} disabled={loading} title="Actualizar" className="flex items-center gap-2">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
          Actualizar
        </Button>
      </EncabezadoPagina>

      {error && (
        <div role="alert" className="p-4 bg-red-50 text-red-800 rounded-[10px] border border-red-200 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* ── Qué requiere atención + cifras del docente ────────── */}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        <div className={`rounded-[14px] border p-5 flex flex-col justify-between gap-4 ${
          !loading && enRiesgo > 0 ? 'bg-red-50 border-red-200' : 'bg-primary-tint border-primary/15'
        }`}>
          {loading ? (
            <div className="space-y-3">
              <div className="h-9 w-16 rounded-md bg-white/70 animate-pulse" />
              <div className="h-4 w-48 rounded-md bg-white/70 animate-pulse" />
            </div>
          ) : enRiesgo > 0 ? (
            <>
              <div>
                <p className="cifra text-4xl font-semibold text-riesgo-critico leading-none">{enRiesgo}</p>
                <p className="mt-2 font-semibold text-red-900">
                  {enRiesgo === 1 ? 'estudiante necesita' : 'estudiantes necesitan'} tu atención
                </p>
                <p className="mt-1 text-sm text-red-800">Tienen riesgo alto o medio en alguno de tus cursos.</p>
              </div>
              <Link to="/dashboard/alerts" className="inline-flex items-center gap-1.5 self-start rounded-[10px] bg-riesgo-critico px-3.5 py-2 text-sm font-semibold text-white hover:bg-red-700">
                Revisar alertas
                <ChevronRight className="w-4 h-4" aria-hidden="true" />
              </Link>
            </>
          ) : (
            <div>
              <CheckCircle2 className="w-6 h-6 text-primary" aria-hidden="true" />
              <p className="mt-2 font-semibold text-primary-strong">Ningún estudiante en riesgo</p>
              <p className="mt-1 text-sm text-ink-soft">Tus cursos no tienen estudiantes con riesgo alto o medio.</p>
            </div>
          )}
        </div>

        <CintaIndicadores
          cargando={loading}
          indicadores={kpis
            .filter((k) => k.label !== 'Estudiantes en Riesgo')
            .map((k) => ({
              etiqueta: k.label,
              valor: k.value,
              detalle: k.sublabel,
              icono: k.icon,
              onClick: k.onClick,
              tono: (k.label === 'Alertas Activas' || k.label === 'Cursos Críticos') && Number(k.value) > 0 ? ('alerta' as const) : undefined,
            }))}
        />
      </div>

      {/* ── Distribución de riesgo + materias críticas ────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 6.4: Distribución de riesgo */}
        <Seccion titulo="Distribución de Riesgo de Mis Estudiantes" detalle="Cuántos estudiantes hay en cada nivel.">
          {loading ? (
            <div className="h-24 bg-wash rounded-[10px] animate-pulse" />
          ) : distData.every(d => d.value === 0) ? (
            <p className="py-8 text-center text-ink-muted text-sm bg-paper border border-dashed border-line-strong rounded-[10px]">
              Sin datos de riesgo aún
            </p>
          ) : (
            <BarraDistribucion tramos={distData.map((d) => ({ etiqueta: d.nivel, valor: d.value, color: d.fill }))} />
          )}
        </Seccion>

        {/* 6.4: Top materias más reprobadas */}
        <Seccion titulo="Materias con Más Reprobaciones" detalle="Ordenadas de mayor a menor.">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-8 bg-wash rounded-[10px] animate-pulse" />
              ))}
            </div>
          ) : !data?.materias_criticas?.length ? (
            <p className="py-8 text-center text-ink-muted text-sm bg-paper border border-dashed border-line-strong rounded-[10px]">
              Sin reprobaciones registradas
            </p>
          ) : (
            <ul className="space-y-3">
              {data.materias_criticas.map((m, i) => {
                const maxRep = data.materias_criticas[0]?.reprobaciones || 1;
                const pct = Math.round((m.reprobaciones / maxRep) * 100);
                return (
                  <li key={i} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)_auto] items-center gap-3">
                    <span className="text-sm font-medium text-ink truncate">{m.materia}</span>
                    <span className="h-2 bg-wash rounded-full overflow-hidden">
                      <span className="block h-2 rounded-full bg-riesgo-alto" style={{ width: `${pct}%` }} />
                    </span>
                    <span className="text-sm text-ink-soft tabular-nums whitespace-nowrap">{m.reprobaciones} reprobaciones</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Seccion>
      </div>

      {/* ── Mis Cursos ──────────────────────────────────────────── */}
      <div className="bg-white rounded-[14px] border border-line shadow-sm">
        <div className="border-b border-line px-5 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-primary" />
            <h2 className="text-base font-semibold text-gray-900">Mis Cursos</h2>
          </div>
          {data && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-wash text-ink-soft">
              {data.cursos.length} cursos
            </span>
          )}
        </div>

        {loading && !data ? (
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-32 bg-wash rounded-[10px] animate-pulse" />
            ))}
          </div>
        ) : !data?.cursos.length ? (
          <div className="px-6 py-14 text-center text-ink-muted text-sm">
            No tienes cursos asignados. Cuando el administrador te asigne un curso, aparecerá aquí.
          </div>
        ) : (
          <div className="p-5 sm:p-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.cursos.map((curso, ci) => (
              <div
                key={curso.curso_id}
                onClick={() => { setSelectedCurso(curso); setModalPage(1); setModalStudents([]); }}
                style={{ ...entrada(ci), borderLeftColor: colorEstado(curso.estado) }}
                className="p-5 border border-line border-l-4 rounded-[14px] hover:shadow-md transition-all cursor-pointer flex flex-col gap-3 group bg-white"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-xs tabular-nums text-ink-muted mb-1">
                      {curso.codigo} · Grupo {curso.grupo}
                    </p>
                    <h3 className="font-semibold text-ink text-base leading-snug line-clamp-2 group-hover:text-primary transition-colors">
                      {curso.materia}
                    </h3>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-semibold whitespace-nowrap flex-shrink-0 ${estadoBadgeClass(curso.estado)}`}>
                    {curso.estado}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-3 border-t border-wash text-sm text-ink-soft">
                  <div className="flex items-center gap-1">
                    <Users className="w-3.5 h-3.5 text-gray-400" />
                    <span>{curso.matriculados} inscritos</span>
                  </div>
                  <div className="flex items-center gap-1 text-red-600 font-semibold">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>{curso.en_riesgo} en riesgo</span>
                  </div>
                  <div className={`flex items-center gap-1 col-span-2 ${
                    (curso.inasistencia_sobre_umbral ?? 0) > 0 ? 'text-red-600 font-semibold' : 'text-gray-500'
                  }`}>
                    <CalendarX className="w-3.5 h-3.5" />
                    <span>
                      {curso.umbral_inasistencia === null || curso.inasistencia_sobre_umbral === null
                        ? 'Sin umbral de inasistencia configurado'
                        : `${curso.inasistencia_sobre_umbral} sobre el umbral de inasistencia (${curso.umbral_inasistencia}%${
                            curso.origen_umbral_inasistencia === 'curso' ? ', propio del curso' : ''
                          })`}
                    </span>
                  </div>
                  {(curso.inasistencia_cerca_umbral ?? 0) > 0 && (
                    <div className="flex items-center gap-1 col-span-2 text-amber-600 font-semibold">
                      <CalendarX className="w-3.5 h-3.5" />
                      <span>{curso.inasistencia_cerca_umbral} cerca del umbral de inasistencia</span>
                    </div>
                  )}
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
                
                <div className="pt-2">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="w-full justify-center text-primary border-primary/30 hover:bg-primary-tint hover:text-primary-strong hover:border-primary/50"
                    onClick={(e) => {
                      e.stopPropagation();
                      setAttendanceCurso(curso);
                    }}
                  >
                    <CheckSquare className="w-4 h-4 mr-2" /> Tomar asistencia
                  </Button>
                </div>
              </div>
            ))}
          </div>

        )}
      </div>

      {/* ── Carga de asistencia por archivo (HU-33) ────────────── */}
      <AttendanceImport />

      {/* ── Modal: Estudiantes en riesgo del curso ────────────── */}
      {selectedCurso && (
        <>
          <div
            className="fixed inset-0 z-40 bg-ink/50 animate-in fade-in duration-200"
            onClick={() => setSelectedCurso(null)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-[14px] shadow-2xl w-full max-w-4xl max-h-[85vh] overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200">
              <div className="bg-white text-ink border-b border-line px-6 py-4 flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold">{selectedCurso.materia}</h2>
                  <p className="text-sm text-ink-muted">{selectedCurso.codigo} · Grupo {selectedCurso.grupo}</p>
                </div>
                <button onClick={() => setSelectedCurso(null)} className="p-1.5 rounded-[10px] text-ink-muted hover:text-ink hover:bg-wash transition-colors">
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="p-6 overflow-y-auto flex-1 space-y-4">
                {modalLoading && modalStudents.length === 0 ? (
                  <div className="py-12 text-center text-gray-400">Cargando estudiantes en riesgo...</div>
                ) : modalError ? (
                  <div className="p-4 bg-red-50 text-red-700 rounded-[10px] border border-red-200 flex items-center gap-2 text-sm">
                    <AlertTriangle className="w-4 h-4" /> {modalError}
                  </div>
                ) : modalStudents.length === 0 ? (
                  <div className="py-12 text-center text-ink-muted">No hay estudiantes en riesgo en este curso. Buen momento para revisar la asistencia.</div>
                ) : (
                  <>
                    <div className="overflow-x-auto border border-line rounded-[10px]">
                      <table className="w-full text-sm">
                        <thead className="bg-paper text-ink-soft border-b border-line">
                          <tr>
                            {['Estudiante', 'Código', 'Nivel Riesgo', '% Inasistencia', 'Alertas', 'Acciones'].map(h => (
                              <th key={h} className="px-4 py-3 text-left text-xs font-semibold">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {modalStudents.map((est, idx) => (
                            <tr key={est.codigo} className="transition-colors hover:bg-paper">
                              <td className="px-4 py-3 font-semibold text-gray-900">{est.nombre}</td>
                              <td className="px-4 py-3 text-gray-500 tabular-nums text-xs">{est.codigo}</td>
                              <td className="px-4 py-3">
                                {est.nivel_riesgo === 'high'   && <Badge variant="high">ALTO</Badge>}
                                {est.nivel_riesgo === 'medium' && <Badge variant="medium">MEDIO</Badge>}
                              </td>
                              <td className="px-4 py-3">
                                {est.porcentaje_inasistencia == null ? (
                                  <span className="text-xs text-gray-400">Sin registros</span>
                                ) : (
                                  <span
                                    className={`tabular-nums text-xs font-semibold px-2 py-1 rounded ${
                                      est.supera_umbral_inasistencia
                                        ? 'bg-red-50 text-red-600'
                                        : est.cerca_umbral_inasistencia
                                          ? 'bg-amber-50 text-amber-700'
                                          : 'bg-green-50 text-green-700'
                                    }`}
                                    title={
                                      est.supera_umbral_inasistencia
                                        ? 'Supera el umbral de inasistencia'
                                        : est.cerca_umbral_inasistencia
                                          ? 'Se aproxima al umbral de inasistencia'
                                          : undefined
                                    }
                                  >
                                    {est.porcentaje_inasistencia.toFixed(2)}%
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-3">
                                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-red-600 text-white text-xs font-semibold tabular-nums">
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

      {/* ── Modal: Toma de Asistencia ────────────── */}
      {attendanceCurso && (
        <AttendanceModal 
          curso={attendanceCurso} 
          onClose={() => setAttendanceCurso(null)} 
        />
      )}
    </div>
  );
}
