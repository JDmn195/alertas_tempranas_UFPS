import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router';
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
  TrendingUp as TrendingUpIcon,
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
import { Badge } from '../components/ui/Badge';

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

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      {/* Header de sección */}
      <div className="bg-[#C8102E] px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
          <User className="w-4 h-4 text-white" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-white">Ficha Académica</h2>
          <p className="text-xs text-red-200">Información personal y académica del estudiante</p>
        </div>
        <div className="ml-auto">
          <span className="text-xs bg-white/20 text-white px-2 py-1 rounded-full">
            Datos Verificados
          </span>
        </div>
      </div>

      {/* Contenido placeholder */}
      <div className="p-6">
        <div className="grid grid-cols-2 gap-6">
          {/* Col izquierda: datos personales */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-gray-100 pb-2">
              Datos Personales
            </h3>
            {[
              { icon: User,      label: 'Nombre Completo',       value: student.nombre },
              { icon: Hash,      label: 'Código Estudiantil',    value: student.codigo },
              { icon: FileText,  label: 'Tipo de Documento',     value: student.tipo_documento },
              { icon: Hash,      label: 'Número de Documento',   value: student.numero_documento },
              { icon: Phone,     label: 'Celular',               value: student.celular || 'No registrado' },
              { icon: Mail,      label: 'Correo Personal',       value: student.email_personal || 'No registrado' },
              { icon: Mail,      label: 'Correo Institucional',  value: student.email_institucional || 'No registrado' },
              { icon: MapPin,    label: 'Municipio Nacimiento',  value: student.municipio_nacimiento || 'No registrado' },
            ].map(({ icon: Icon, label, value }) => (
              <div key={label} className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center flex-shrink-0">
                  <Icon className="w-4 h-4 text-[#C8102E]" />
                </div>
                <div>
                  <p className="text-xs text-gray-400">{label}</p>
                  <p className="text-sm text-gray-900 font-medium">{value}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Col derecha: datos académicos */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-100 pb-2">
              Datos Académicos
            </h3>
            {[
              { icon: Layers,       label: 'Semestre Actual',     value: `${student.semestre}° Semestre` },
              { icon: BookOpen,     label: 'Pensum',              value: student.pensum || 'No definido' },
              { icon: Calendar,     label: 'Fecha de Ingreso',    value: student.ingreso || 'Sin dato' },
              { icon: GraduationCap,label: 'Estado de Matrícula', value: student.estado_matricula },
              { icon: MapPin,       label: 'Colegio Egresado',    value: student.colegio_egresado || 'No registrado' },
            ].map(({ icon: Icon, label, value }) => (
              <div key={label} className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center flex-shrink-0">
                  <Icon className="w-4 h-4 text-[#C8102E]" />
                </div>
                <div>
                  <p className="text-xs text-gray-400">{label}</p>
                  <p className="text-sm text-gray-900 font-medium">{value}</p>
                </div>
              </div>
            ))}

            {/* Nivel de riesgo real */}
            <div className={`mt-6 rounded-lg p-4 text-center border-2 ${
              student.nivel_riesgo === 'high' ? 'bg-red-50 border-red-200' :
              student.nivel_riesgo === 'medium' ? 'bg-yellow-50 border-yellow-200' :
              student.nivel_riesgo === 'low' ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'
            }`}>
              <AlertTriangle className={`w-6 h-6 mx-auto mb-1 ${
                student.nivel_riesgo === 'high' ? 'text-red-500' :
                student.nivel_riesgo === 'medium' ? 'text-yellow-500' :
                student.nivel_riesgo === 'low' ? 'text-green-500' : 'text-gray-400'
              }`} />
              <p className="text-xs text-gray-500 font-bold uppercase tracking-wider">Nivel de Riesgo</p>
              <p className={`text-lg font-black ${
                student.nivel_riesgo === 'high' ? 'text-red-700' :
                student.nivel_riesgo === 'medium' ? 'text-yellow-700' :
                student.nivel_riesgo === 'low' ? 'text-green-700' : 'text-gray-500'
              }`}>
                {student.nivel_riesgo === 'high' ? 'ALTO' :
                 student.nivel_riesgo === 'medium' ? 'MEDIO' :
                 student.nivel_riesgo === 'low' ? 'BAJO' : 'DESCONOCIDO'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface Intento {
  periodo: string;
  nota: number;
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
}

function IndicadoresSection({ data, loading }: { data: IndicadoresData | null; loading: boolean }) {
  const indicadores = [
    {
      icon: BarChart2,
      label: 'Promedio Acumulado',
      sublabel: 'Sobre escala de 0 a 5',
      color: 'blue',
      value: data?.promedio_acumulado ? data.promedio_acumulado.toFixed(2) : null,
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
    },
    {
      icon: AlertTriangle,
      label: 'Alertas Activas',
      sublabel: 'Alertas sin resolver',
      color: 'red',
      value: data?.alertas_activas ?? 0,
    },
    {
      icon: CheckCircle2,
      label: 'Materias Aprobadas',
      sublabel: 'Total acumulado',
      color: 'green',
      value: data?.aprobadas,
    },
    {
      icon: Activity,
      label: 'Materias Reprobadas',
      sublabel: 'Total acumulado',
      color: 'orange',
      value: data?.reprobadas,
    },
    {
      icon: Clock,
      label: 'Créditos Cursados',
      sublabel: 'Sobre total del pensum',
      color: 'teal',
      value: data ? `${data.creditos_cursados} créditos | ${data.porcentaje_progreso}%` : null,
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
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      {/* Header de sección */}
      <div className="bg-gray-800 px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
          <BarChart2 className="w-4 h-4 text-white" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-white">Indicadores de Desempeño</h2>
          <p className="text-xs text-gray-400">Métricas clave del rendimiento académico</p>
        </div>
        {!loading && (
          <div className="ml-auto">
            <span className="text-xs bg-green-500/20 text-green-300 px-2 py-1 rounded-full border border-green-500/30">
              Datos Actualizados
            </span>
          </div>
        )}
      </div>

      {/* Grid de indicadores */}
      <div className="p-6">
        <div className="grid grid-cols-3 gap-4">
          {indicadores.map(({ icon: Icon, label, sublabel, color, value }) => (
            <div
              key={label}
              className={`rounded-xl border ${colorMap[color].split(' ').slice(0,2).join(' ')} p-4 flex flex-col items-center text-center gap-2`}
            >
              <div className={`w-10 h-10 rounded-full ${colorMap[color].split(' ').slice(0,2).join(' ')} flex items-center justify-center`}>
                <Icon className={`w-5 h-5 ${colorMap[color].split(' ').slice(2).join(' ')}`} />
              </div>
              
              {/* Valor Real o Placeholder */}
              {loading || (value === null && label !== 'Promedio Acumulado' && label !== 'Tendencia del Promedio' && label !== 'Alertas Activas') ? (
                <div className="w-12 h-8 rounded bg-gray-100 animate-pulse" />
              ) : (
                <div className="text-lg font-bold text-gray-800">
                  {value ?? '—'}
                </div>
              )}

              <div>
                <p className="text-xs font-semibold text-gray-600">{label}</p>
                <p className="text-xs text-gray-400">{sublabel}</p>
              </div>
            </div>
          ))}
        </div>

        {/* ─── Sub-sección: Materias Repetidas (Acordeón) ─────────────────── */}
        {data && data.materias_repetidas.length > 0 && (
          <div className="mt-8 space-y-4">
            <div className="flex items-center gap-2 px-2 pb-2 border-b border-gray-100">
              <History className="w-4 h-4 text-gray-400" />
              <h3 className="text-sm font-bold text-gray-700 uppercase tracking-tight">
                Historial de Materias Repetidas
              </h3>
              <span className="ml-auto text-[10px] bg-amber-100 text-amber-600 px-2 py-0.5 rounded-full font-bold">
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
        <div className="mt-6 rounded-xl border border-gray-100 bg-gray-50/30 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-sm font-bold text-gray-700">Evolución del Promedio Acumulado</h3>
              <p className="text-xs text-gray-400 mt-0.5">Historial del PPA periodo a periodo</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full bg-[#C8102E]" />
                <span className="text-[10px] font-bold text-gray-500 uppercase">Promedio Acumulado</span>
              </div>
            </div>
          </div>
          
          <div className="h-64 w-full">
            {loading ? (
              <div className="w-full h-full bg-gray-100 animate-pulse rounded-lg" />
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
                    tick={{ fontSize: 10, fontWeight: 600, fill: '#9ca3af' }}
                    dy={10}
                  />
                  <YAxis 
                    domain={[2, 5]} 
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 10, fontWeight: 600, fill: '#9ca3af' }}
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
              <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 border-2 border-dashed border-gray-100 rounded-xl">
                <Activity className="w-8 h-8 mb-2 opacity-20" />
                <p className="text-xs font-medium">No hay datos históricos suficientes</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MateriaRepetidaCard({ materia }: { materia: MateriaRepetida }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden transition-all duration-200 hover:shadow-md">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 bg-gray-50/50 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-white border border-gray-200 flex items-center justify-center text-xs font-bold text-gray-500 shadow-sm">
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
                <span className="text-xs font-bold text-gray-600">{intento.periodo}</span>
                <span className={`text-[10px] font-bold uppercase tracking-wider ${
                  intento.estado === 'Aprobado' ? 'text-green-500' : 'text-red-500'
                }`}>
                  {intento.estado}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-gray-400 font-medium">Definitiva</span>
                <div className={`px-3 py-1 rounded-lg font-mono text-sm font-bold ${
                  intento.nota < 3.0 
                    ? 'bg-red-50 text-red-700 border border-red-100'
                    : intento.nota < 4.0
                    ? 'bg-amber-50 text-amber-700 border border-amber-100'
                    : 'bg-green-50 text-green-700 border border-green-100'
                }`}>
                  {intento.nota.toFixed(1)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Sección 3: Historial Académico (placeholder) ─────────────────────────────
function HistorialAcademico() {
  const placeholderRows = Array.from({ length: 6 }, (_, i) => i);

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      {/* Header de sección */}
      <div className="bg-gray-700 px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
          <BookOpen className="w-4 h-4 text-white" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-white">Historial Académico</h2>
          <p className="text-xs text-gray-400">Notas y materias cursadas por semestre</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs bg-white/10 text-gray-300 px-2 py-1 rounded-full">
            Próximamente
          </span>
        </div>
      </div>

      {/* Tabs de semestres placeholder */}
      <div className="border-b border-gray-100 px-6 pt-4 flex gap-2 overflow-x-auto">
        {['2024-1', '2024-2', '2025-1', '2025-2', '2026-1'].map((sem, i) => (
          <button
            key={sem}
            className={`px-4 py-2 text-xs font-medium rounded-t-lg border-b-2 whitespace-nowrap transition-colors ${
              i === 4
                ? 'border-[#C8102E] text-[#C8102E] bg-red-50'
                : 'border-transparent text-gray-400 hover:text-gray-600'
            }`}
          >
            {sem}
          </button>
        ))}
      </div>

      {/* Tabla placeholder */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['Código', 'Materia', 'Créditos', 'Grupo', 'Docente', 'Nota Final', 'Estado'].map(col => (
                <th key={col} className="px-5 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {placeholderRows.map((_, i) => (
              <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                <td className="px-5 py-3.5">
                  <div className="h-3.5 bg-gray-100 rounded w-16 animate-pulse" />
                </td>
                <td className="px-5 py-3.5">
                  <div className="h-3.5 bg-gray-100 rounded w-40 animate-pulse" />
                </td>
                <td className="px-5 py-3.5">
                  <div className="h-3.5 bg-gray-100 rounded w-8 animate-pulse" />
                </td>
                <td className="px-5 py-3.5">
                  <div className="h-3.5 bg-gray-100 rounded w-8 animate-pulse" />
                </td>
                <td className="px-5 py-3.5">
                  <div className="h-3.5 bg-gray-100 rounded w-32 animate-pulse" />
                </td>
                <td className="px-5 py-3.5">
                  <div className="h-3.5 bg-gray-100 rounded w-10 animate-pulse" />
                </td>
                <td className="px-5 py-3.5">
                  <div className="h-5 bg-gray-100 rounded-full w-16 animate-pulse" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer placeholder */}
      <div className="border-t border-gray-100 px-6 py-3 flex items-center justify-between">
        <p className="text-xs text-gray-400">Promedio del semestre: —</p>
        <p className="text-xs text-gray-400">Créditos cursados: —</p>
      </div>
    </div>
  );
}

// ─── Página principal StudentProfile ─────────────────────────────────────────
export default function StudentProfile() {
  const { id } = useParams();
  const [student, setStudent] = useState<StudentDetail | null>(null);
  const [indicadores, setIndicadores] = useState<IndicadoresData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        
        // Cargar datos del perfil y indicadores en paralelo
        const [studentRes, indicatorsRes] = await Promise.all([
          fetch(`${baseUrl}/api/academico/students/${id}/`),
          fetch(`${baseUrl}/api/academico/students/${id}/indicators/`)
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
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (id) fetchData();
  }, [id]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <div className="w-12 h-12 border-4 border-[#C8102E] border-t-transparent rounded-full animate-spin"></div>
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
          <h2 className="text-xl font-bold text-gray-900">{error || 'Estudiante no encontrado'}</h2>
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
      {/* Back button */}
      <div className="flex items-center justify-between">
        <Link to="/dashboard/students">
          <Button variant="secondary" size="sm">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Volver a Estudiantes
          </Button>
        </Link>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Hash className="w-3 h-3" />
          <span>ID: {id}</span>
        </div>
      </div>

      {/* Header del estudiante */}
      <div className="bg-gradient-to-r from-[#C8102E] to-[#a00d25] text-white rounded-xl p-6 shadow-md">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
              <User className="w-7 h-7 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold leading-tight">{student.nombre}</h1>
              <p className="text-sm text-red-200 mt-0.5">
                Código: <span className="font-mono font-semibold text-white">{student.codigo}</span>
              </p>
              <div className="flex items-center gap-3 mt-2">
                <span className="flex items-center gap-1 text-xs text-white bg-white/10 px-2 py-0.5 rounded">
                  <Layers className="w-3 h-3" />
                  {student.semestre}° Semestre
                </span>
                <span className="flex items-center gap-1 text-xs text-white bg-white/10 px-2 py-0.5 rounded">
                  <CheckCircle2 className="w-3 h-3" />
                  {student.estado_matricula}
                </span>
              </div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 text-right">
            <div className="text-xs text-red-200 uppercase tracking-wider font-bold">Promedio Acumulado</div>
            <div className="text-4xl font-black">{student.promedio?.toFixed(2) || '—'}</div>
            {student.alertas_activas > 0 && (
              <Badge variant="high" className="animate-pulse">
                {student.alertas_activas} ALERTAS ACTIVAS
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* ── Bloque 1: Ficha Académica ─────────────────────────────────────── */}
      <FichaAcademica student={student} />

      {/* ── Bloque 2: Indicadores ────────────────────────────────────────── */}
      <IndicadoresSection data={indicadores} loading={loading} />

      {/* ── Bloque 3: Historial Académico ────────────────────────────────── */}
      <HistorialAcademico />
    </div>
  );
}
