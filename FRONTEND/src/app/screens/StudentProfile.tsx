import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router';
import {
  ArrowLeft,
  User,
  BookOpen,
  BarChart2,
  GraduationCap,
  Phone,
  Mail,
  MapPin,
  Calendar,
  Hash,
  Layers,
  Clock,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Activity,
  FileText,
  ChevronDown,
  ChevronUp,
  History,
  X,
  ExternalLink,
  RefreshCw,
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Area,
  AreaChart,
  ReferenceLine
} from 'recharts';
import { Button } from '../components/ui/Button';
import { NivelRiesgoChip } from '../components/Riesgo';
import { apiFetch } from '../../services/apiFetch';

interface StudentDetail {
  codigo: string;
  nombre: string;
  tipo_documento: string;
  numero_documento: string;
  semestre: number;
  pensum: string | null;
  ingreso: string | null;
  promedio: number | null;
  estado_matricula: string;
  celular: string | null;
  email_personal: string | null;
  email_institucional: string | null;
  colegio_egresado: string | null;
  municipio_nacimiento: string | null;
  nivel_riesgo: 'high' | 'medium' | 'low' | 'unknown';
  alertas_activas: number;
}

// ─── Sección 1: Ficha Académica ──────────────────────────────────────────────
function FichaAcademica({ student }: { student: StudentDetail | null }) {
  if (!student) return null;

  const personales: [string, string][] = [
    ['Nombre Completo', student.nombre],
    ['Código Estudiantil', student.codigo],
    ['Tipo de Documento', student.tipo_documento],
    ['Número de Documento', student.numero_documento],
    ['Celular', student.celular || 'No registrado'],
    ['Correo Personal', student.email_personal || 'No registrado'],
    ['Correo Institucional', student.email_institucional || 'No registrado'],
    ['Municipio Nacimiento', student.municipio_nacimiento || 'No registrado'],
  ];
  const academicos: [string, string][] = [
    ['Semestre Actual', `${student.semestre}° Semestre`],
    ['Pensum', student.pensum || 'No definido'],
    ['Fecha de Ingreso', student.ingreso || 'Sin dato'],
    ['Estado de Matrícula', student.estado_matricula],
    ['Colegio Egresado', student.colegio_egresado || 'No registrado'],
  ];
  const sinDato = ['No registrado', 'No definido', 'Sin dato'];

  const filas = (datos: [string, string][]) => (
    <dl className="divide-y divide-wash">
      {datos.map(([label, value]) => (
        <div key={label} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] gap-4 py-2.5 text-sm">
          <dt className="text-ink-muted">{label}</dt>
          <dd className={`break-words ${sinDato.includes(value) ? 'text-ink-faint' : 'font-medium text-ink'}`}>{value}</dd>
        </div>
      ))}
    </dl>
  );

  return (
    <section className="bg-white rounded-[14px] border border-line overflow-hidden">
      <div className="border-b border-line px-5 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-ink">Ficha Académica</h2>
          <p className="text-sm text-ink-muted">Información personal y académica del estudiante</p>
        </div>
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-soft border border-line rounded-md px-2 py-1">
          <CheckCircle2 className="w-3.5 h-3.5 text-riesgo-bajo" aria-hidden="true" />
          Datos Verificados
        </span>
      </div>

      <div className="grid md:grid-cols-2 md:divide-x divide-line">
        <div className="px-5 sm:px-6 py-4">
          <h3 className="text-sm font-semibold text-ink mb-1">Datos Personales</h3>
          {filas(personales)}
        </div>
        <div className="px-5 sm:px-6 py-4 border-t md:border-t-0 border-line">
          <h3 className="text-sm font-semibold text-ink mb-1">Datos Académicos</h3>
          {filas(academicos)}

          {/* Nivel de riesgo real */}
          <div className="mt-4 flex items-center justify-between gap-3 rounded-[10px] border border-line bg-paper px-4 py-3">
            <p className="text-sm font-medium text-ink-soft">Nivel de Riesgo</p>
            <NivelRiesgoChip
              nivel={student.nivel_riesgo}
              texto={
                student.nivel_riesgo === 'high' ? 'ALTO' :
                student.nivel_riesgo === 'medium' ? 'MEDIO' :
                student.nivel_riesgo === 'low' ? 'BAJO' : 'DESCONOCIDO'
              }
            />
          </div>
        </div>
      </div>
    </section>
  );
}

interface Intento {
  periodo: string;
  nota: number | null; // null: materia en curso, sin definitiva
  estado: string;
}

interface MateriaRepetida {
  nombre: string;
  veces: number;
  intentos: Intento[];
}

interface EvolucionData {
  periodo: string;
  pps: number;
  ppa: number;
}

interface TendenciaData {
  valor: number;
  porcentaje: number;
  direccion: 'up' | 'down' | 'stable';
}

interface RiesgoEvolucionItem {
  periodo: string;
  nivel_riesgo: 'high' | 'medium' | 'low' | 'unknown';
}

interface IndicadoresData {
  aprobadas: number;
  reprobadas: number;
  creditos_cursados: number;
  porcentaje_progreso: number;
  materias_repetidas: MateriaRepetida[];
  promedio_acumulado: number;
  tendencia: TendenciaData;
  evolucion: EvolucionData[];
  alertas_activas: number;
  riesgo_evolucion: RiesgoEvolucionItem[];
}

// ─── Modal Materias Reprobadas (4.3) ─────────────────────────────────────────
function ModalMateriasReprobadas({
  historial,
  onClose,
}: {
  historial: HistorialPeriodo[] | null;
  onClose: () => void;
}) {
  // Aplanar todas las materias reprobadas con su periodo
  const reprobadas: { materia: string; codigo: string; nota: number; periodo: string }[] = [];
  (historial ?? []).forEach((p) => {
    p.materias.forEach((m) => {
      if (m.estado === 'Reprobado' && m.nota_final !== null) {
        reprobadas.push({
          materia: m.materia,
          codigo: m.codigo,
          nota: m.nota_final,
          periodo: p.periodo,
        });
      }
    });
  });

  // Agrupar por materia
  const agrupadas: Record<string, typeof reprobadas> = {};
  reprobadas.forEach((r) => {
    if (!agrupadas[r.materia]) agrupadas[r.materia] = [];
    agrupadas[r.materia].push(r);
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-[14px] shadow-2xl w-full max-w-lg mx-4 z-10 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-orange-50 rounded-t-2xl">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-[10px] bg-orange-100 flex items-center justify-center">
              <Activity className="w-4 h-4 text-orange-600" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-gray-900">Materias Reprobadas</h2>
              <p className="text-xs text-gray-500">{reprobadas.length} registros en el historial</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-[10px] hover:bg-gray-100">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Contenido */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {reprobadas.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircle2 className="w-12 h-12 text-green-300 mx-auto mb-3" />
              <p className="text-sm font-semibold text-gray-500">Sin materias reprobadas</p>
              <p className="text-xs text-gray-400 mt-1">El estudiante no tiene pérdidas registradas.</p>
            </div>
          ) : (
            Object.entries(agrupadas).map(([nombre, intentos]) => (
              <div key={nombre} className="border border-orange-100 rounded-[10px] overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 bg-orange-50/60">
                  <div>
                    <p className="text-xs font-semibold text-gray-800">{nombre}</p>
                    <p className="text-[10px] text-gray-400 tabular-nums mt-0.5">{intentos[0].codigo}</p>
                  </div>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-orange-100 text-orange-700">
                    {intentos.length} {intentos.length === 1 ? 'vez' : 'veces'}
                  </span>
                </div>
                <div className="divide-y divide-orange-50">
                  {intentos.map((it, i) => (
                    <div key={i} className="flex items-center justify-between px-4 py-2.5 bg-white">
                      <span className="text-xs text-gray-500 tabular-nums">{it.periodo}</span>
                      <span className="tabular-nums text-sm font-semibold px-2.5 py-1 rounded-[10px] bg-red-50 text-red-700 border border-red-100">
                        {it.nota.toFixed(1)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="px-6 py-3 border-t border-gray-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-gray-600 border border-gray-200 rounded-[10px] hover:bg-gray-50 transition-colors"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

function IndicadoresSection({
  data,
  loading,
  studentName,
  historial,
}: {
  data: IndicadoresData | null;
  loading: boolean;
  studentName?: string;
  historial?: HistorialPeriodo[] | null;
}) {
  const navigate = useNavigate();
  const [showReprobadas, setShowReprobadas] = useState(false); // 4.3
  const indicadores = [
    {
      icon: BarChart2,
      label: 'Promedio Acumulado',
      sublabel: 'Sobre escala de 0 a 5',
      color: 'blue',
      value: data?.promedio_acumulado ? data.promedio_acumulado.toFixed(2) : null,
      onClick: undefined as (() => void) | undefined,
    },
    {
      icon: data?.tendencia?.direccion === 'down' ? TrendingDown : TrendingUp,
      label: 'Tendencia del Promedio',
      sublabel: 'Últimos 3 semestres',
      color: data?.tendencia?.direccion === 'down' ? 'red' : 'green',
      value: data?.tendencia ? (
        <div className="flex items-center gap-1">
          {data.tendencia.direccion === 'up' ? '+' : data.tendencia.direccion === 'down' ? '-' : ''}
          {data.tendencia.porcentaje}%
        </div>
      ) : null,
      onClick: undefined as (() => void) | undefined,
    },
    {
      icon: AlertTriangle,
      label: 'Alertas Activas',
      sublabel: 'Ver en gestión de alertas',    // 4.2
      color: 'red',
      value: data?.alertas_activas ?? 0,
      // 4.2: navegar a alertas buscando por nombre
      onClick: studentName
        ? () => navigate(`/dashboard/alerts?search=${encodeURIComponent(studentName)}`)
        : undefined,
    },
    {
      icon: CheckCircle2,
      label: 'Materias Aprobadas',
      sublabel: 'Total acumulado',
      color: 'green',
      value: data?.aprobadas,
      onClick: undefined as (() => void) | undefined,
    },
    {
      icon: Activity,
      label: 'Materias Reprobadas',
      sublabel: 'Clic para ver detalle',        // 4.3
      color: 'orange',
      value: data?.reprobadas,
      onClick: () => setShowReprobadas(true),    // 4.3
    },
    {
      icon: Clock,
      label: 'Créditos Cursados',
      sublabel: 'Sobre total del pensum',
      color: 'teal',
      value: data ? `${data.creditos_cursados} créditos | ${data.porcentaje_progreso}%` : null,
      onClick: undefined as (() => void) | undefined,
    },
  ];

  const colorMap: Record<string, string> = {
    blue:   'bg-blue-50   border-blue-200   text-blue-500',
    purple: 'bg-purple-50 border-purple-200 text-purple-500',
    red:    'bg-red-50    border-red-200    text-red-500',
    green:  'bg-green-50  border-green-200  text-green-500',
    orange: 'bg-orange-50 border-orange-200 text-orange-500',
    teal:   'bg-teal-50   border-teal-200   text-teal-500',
  };

  return (
    <div className="bg-white rounded-[14px] border border-line overflow-hidden">
      {/* Modal materias reprobadas — 4.3 */}
      {showReprobadas && (
        <ModalMateriasReprobadas
          historial={historial ?? null}
          onClose={() => setShowReprobadas(false)}
        />
      )}

      {/* Header de sección */}
      <div className="border-b border-line px-5 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-ink">Indicadores de Desempeño</h2>
          <p className="text-sm text-ink-muted">Métricas clave del rendimiento académico</p>
        </div>
        {!loading && (
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-soft border border-line rounded-md px-2 py-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-riesgo-bajo" aria-hidden="true" />
            Datos Actualizados
          </span>
        )}
      </div>

      {/* Indicadores: una cinta de celdas; las que abren detalle son botones */}
      <div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 border-b border-line overflow-hidden">
          {indicadores.map(({ icon: Icon, label, sublabel, color, value, onClick }) => {
            const activo = !loading && !!onClick;
            return (
              <div
                key={label}
                onClick={activo ? onClick : undefined}
                onKeyDown={activo ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick!(); } } : undefined}
                role={activo ? 'button' : undefined}
                tabIndex={activo ? 0 : undefined}
                className={`relative px-4 sm:px-5 py-4 border-line border-r border-b -mb-px -mr-px flex flex-col gap-1.5 ${
                  activo ? 'cursor-pointer hover:bg-paper' : ''
                }`}
              >
                {/* Valor Real o Placeholder */}
                {loading || (value === null && label !== 'Promedio Acumulado' && label !== 'Tendencia del Promedio' && label !== 'Alertas Activas') ? (
                  <div className="w-12 h-7 rounded bg-wash animate-pulse" />
                ) : (
                  <div className={`text-2xl font-semibold leading-none tracking-[-0.02em] ${
                    color === 'red' && value !== 0 ? 'text-riesgo-critico' : 'text-ink'
                  } ${typeof value === 'string' && value.length > 8 ? 'text-base leading-tight tracking-normal' : ''}`}>
                    {value ?? '—'}
                  </div>
                )}

                <div>
                  <p className="text-sm font-medium text-ink-soft">{label}</p>
                  <p className="text-xs text-ink-muted">{sublabel}</p>
                </div>

                {/* Indicador visual de interactividad */}
                {activo ? (
                  <ExternalLink className="absolute top-3.5 right-3.5 w-3.5 h-3.5 text-ink-faint" aria-hidden="true" />
                ) : (
                  <Icon className="absolute top-3.5 right-3.5 w-4 h-4 text-line-strong" aria-hidden="true" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="p-5 sm:p-6">
        {/* ─── Sub-sección: Materias Repetidas (Acordeón) ─────────────────── */}
        {data && data.materias_repetidas.length > 0 && (
          <div className="mb-6 space-y-4">
            <div className="flex items-center gap-2 px-2 pb-2 border-b border-gray-100">
              <History className="w-4 h-4 text-gray-400" />
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-tight">
                Historial de Materias Repetidas
              </h3>
              <span className="ml-auto text-[10px] bg-amber-100 text-amber-600 px-2 py-0.5 rounded-full font-semibold">
                {data.materias_repetidas.length} MATERIAS
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {data.materias_repetidas.map((materia) => (
                <MateriaRepetidaCard key={materia.nombre} materia={materia} />
              ))}
            </div>
          </div>
        )}

        {/* Gráfico de evolución */}
        <div className="rounded-[10px] border border-line p-5">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-sm font-semibold text-gray-700">Evolución del Promedio Acumulado</h3>
              <p className="text-xs text-gray-400 mt-0.5">Historial del PPA periodo a periodo</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full bg-primary" />
                <span className="text-[10px] font-semibold text-gray-500 uppercase">Promedio Acumulado</span>
              </div>
            </div>
          </div>
          
          <div className="h-64 w-full">
            {loading ? (
              <div className="w-full h-full bg-wash animate-pulse rounded-[10px]" />
            ) : data && data.evolucion.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.evolucion} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorPpa" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#C8102E" stopOpacity={0.1}/>
                      <stop offset="95%" stopColor="#C8102E" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                  <XAxis 
                    dataKey="periodo" 
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 10, fontWeight: 600, fill: '#9C8D8A' }}
                    dy={10}
                  />
                  <YAxis 
                    domain={[2, 5]} 
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 10, fontWeight: 600, fill: '#9C8D8A' }}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      borderRadius: '12px', 
                      border: 'none', 
                      boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                      fontSize: '12px'
                    }}
                  />
                  <Area 
                    type="linear" 
                    dataKey="ppa" 
                    stroke="#C8102E" 
                    strokeWidth={3}
                    fillOpacity={1} 
                    fill="url(#colorPpa)"
                    name="Acumulado"
                    dot={{ r: 4, fill: '#C8102E', strokeWidth: 2, stroke: '#fff' }}
                    activeDot={{ r: 6, strokeWidth: 0 }}
                  />
                  <ReferenceLine y={3} stroke="#fee2e2" strokeDasharray="3 3" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 border-2 border-dashed border-gray-100 rounded-[10px]">
                <Activity className="w-8 h-8 mb-2 opacity-20" />
                <p className="text-xs font-medium">No hay datos históricos suficientes</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Gráfica de evolución de riesgo por periodo */}
      {data?.riesgo_evolucion && data.riesgo_evolucion.length > 0 && (
        <div className="px-6 pb-6">
          <div className="bg-gray-50 rounded-[10px] p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-primary" />
              Evolución del Nivel de Riesgo por Periodo
            </h3>
            {/* Gráfica de línea con niveles numéricos */}
            <div className="mb-4">
              <ResponsiveContainer width="100%" height={160}>
                <LineChart
                  data={data.riesgo_evolucion.map(item => ({
                    periodo: item.periodo,
                    valor: item.nivel_riesgo === 'high' ? 3 : item.nivel_riesgo === 'medium' ? 2 : item.nivel_riesgo === 'low' ? 1 : 0,
                    nivel: item.nivel_riesgo,
                  }))}
                  margin={{ top: 10, right: 10, left: -30, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                  <XAxis
                    dataKey="periodo"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 10, fontWeight: 600, fill: '#9C8D8A' }}
                    dy={8}
                  />
                  <YAxis
                    domain={[0, 3]}
                    ticks={[1, 2, 3]}
                    tickFormatter={(v) => v === 3 ? 'Alto' : v === 2 ? 'Medio' : v === 1 ? 'Bajo' : ''}
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 10, fontWeight: 600, fill: '#9C8D8A' }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '10px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', fontSize: '12px' }}
                    formatter={(value: number) => {
                      const labels: Record<number, string> = { 3: 'Alto', 2: 'Medio', 1: 'Bajo', 0: 'Sin dato' };
                      return [labels[value] ?? value, 'Nivel de riesgo'];
                    }}
                  />
                  <ReferenceLine y={3} stroke="#fca5a5" strokeDasharray="4 4" strokeWidth={1} />
                  <ReferenceLine y={2} stroke="#fcd34d" strokeDasharray="4 4" strokeWidth={1} />
                  <Line
                    type="stepAfter"
                    dataKey="valor"
                    stroke="#C8102E"
                    strokeWidth={2.5}
                    dot={(props: any) => {
                      const { cx, cy, payload, index } = props;
                      const colors: Record<string, string> = { high: '#B02A2B', medium: '#C98A12', low: '#2F8F6B', unknown: '#9C8D8A' };
                      return <circle key={index} cx={cx} cy={cy} r={5} fill={colors[payload.nivel] ?? '#9C8D8A'} stroke="#fff" strokeWidth={2} />;
                    }}
                    activeDot={{ r: 7 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {/* Leyenda de periodos con colores */}
            <div className="space-y-1.5">
              {data.riesgo_evolucion.map((item, idx) => {
                const riesgoColors = {
                  high: { bg: 'bg-red-100', text: 'text-red-700', bar: 'bg-red-500', label: 'Alto', width: '100%' },
                  medium: { bg: 'bg-amber-100', text: 'text-amber-700', bar: 'bg-amber-400', label: 'Medio', width: '66%' },
                  low: { bg: 'bg-green-100', text: 'text-green-700', bar: 'bg-green-500', label: 'Bajo', width: '33%' },
                  unknown: { bg: 'bg-gray-100', text: 'text-gray-500', bar: 'bg-gray-300', label: 'Sin dato', width: '10%' },
                };
                const c = riesgoColors[item.nivel_riesgo] ?? riesgoColors.unknown;
                return (
                  <div key={idx} className="flex items-center gap-3">
                    <span className="text-xs tabular-nums text-gray-500 w-16 flex-shrink-0">{item.periodo}</span>
                    <div className="flex-1 bg-gray-200 rounded-full h-2.5 overflow-hidden">
                      <div className={`${c.bar} h-2.5 rounded-full transition-all`} style={{ width: c.width }} />
                    </div>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${c.bg} ${c.text} w-16 text-center flex-shrink-0`}>
                      {c.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MateriaRepetidaCard({ materia }: { materia: MateriaRepetida }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="border border-gray-100 rounded-[10px] overflow-hidden transition-all duration-200 hover:shadow-md">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 bg-gray-50/50 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-[10px] bg-white border border-gray-200 flex items-center justify-center text-xs font-semibold text-gray-500 shadow-sm">
            {materia.veces}
          </div>
          <div className="text-left">
            <p className="text-sm font-semibold text-gray-700">{materia.nombre}</p>
            <p className="text-[10px] text-gray-400 font-medium">Cursada {materia.veces} veces en total</p>
          </div>
        </div>
        {isOpen ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </button>

      {isOpen && (
        <div className="p-4 bg-white divide-y divide-gray-50 animate-in fade-in slide-in-from-top-2">
          {materia.intentos.map((intento, idx) => (
            <div key={idx} className="py-2.5 flex items-center justify-between first:pt-0 last:pb-0">
              <div className="flex flex-col">
                <span className="text-xs font-semibold text-gray-600">{intento.periodo}</span>
                <span className={`text-[10px] font-semibold uppercase tracking-wider ${
                  intento.estado === 'Aprobado' ? 'text-green-500'
                    : intento.estado === 'En curso' ? 'text-blue-500' : 'text-red-500'
                }`}>
                  {intento.estado}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-gray-400 font-medium">Definitiva</span>
                <div className={`px-3 py-1 rounded-[10px] tabular-nums text-sm font-semibold ${
                  intento.nota === null
                    ? 'bg-gray-50 text-gray-500 border border-gray-100'
                    : intento.nota < 3.0
                    ? 'bg-red-50 text-red-700 border border-red-100'
                    : intento.nota < 4.0
                    ? 'bg-amber-50 text-amber-700 border border-amber-100'
                    : 'bg-green-50 text-green-700 border border-green-100'
                }`}>
                  {intento.nota === null ? '--' : intento.nota.toFixed(1)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Sección 3: Historial Académico ──────────────────────────────────────────

export interface MateriaCursada {
  codigo: string;
  materia: string;
  creditos: number;
  grupo: string;
  docente: string;
  nota_final: number | null;
  estado: string;
  // HU-31: desglose por corte y alertas por corte abiertas (HU-32)
  corte1: number | null;
  corte2: number | null;
  corte3: number | null;
  examen_final: number | null;
  nota_necesaria_examen: number | null;
  alertas_corte: AlertaCorteResumen[];
}

export interface AlertaCorteResumen {
  id: number;
  clave: string;
  regla: string;
  nivel: string;
  corte: number | null;
  valor_causa: number | null;
  nota_necesaria: number | null;
  estado: string;
}

const NOTA_APROBATORIA = 3.0;

function NotaCelda({ valor, destacada = false }: { valor: number | null; destacada?: boolean }) {
  if (valor === null || valor === undefined) {
    return <span className="text-xs text-gray-300">--</span>;
  }
  const baja = valor < NOTA_APROBATORIA;
  return (
    <span
      className={`tabular-nums text-sm px-2 py-1 rounded ${destacada ? 'font-semibold' : 'font-medium'} ${
        baja ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'
      }`}
    >
      {valor.toFixed(1)}
    </span>
  );
}

export interface HistorialPeriodo {
  periodo: string;
  materias: MateriaCursada[];
  promedio_semestre: number;
  creditos_cursados: number;
  creditos_aprobados: number;
  creditos_intentados: number;
}

function HistorialAcademico({ data, loading }: { data: HistorialPeriodo[] | null, loading: boolean }) {
  const [activeTab, setActiveTab] = useState<string | null>(null);

  useEffect(() => {
    if (data && data.length > 0 && !activeTab) {
      setActiveTab(data[data.length - 1].periodo); // Select the most recent by default
    }
  }, [data, activeTab]);

  const activePeriodData = data?.find(p => p.periodo === activeTab);

  return (
    <div className="bg-white rounded-[14px] border border-line overflow-hidden">
      {/* Header de sección */}
      <div className="bg-white border-b border-line px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-primary-tint flex items-center justify-center">
          <BookOpen className="w-4 h-4 text-primary" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-ink">Historial Académico</h2>
          <p className="text-xs text-ink-muted">Notas por corte y materias cursadas por semestre</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {!loading && data && (
            <span className="text-xs bg-green-50 text-green-700 px-2 py-1 rounded-full border border-green-200">
              {data.length} Periodos
            </span>
          )}
        </div>
      </div>

      {/* Tabs de semestres */}
      <div className="border-b border-gray-100 px-6 pt-4 flex gap-2 overflow-x-auto">
        {loading ? (
          <div className="flex gap-2">
            <div className="w-20 h-8 bg-wash rounded-t-lg animate-pulse" />
            <div className="w-20 h-8 bg-wash rounded-t-lg animate-pulse" />
          </div>
        ) : data && data.length > 0 ? (
          data.map((sem) => (
            <button
              key={sem.periodo}
              onClick={() => setActiveTab(sem.periodo)}
              className={`px-4 py-2 text-xs font-medium rounded-t-lg border-b-2 whitespace-nowrap transition-colors ${
                activeTab === sem.periodo
                  ? 'border-primary text-primary bg-primary-tint'
                  : 'border-transparent text-gray-400 hover:text-gray-600 hover:bg-gray-50'
              }`}
            >
              {sem.periodo}
            </button>
          ))
        ) : (
          <div className="py-2 text-xs text-gray-400">No hay periodos registrados</div>
        )}
      </div>

      {/* Tabla */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['Código', 'Materia', 'Créditos', 'Grupo', 'Docente', 'Corte 1', 'Corte 2', 'Corte 3', 'Examen', 'Nota Final', 'Estado'].map(col => (
                <th key={col} className="px-5 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                  <td className="px-5 py-3.5"><div className="h-3.5 bg-wash rounded w-16 animate-pulse" /></td>
                  <td className="px-5 py-3.5"><div className="h-3.5 bg-wash rounded w-40 animate-pulse" /></td>
                  <td className="px-5 py-3.5"><div className="h-3.5 bg-wash rounded w-8 animate-pulse" /></td>
                  <td className="px-5 py-3.5"><div className="h-3.5 bg-wash rounded w-8 animate-pulse" /></td>
                  <td className="px-5 py-3.5"><div className="h-3.5 bg-wash rounded w-32 animate-pulse" /></td>
                  {Array.from({ length: 5 }).map((__, j) => (
                    <td key={j} className="px-5 py-3.5"><div className="h-3.5 bg-wash rounded w-10 animate-pulse" /></td>
                  ))}
                  <td className="px-5 py-3.5"><div className="h-5 bg-wash rounded-full w-16 animate-pulse" /></td>
                </tr>
              ))
            ) : activePeriodData ? (
              activePeriodData.materias.map((mat, i) => (
                <tr key={mat.codigo} className="bg-white hover:bg-paper transition-colors duration-150">
                  <td className="px-5 py-3.5 text-xs tabular-nums text-gray-500">{mat.codigo}</td>
                  <td className="px-5 py-3.5 text-sm font-medium text-gray-900">
                    {mat.materia}
                    {mat.alertas_corte && mat.alertas_corte.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {mat.alertas_corte.map(a => (
                          <span
                            key={a.id}
                            title={a.regla}
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800 border border-amber-200"
                          >
                            <AlertTriangle className="w-3 h-3" />
                            {a.corte ? `Alerta corte ${a.corte}` : 'Alerta examen'} ({a.clave})
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-sm text-gray-500 text-center">{mat.creditos}</td>
                  <td className="px-5 py-3.5 text-sm text-gray-500 text-center">{mat.grupo}</td>
                  <td className="px-5 py-3.5 text-sm text-gray-500 truncate max-w-[200px]" title={mat.docente}>{mat.docente}</td>
                  <td className="px-5 py-3.5 text-center"><NotaCelda valor={mat.corte1} /></td>
                  <td className="px-5 py-3.5 text-center"><NotaCelda valor={mat.corte2} /></td>
                  <td className="px-5 py-3.5 text-center"><NotaCelda valor={mat.corte3} /></td>
                  <td className="px-5 py-3.5 text-center">
                    <NotaCelda valor={mat.examen_final} />
                    {mat.nota_necesaria_examen !== null && mat.nota_necesaria_examen !== undefined && (
                      <p
                        className={`mt-1 text-[10px] ${mat.nota_necesaria_examen > 5 ? 'text-red-600 font-semibold' : 'text-gray-400'}`}
                        title="Nota necesaria en el examen final para aprobar con 3.0"
                      >
                        Necesita {mat.nota_necesaria_examen.toFixed(1)}
                      </p>
                    )}
                  </td>
                  <td className="px-5 py-3.5"><NotaCelda valor={mat.nota_final} destacada /></td>
                  <td className="px-5 py-3.5">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                      mat.estado === 'Aprobado'
                        ? 'bg-green-100 text-green-700'
                        : mat.estado === 'En curso'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-red-100 text-red-700'
                    }`}>
                      {mat.estado}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={11} className="px-5 py-8 text-center text-sm text-gray-400">
                  No hay materias para mostrar en este periodo.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Footer estadístico del periodo */}
      <div className="border-t border-gray-100 px-6 py-4 flex items-center justify-between bg-gray-50">
        <div className="flex items-center gap-6">
          <div>
            <p className="text-[10px] uppercase font-semibold text-gray-400">Promedio del Semestre</p>
            <p className="text-lg font-semibold text-gray-800">
              {loading ? <span className="text-gray-300 animate-pulse">--</span> : activePeriodData?.promedio_semestre.toFixed(2) || '0.00'}
            </p>
          </div>
          <div>
            <p className="text-[10px] uppercase font-semibold text-gray-400">Créditos Cursados</p>
            <p className="text-lg font-semibold text-gray-800">
              {loading ? <span className="text-gray-300 animate-pulse">--</span> : activePeriodData?.creditos_intentados || 0}
            </p>
          </div>
          <div>
            <p className="text-[10px] uppercase font-semibold text-gray-400">Créditos Aprobados</p>
            <p className="text-lg font-semibold text-green-600">
              {loading ? <span className="text-gray-300 animate-pulse">--</span> : activePeriodData?.creditos_aprobados || 0}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export interface Intervencion {
  id: number;
  tipo: string;
  observaciones: string;
  evidencia: string | null;
  resultado: string | null;
  fecha: string;
  usuario: string;
  usuario_rol: string;
  alerta_id: number;
  alerta_causa: string;
  alerta_estado: string;
}

function HistorialIntervenciones({ data, loading }: { data: Intervencion[] | null; loading: boolean }) {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Intervencion | null>(null); // 4.1

  const TIPO_LABEL: Record<string, string> = {
    TUTORIA: 'Tutoría', CITACION: 'Citación', REMISION: 'Remisión',
  };
  const TIPO_COLOR: Record<string, string> = {
    TUTORIA: 'bg-blue-100 text-blue-700',
    CITACION: 'bg-amber-100 text-amber-700',
    REMISION: 'bg-purple-100 text-purple-700',
  };

  return (
    <div className="bg-white rounded-[14px] border border-line overflow-hidden">
      {/* Panel lateral de detalle — 4.1 */}
      {selected && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/30" onClick={() => setSelected(null)} />
          <div className="relative z-10 w-full max-w-md bg-white shadow-2xl flex flex-col h-full overflow-y-auto">
            {/* Header del panel */}
            <div className="bg-red-800 px-6 py-4 flex items-center justify-between sticky top-0">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-white" />
                <div>
                  <h2 className="text-sm font-semibold text-white">Detalle de Intervención</h2>
                  <p className="text-[10px] text-red-200">#{selected.id}</p>
                </div>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="text-white/80 hover:text-white transition-colors p-1 rounded-[10px] hover:bg-white/10"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Contenido del panel */}
            <div className="p-6 space-y-5 flex-1">
              {/* Tipo y fecha */}
              <div className="flex items-center justify-between">
                <span className={`text-xs font-semibold px-3 py-1.5 rounded-full ${TIPO_COLOR[selected.tipo] ?? 'bg-gray-100 text-gray-600'}`}>
                  {TIPO_LABEL[selected.tipo] ?? selected.tipo}
                </span>
                <span className="text-xs tabular-nums text-gray-400">{selected.fecha}</span>
              </div>

              {/* Causa de la alerta */}
              <div className="bg-red-50 border border-red-100 rounded-[10px] p-4">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-red-400 mb-1">Causa de la Alerta</p>
                <p className="text-sm font-semibold text-red-800">
                  {selected.alerta_causa}
                  <span className="ml-2 text-xs tabular-nums text-red-400">(Alerta #{selected.alerta_id})</span>
                </p>
                <span className={`mt-2 inline-block text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                  selected.alerta_estado === 'activa' || selected.alerta_estado === 'active'
                    ? 'bg-red-100 text-red-700'
                    : selected.alerta_estado === 'cerrada' || selected.alerta_estado === 'closed'
                    ? 'bg-gray-100 text-gray-600'
                    : 'bg-amber-100 text-amber-700'
                }`}>
                  {selected.alerta_estado}
                </span>
              </div>

              {/* Atendido por */}
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Atendido por</p>
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-xs font-semibold text-gray-500">
                    {selected.usuario.charAt(0)}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-800">{selected.usuario}</p>
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
                      selected.usuario_rol === 'BIENESTAR' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                    }`}>
                      {selected.usuario_rol}
                    </span>
                  </div>
                </div>
              </div>

              {/* Observaciones */}
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-2">Observaciones</p>
                <div className="bg-gray-50 rounded-[10px] p-4 border border-gray-100">
                  <p className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">
                    {selected.observaciones}
                  </p>
                </div>
              </div>

              {/* Resultado */}
              {selected.resultado && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-green-600 mb-2">Resultado / Conclusión</p>
                  <div className="bg-green-50 rounded-[10px] p-4 border border-green-100">
                    <p className="text-sm text-green-800 font-medium leading-relaxed">
                      {selected.resultado}
                    </p>
                  </div>
                </div>
              )}

              {/* Evidencia */}
              {selected.evidencia && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-2">Evidencia adjunta</p>
                  <a
                    href={selected.evidencia}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-xs text-primary font-semibold bg-red-50 border border-red-100 px-4 py-2.5 rounded-[10px] hover:bg-red-100 transition-colors"
                  >
                    <FileText className="w-4 h-4" />
                    Ver documento adjunto
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex gap-3">
              <button
                onClick={() => navigate(`/dashboard/intervenciones/${selected.id}/evidencias`)}
                className="flex-1 px-4 py-2.5 text-sm font-semibold text-white bg-primary rounded-[10px] hover:bg-red-700 transition-colors flex items-center justify-center gap-2"
              >
                <ExternalLink className="w-4 h-4" />
                Ver Evidencias
              </button>
              <button
                onClick={() => setSelected(null)}
                className="flex-1 px-4 py-2.5 text-sm font-semibold text-gray-600 border border-gray-200 rounded-[10px] hover:bg-white transition-colors"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header de sección */}
      <div className="bg-white border-b border-line px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-primary-tint flex items-center justify-center">
          <History className="w-4 h-4 text-primary" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-ink">Historial de Intervenciones</h2>
          <p className="text-xs text-ink-muted">Seguimiento de acciones de acompañamiento realizadas al estudiante</p>
        </div>
        {!loading && data && data.length > 0 && (
          <div className="ml-auto">
            <span className="text-xs bg-wash text-ink-soft px-2.5 py-1 rounded-full font-semibold">
              {data.length} {data.length === 1 ? 'Intervención' : 'Intervenciones'}
            </span>
          </div>
        )}
      </div>

      {/* Contenido */}
      <div className="p-6">
        {loading ? (
          <div className="space-y-4">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="flex gap-4 p-4 border border-gray-100 rounded-[10px] animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-24" />
                <div className="h-4 bg-gray-200 rounded w-48" />
                <div className="h-4 bg-gray-200 rounded w-32" />
              </div>
            ))}
          </div>
        ) : !data || data.length === 0 ? (
          <div className="text-center py-10">
            <History className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-sm font-semibold text-gray-500">No hay intervenciones registradas</p>
            <p className="text-xs text-gray-400 mt-1">El estudiante no cuenta con acciones de seguimiento en este momento.</p>
          </div>
        ) : (
          <div className="relative border-l-2 border-line ml-4 pl-6 space-y-6">
            {data.map((intervencion) => (
              <div key={intervencion.id} className="relative">
                {/* Dot/Indicator */}
                <div className="absolute -left-[31px] top-1.5 w-4 h-4 rounded-full border-2 border-white bg-primary shadow-sm ring-4 ring-primary-tint" />

                {/* Tarjeta clickeable — 4.1 */}
                <button
                  onClick={() => setSelected(intervencion)}
                  className="w-full text-left bg-gray-50/50 rounded-[10px] p-5 border border-gray-200 hover:border-red-200 hover:bg-white hover:shadow-md transition-all duration-200 shadow-sm group"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-gray-800 group-hover:text-primary transition-colors">
                        {TIPO_LABEL[intervencion.tipo] ?? intervencion.tipo}
                      </span>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                        intervencion.usuario_rol === 'BIENESTAR'
                          ? 'bg-purple-100 text-purple-700'
                          : 'bg-blue-100 text-blue-700'
                      }`}>
                        {intervencion.usuario_rol}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400 tabular-nums">{intervencion.fecha}</span>
                      <ExternalLink className="w-3.5 h-3.5 text-gray-300 group-hover:text-primary transition-colors" />
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 line-clamp-2 text-left">
                    <span className="font-semibold text-gray-600">Alerta: </span>
                    {intervencion.alerta_causa}
                  </p>
                  <p className="text-[10px] text-gray-400 mt-1 text-left">
                    Por: <span className="font-medium text-gray-600">{intervencion.usuario}</span>
                    {intervencion.resultado && (
                      <span className="ml-2 text-green-500 font-semibold">· Con resultado</span>
                    )}
                  </p>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── HU-34: Asistencia del estudiante ───────────────────────────────────────
interface AsistenciaDetalle {
  fecha: string;
  estado: 'ASISTIO' | 'FALTA' | 'FALTA_JUSTIFICADA';
  observacion: string | null;
}

interface AsistenciaCurso {
  curso_id: number;
  materia: string;
  codigo: string;
  grupo: string;
  total_clases: number;
  asistencias: number;
  faltas: number;
  faltas_justificadas: number;
  porcentaje: number | null;
  umbral: number | null;                        // HU-35: umbral efectivo del curso
  origen_umbral: 'curso' | 'general' | null;
  supera_umbral: boolean | null;                // null sin umbral configurado
  cerca_umbral: boolean | null;                 // se aproxima al umbral sin superarlo
  umbral_aviso: number | null;                  // porcentaje desde el que se advierte
  detalle: AsistenciaDetalle[];
}

interface AsistenciaEstudianteData {
  periodo: string | null;
  periodos_disponibles: string[];
  umbral: number | null;                        // HU-35: umbral general
  cursos: AsistenciaCurso[];
}

const ESTADO_ASISTENCIA: Record<AsistenciaDetalle['estado'], { label: string; className: string }> = {
  ASISTIO:           { label: 'Asistió',           className: 'bg-green-100 text-green-700' },
  FALTA:             { label: 'Falta',             className: 'bg-red-100 text-red-700' },
  FALTA_JUSTIFICADA: { label: 'Falta justificada', className: 'bg-amber-100 text-amber-700' },
};

function AsistenciaEstudiante({ codigo }: { codigo: string }) {
  const [data, setData] = useState<AsistenciaEstudianteData | null>(null);
  const [periodo, setPeriodo] = useState('');
  const [cursoFiltro, setCursoFiltro] = useState('');
  const [expandido, setExpandido] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const cargar = async () => {
      setLoading(true);
      setError(null);
      try {
        const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const query = periodo ? `?periodo=${encodeURIComponent(periodo)}` : '';
        const res = await apiFetch(`${baseUrl}/api/academico/students/${codigo}/asistencia/${query}`);
        if (!res.ok) throw new Error('No se pudo cargar la asistencia del estudiante.');
        const json: AsistenciaEstudianteData = await res.json();
        setData(json);
        if (!periodo && json.periodo) setPeriodo(json.periodo);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    cargar();
  }, [codigo, periodo]);

  const cursos = (data?.cursos ?? []).filter(c => !cursoFiltro || String(c.curso_id) === cursoFiltro);
  const cursosCerca = cursos.filter(c => c.cerca_umbral);
  const cursosSobre = cursos.filter(c => c.supera_umbral);

  return (
    <div className="bg-white rounded-[14px] border border-line overflow-hidden">
      <div className="bg-white border-b border-line px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-primary-tint flex items-center justify-center">
          <Calendar className="w-4 h-4 text-primary" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-ink">Asistencia</h2>
          <p className="text-xs text-ink-muted">
            Porcentaje de inasistencia por curso.{' '}
            {data?.umbral != null ? `Umbral general: ${data.umbral}%` : 'Sin umbral general activo'}
          </p>
        </div>
      </div>

      {/* Filtros */}
      <div className="px-6 py-4 border-b border-gray-100 flex flex-wrap gap-4">
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-500">
          Periodo
          <select
            value={periodo}
            onChange={e => { setPeriodo(e.target.value); setCursoFiltro(''); setExpandido(null); }}
            className="h-10 px-3 text-sm border border-line-strong rounded-[10px] bg-white text-gray-800 transition-colors hover:border-ink-faint"
          >
            {(data?.periodos_disponibles ?? []).map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-500">
          Curso
          <select
            value={cursoFiltro}
            onChange={e => { setCursoFiltro(e.target.value); setExpandido(null); }}
            className="h-10 px-3 text-sm border border-line-strong rounded-[10px] bg-white text-gray-800 transition-colors hover:border-ink-faint"
          >
            <option value="">Todos los cursos</option>
            {(data?.cursos ?? []).map(c => (
              <option key={c.curso_id} value={String(c.curso_id)}>
                {c.materia} - Grupo {c.grupo}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Avisos: cursos que superan el umbral o se aproximan a él */}
      {!loading && !error && (cursosSobre.length > 0 || cursosCerca.length > 0) && (
        <div className="px-6 pt-4 space-y-2">
          {cursosSobre.length > 0 && (
            <div className="flex items-start gap-2 rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <p>
                <strong>Supera el umbral de inasistencia</strong> en{' '}
                {cursosSobre.map(c => `${c.materia} (${c.porcentaje?.toFixed(2)}% de ${c.umbral}%)`).join(', ')}.
              </p>
            </div>
          )}
          {cursosCerca.length > 0 && (
            <div className="flex items-start gap-2 rounded-[10px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <p>
                <strong>Se aproxima al umbral de inasistencia</strong> en{' '}
                {cursosCerca.map(c => `${c.materia} (${c.porcentaje?.toFixed(2)}% de ${c.umbral}%)`).join(', ')}.
                {' '}Al estudiante se le envía un aviso preventivo por correo.
              </p>
            </div>
          )}
        </div>
      )}

      {error ? (
        <div className="px-6 py-8 text-center text-sm text-red-600">{error}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {['', 'Materia', 'Grupo', 'Clases', 'Faltas', 'Faltas justificadas', '% Inasistencia'].map(col => (
                  <th key={col} className="px-5 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-sm text-gray-400 animate-pulse">
                    Cargando asistencia...
                  </td>
                </tr>
              ) : cursos.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-sm text-gray-400">
                    No hay cursos para mostrar en este periodo.
                  </td>
                </tr>
              ) : (
                cursos.map(c => {
                  const abierto = expandido === c.curso_id;
                  return [
                    <tr
                      key={c.curso_id}
                      onClick={() => setExpandido(abierto ? null : c.curso_id)}
                      className="cursor-pointer hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-5 py-3.5 text-gray-400">
                        {abierto ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </td>
                      <td className="px-5 py-3.5 text-sm font-medium text-gray-900">
                        {c.materia}
                        <span className="block text-xs tabular-nums text-gray-400">{c.codigo}</span>
                      </td>
                      <td className="px-5 py-3.5 text-sm text-gray-500">{c.grupo}</td>
                      <td className="px-5 py-3.5 text-sm text-gray-700">{c.total_clases}</td>
                      <td className="px-5 py-3.5 text-sm text-gray-700">{c.faltas}</td>
                      <td className="px-5 py-3.5 text-sm text-gray-700">{c.faltas_justificadas}</td>
                      <td className="px-5 py-3.5">
                        {c.porcentaje === null ? (
                          <span className="text-xs text-gray-400">Sin registros</span>
                        ) : (
                          <span className={`tabular-nums text-sm font-semibold px-2 py-1 rounded ${
                            c.supera_umbral
                              ? 'bg-red-50 text-red-700'
                              : c.cerca_umbral
                                ? 'bg-amber-50 text-amber-700'
                                : 'bg-green-50 text-green-700'
                          }`}>
                            {c.porcentaje.toFixed(2)}%
                          </span>
                        )}
                        {c.cerca_umbral && (
                          <span className="block text-[11px] font-semibold text-amber-700 mt-1">
                            Cerca del umbral (aviso desde {c.umbral_aviso}%)
                          </span>
                        )}
                        {c.origen_umbral === 'curso' && c.umbral !== null && (
                          <span className="block text-[11px] text-gray-500 mt-1">Umbral del curso: {c.umbral}%</span>
                        )}
                      </td>
                    </tr>,
                    abierto && (
                      <tr key={`${c.curso_id}-detalle`} className="bg-gray-50/60">
                        <td colSpan={7} className="px-10 py-4">
                          {c.detalle.length === 0 ? (
                            <p className="text-sm text-gray-400">Sin registros de asistencia en este curso.</p>
                          ) : (
                            <table className="w-full">
                              <thead>
                                <tr>
                                  {['Fecha', 'Estado', 'Observación'].map(col => (
                                    <th key={col} className="py-2 text-left text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                                      {col}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-100">
                                {c.detalle.map(d => (
                                  <tr key={d.fecha}>
                                    <td className="py-2 text-sm tabular-nums text-gray-600">{d.fecha}</td>
                                    <td className="py-2">
                                      <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${ESTADO_ASISTENCIA[d.estado].className}`}>
                                        {ESTADO_ASISTENCIA[d.estado].label}
                                      </span>
                                    </td>
                                    <td className="py-2 text-sm text-gray-500">{d.observacion || '—'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </td>
                      </tr>
                    ),
                  ];
                })
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Página principal StudentProfile ─────────────────────────────────────────
export default function StudentProfile() {
  const { id } = useParams();
  const [student, setStudent] = useState<StudentDetail | null>(null);
  const [indicadores, setIndicadores] = useState<IndicadoresData | null>(null);
  const [historial, setHistorial] = useState<HistorialPeriodo[] | null>(null);
  const [intervenciones, setIntervenciones] = useState<Intervencion[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recalculating, setRecalculating] = useState(false);
  const [recalcMsg, setRecalcMsg] = useState<string | null>(null);
  const [pestana, setPestana] = useState<'resumen' | 'asistencia'>('resumen');

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        
        // Cargar datos del perfil, indicadores e historial en paralelo
        const [studentRes, indicatorsRes, historialRes, intervencionesRes] = await Promise.all([
          apiFetch(`${baseUrl}/api/academico/students/${id}/`),
          apiFetch(`${baseUrl}/api/academico/students/${id}/indicators/`),
          apiFetch(`${baseUrl}/api/academico/students/${id}/history/`),
          apiFetch(`${baseUrl}/api/academico/students/${id}/intervenciones/`)
        ]);

        if (!studentRes.ok) {
          if (studentRes.status === 404) throw new Error('Estudiante no encontrado');
          throw new Error('Error al cargar la información del perfil');
        }
        
        const studentData = await studentRes.json();
        setStudent(studentData);

        if (indicatorsRes.ok) {
          const indicatorsData = await indicatorsRes.json();
          setIndicadores(indicatorsData.indicadores);
        }

        if (historialRes.ok) {
          const historialData = await historialRes.json();
          setHistorial(historialData.historial);
        }

        if (intervencionesRes.ok) {
          const intervencionesData = await intervencionesRes.json();
          setIntervenciones(intervencionesData.intervenciones);
        }
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (id) fetchData();
  }, [id]);

  const handleRecalcular = async () => {
    if (!id) return;
    setRecalculating(true);
    setRecalcMsg(null);
    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await apiFetch(`${baseUrl}/api/alertas/estudiantes/${id}/recalcular/`, {
        method: 'POST',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Error al recalcular');

      // Refrescar datos del perfil e indicadores con los nuevos valores
      const [studentRes, indicatorsRes] = await Promise.all([
        apiFetch(`${baseUrl}/api/academico/students/${id}/`),
        apiFetch(`${baseUrl}/api/academico/students/${id}/indicators/`),
      ]);
      if (studentRes.ok) setStudent(await studentRes.json());
      if (indicatorsRes.ok) {
        const d = await indicatorsRes.json();
        setIndicadores(d.indicadores);
      }

      const nivelLabel: Record<string, string> = { high: 'Alto', medium: 'Medio', low: 'Bajo', unknown: 'Desconocido' };
      setRecalcMsg(`Datos actualizados. Nivel de riesgo: ${nivelLabel[data.nivel_riesgo] ?? data.nivel_riesgo}`);
      setTimeout(() => setRecalcMsg(null), 5000);
    } catch (err: any) {
      setRecalcMsg(`Error: ${err.message}`);
      setTimeout(() => setRecalcMsg(null), 5000);
    } finally {
      setRecalculating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
        <p className="text-gray-500 animate-pulse">Obteniendo ficha académica e indicadores...</p>
      </div>
    );
  }

  if (error || !student) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-6 text-center">
        <div className="w-20 h-20 rounded-full bg-red-50 flex items-center justify-center">
          <AlertTriangle className="w-10 h-10 text-red-500" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-gray-900">{error || 'Estudiante no encontrado'}</h2>
          <p className="text-gray-500 mt-2">No se pudo recuperar la información del código {id}</p>
        </div>
        <Link to="/dashboard/students">
          <Button variant="outline">Volver al listado</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Volver y acciones */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/dashboard/students" className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink rounded-[10px]">
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          Volver a Estudiantes
        </Link>
        <Button
          variant="outline"
          onClick={handleRecalcular}
          disabled={recalculating || loading}
          title="Recalcula el promedio desde las notas y actualiza el nivel de riesgo"
          className="gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${recalculating ? 'animate-spin' : ''}`} aria-hidden="true" />
          {recalculating ? 'Actualizando...' : 'Actualizar riesgo'}
        </Button>
      </div>

      {/* Mensaje de resultado del recálculo */}
      {recalcMsg && (
        <div role="status" className={`flex items-center gap-3 px-4 py-3 rounded-[10px] text-sm font-medium border ${
          recalcMsg.startsWith('Error')
            ? 'bg-red-50 border-red-200 text-red-800'
            : 'bg-green-50 border-green-200 text-green-800'
        }`}>
          {recalcMsg.startsWith('Error')
            ? <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            : <CheckCircle2 className="w-4 h-4 flex-shrink-0" />}
          {recalcMsg}
        </div>
      )}

      {/* Cabecera del estudiante: quién es y cómo va, en una sola lectura */}
      <header className="bg-white border border-line rounded-[14px] overflow-hidden">
        <div className="p-5 sm:p-6 flex flex-wrap items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-primary-tint text-primary-strong text-lg font-semibold flex items-center justify-center shrink-0" aria-hidden="true">
            {student.nombre.trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join('').toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-[1.65rem] font-semibold text-ink leading-tight tracking-[-0.02em]">{student.nombre}</h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-muted">
              <span>Código: <span className="font-semibold text-ink">{student.codigo}</span></span>
              <span className="inline-flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" aria-hidden="true" />
                {student.semestre}° Semestre
              </span>
              <span className="inline-flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" />
                {student.estado_matricula}
              </span>
            </p>
          </div>
        </div>

        <dl className="grid grid-cols-1 sm:grid-cols-3 border-t border-line divide-y sm:divide-y-0 sm:divide-x divide-line">
          <div className="px-5 sm:px-6 py-4">
            <dt className="text-sm font-medium text-ink-muted">Riesgo actual</dt>
            <dd className="mt-2">
              <NivelRiesgoChip nivel={student.nivel_riesgo} className="text-sm" />
            </dd>
          </div>
          <div className="px-5 sm:px-6 py-4">
            <dt className="text-sm font-medium text-ink-muted">Promedio Acumulado</dt>
            <dd className={`mt-1 text-3xl font-semibold leading-none tracking-[-0.02em] ${
              student.promedio != null && student.promedio < 3 ? 'text-riesgo-critico' : 'text-ink'
            }`}>
              {student.promedio?.toFixed(2) || '—'}
              <span className="ml-1.5 text-sm font-medium text-ink-muted tracking-normal">de 5.00</span>
            </dd>
          </div>
          <div className="px-5 sm:px-6 py-4">
            <dt className="text-sm font-medium text-ink-muted">Alertas</dt>
            <dd className="mt-1 text-3xl font-semibold leading-none tracking-[-0.02em] text-ink">
              {student.alertas_activas > 0 ? (
                <span className="text-base font-semibold text-riesgo-critico tracking-normal">{student.alertas_activas} ALERTAS ACTIVAS</span>
              ) : (
                <span className="text-base font-medium text-ink-muted tracking-normal">Sin alertas activas</span>
              )}
            </dd>
          </div>
        </dl>
      </header>

      {/* Pestañas */}
      <div className="flex gap-6 border-b border-line">
        {([['resumen', 'Resumen académico'], ['asistencia', 'Asistencia']] as const).map(([clave, label]) => (
          <button
            key={clave}
            onClick={() => setPestana(clave)}
            aria-pressed={pestana === clave}
            className={`-mb-px pb-2.5 text-sm font-semibold border-b-2 ${
              pestana === clave
                ? 'border-primary text-primary-strong'
                : 'border-transparent text-ink-muted hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {pestana === 'asistencia' ? (
        <div key="asistencia" className="">
          <AsistenciaEstudiante codigo={student.codigo} />
        </div>
      ) : (
        <div key="resumen" className="space-y-6 ">
        {/* ── Bloque 1: Ficha Académica ─────────────────────────────────────── */}
        <FichaAcademica student={student} />

        {/* ── Bloque 2: Indicadores ────────────────────────────────────────── */}
        <IndicadoresSection data={indicadores} loading={loading} studentName={student.nombre} historial={historial} />

        {/* ── Bloque 3: Historial Académico ────────────────────────────────── */}
        <HistorialAcademico data={historial} loading={loading} />

        {/* ── Bloque 4: Historial de Intervenciones ────────────────────────── */}
        <HistorialIntervenciones data={intervenciones} loading={loading} />
        </div>
      )}
    </div>
  );
}
