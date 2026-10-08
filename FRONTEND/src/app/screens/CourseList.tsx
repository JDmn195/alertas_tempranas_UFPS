import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Search, RefreshCw, ChevronLeft, ChevronRight,
  AlertTriangle, TrendingUp, TrendingDown, Minus,
  BookOpen, Users, BarChart2, X, Pencil,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, PieChart, Pie, Legend,
} from 'recharts';
import { apiFetch } from '../../services/apiFetch';

// ─── Types ────────────────────────────────────────────────────────────────────
interface CourseIndicator {
  curso_id: number;
  codigo_materia: string;
  materia: string;
  grupo: string;
  docente: string;
  matriculados: number;
  reprobados: number;
  tasa_reprobacion: number;
  promedio_curso: number | null;
  zona_riesgo: number;
  no_presentados: number;
  tasa_no_presentados: number;
  tendencia_puntos: number | null;
  tendencia_descripcion: string;
  estado: string;
  es_critico: boolean;
  // HU-35: umbral de inasistencia efectivo y su origen
  umbral_inasistencia: number | null;
  umbral_inasistencia_curso: number | null;
  origen_umbral_inasistencia: 'curso' | 'general' | null;
}

interface ApiResponse {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  results: CourseIndicator[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/academico`;
const PAGE_SIZE = 15;
const UMBRAL_CRITICO = 30;

function getRiskLevel(tasa: number): 'high' | 'medium' | 'low' {
  if (tasa >= UMBRAL_CRITICO) return 'high';
  if (tasa >= 15) return 'medium';
  return 'low';
}

function esAdministrador(): boolean {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    return (user?.rol || '').split(',').includes('ADMINISTRADOR');
  } catch {
    return false;
  }
}

function TendenciaIcon({ puntos }: { puntos: number | null }) {
  if (puntos === null) return <Minus className="w-4 h-4 text-gray-400" />;
  if (puntos > 0) return <TrendingUp className="w-4 h-4 text-red-500" />;
  if (puntos < 0) return <TrendingDown className="w-4 h-4 text-green-500" />;
  return <Minus className="w-4 h-4 text-gray-400" />;
}

function CustomBarTooltip({ active, payload }: any) {
  if (active && payload && payload.length) {
    const d = payload[0].payload;
    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs">
        <p className="font-bold text-gray-800 mb-1">{d.materia}</p>
        <p className="text-gray-500">Grupo: {d.grupo}</p>
        <p className={`font-semibold mt-1 ${d.tasa >= UMBRAL_CRITICO ? 'text-red-600' : d.tasa >= 15 ? 'text-yellow-600' : 'text-green-600'}`}>
          Tasa reprobación: {d.tasa.toFixed(1)}%
        </p>
      </div>
    );
  }
  return null;
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function CourseList() {
  const [courses, setCourses] = useState<CourseIndicator[]>([]);
  const [allCourses, setAllCourses] = useState<CourseIndicator[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [estadoFilter, setEstadoFilter] = useState('');
  const [periodoAnio, setPeriodoAnio] = useState('todos');
  const [periodoSemestre, setPeriodoSemestre] = useState('1');
  const [advertencia, setAdvertencia] = useState<string | null>(null);

  // HU-35: edición del umbral de inasistencia por curso (solo ADMINISTRADOR)
  const puedeEditarUmbral = esAdministrador();
  const [umbralEditando, setUmbralEditando] = useState<CourseIndicator | null>(null);
  const [umbralValor, setUmbralValor] = useState('');
  const [umbralGuardando, setUmbralGuardando] = useState(false);
  const [umbralError, setUmbralError] = useState<string | null>(null);

  // Detalle de curso modal states
  const [selectedCourseDetail, setSelectedCourseDetail] = useState<number | null>(null);
  const [courseDetailData, setCourseDetailData] = useState<{
    curso_id: number;
    codigo_materia: string;
    materia: string;
    grupo: string;
    docente: string;
    estudiantes: Array<{
      codigo: string;
      nombre: string;
      periodo: string;
      definitiva: number | null;
    }>;
  } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const fetchCourseDetail = useCallback(async (cursoId: number) => {
    setDetailLoading(true);
    setDetailError(null);
    setCourseDetailData(null);
    try {
      const res = await apiFetch(`${API_BASE}/courses/${cursoId}/detail/`);
      if (!res.ok) throw new Error('No se pudo cargar el detalle del curso');
      const data = await res.json();
      setCourseDetailData(data);
    } catch (err: any) {
      setDetailError(err.message || 'Error al obtener el detalle');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedCourseDetail !== null) {
      fetchCourseDetail(selectedCourseDetail);
    }
  }, [selectedCourseDetail, fetchCourseDetail]);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);


  const countCriticos = allCourses.filter(c => c.es_critico).length;
  const countMedio = allCourses.filter(c => !c.es_critico && getRiskLevel(c.tasa_reprobacion) === 'medium').length;
  const countOk = allCourses.filter(c => getRiskLevel(c.tasa_reprobacion) === 'low').length;

  const barData = [...allCourses]
    .filter(c => c.matriculados > 0)
    .sort((a, b) => b.tasa_reprobacion - a.tasa_reprobacion)
    .slice(0, 10)
    .map(c => ({
      materia: c.materia.length > 18 ? c.materia.substring(0, 18) + '…' : c.materia,
      grupo: c.grupo,
      tasa: c.tasa_reprobacion,
    }));

  const donaData = [
    { name: 'Crítico', value: countCriticos, color: '#EF4444' },
    { name: 'En observación', value: countMedio, color: '#F59E0B' },
    { name: 'Estable', value: countOk, color: '#22C55E' },
  ].filter(d => d.value > 0);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setCurrentPage(1);
    }, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [searchTerm]);

  const fetchCourses = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      page: String(currentPage),
      page_size: String(PAGE_SIZE),
      periodo_anio: periodoAnio,
      periodo_semestre: periodoSemestre,
    });
    if (debouncedSearch) params.append('search', debouncedSearch);
    if (estadoFilter) params.append('estado', estadoFilter);
    try {
      const res = await apiFetch(`${API_BASE}/courses/indicators/?${params.toString()}`);
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data: ApiResponse = await res.json();
      setCourses(data.results);
      setTotal(data.total);
      setPages(data.pages);
      setAdvertencia((data as any).advertencia || null);
    } catch {
      setError('No se pudo conectar con el servidor. Verifica que el backend esté activo.');
      setCourses([]);
    } finally {
      setLoading(false);
    }
  }, [currentPage, debouncedSearch, estadoFilter, periodoAnio, periodoSemestre]);

  const fetchAllForCharts = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        page: '1', page_size: '500',
        periodo_anio: periodoAnio,
        periodo_semestre: periodoSemestre,
      });
      if (periodoAnio === 'todos') {
        params.set('periodo_anio', 'todos');
      }
      const res = await apiFetch(`${API_BASE}/courses/indicators/?${params.toString()}`);
      if (!res.ok) return;
      const data: ApiResponse = await res.json();
      setAllCourses(data.results);
    } catch { /* silencioso */ }
  }, [periodoAnio, periodoSemestre]);

  const abrirEdicionUmbral = (course: CourseIndicator) => {
    setUmbralEditando(course);
    setUmbralValor(course.umbral_inasistencia_curso !== null ? String(course.umbral_inasistencia_curso) : '');
    setUmbralError(null);
  };

  const cerrarEdicionUmbral = () => {
    setUmbralEditando(null);
    setUmbralError(null);
  };

  // umbral null = volver al umbral general
  const guardarUmbral = async (umbral: number | null) => {
    if (!umbralEditando) return;
    setUmbralGuardando(true);
    setUmbralError(null);
    try {
      const res = await apiFetch(`${API_BASE}/cursos/${umbralEditando.curso_id}/umbral-inasistencia/`, {
        method: 'PATCH',
        body: JSON.stringify({ umbral }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `Error ${res.status}`);
      cerrarEdicionUmbral();
      fetchCourses();
    } catch (e: any) {
      setUmbralError(e.message || 'No se pudo actualizar el umbral de inasistencia.');
    } finally {
      setUmbralGuardando(false);
    }
  };

  useEffect(() => { fetchCourses(); }, [fetchCourses]);
  useEffect(() => { fetchAllForCharts(); }, [fetchAllForCharts]);

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="border-l-4 border-[#C8102E] pl-4">
        <h1 className="text-2xl font-bold text-gray-900">Indicadores por Curso</h1>
        <p className="text-sm text-gray-600 mt-1">
          Matrícula, tasa de reprobación y tendencia para identificar cursos críticos
        </p>
      </div>

      {/* Banner de advertencia de periodo */}
      {advertencia && (
        <div className="px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2 text-sm text-amber-700">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 text-amber-500" />
          <span>{advertencia}</span>
        </div>
      )}

      {/* Tarjetas resumen */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-red-600" />
          </div>
          <div>
            <p className="text-xs text-red-600 font-medium uppercase tracking-wide">Cursos Críticos</p>
            <p className="text-2xl font-bold text-red-700">{loading ? '—' : countCriticos}</p>
            <p className="text-xs text-red-400">Reprobación ≥ {UMBRAL_CRITICO}%</p>
          </div>
        </div>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center">
            <BarChart2 className="w-5 h-5 text-yellow-600" />
          </div>
          <div>
            <p className="text-xs text-yellow-600 font-medium uppercase tracking-wide">Riesgo Medio</p>
            <p className="text-2xl font-bold text-yellow-700">{loading ? '—' : countMedio}</p>
            <p className="text-xs text-yellow-400">Reprobación 15–29%</p>
          </div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <p className="text-xs text-green-600 font-medium uppercase tracking-wide">Sin Riesgo</p>
            <p className="text-2xl font-bold text-green-700">{loading ? '—' : countOk}</p>
            <p className="text-xs text-green-400">Reprobación &lt; 15%</p>
          </div>
        </div>
      </div>

      {/* Gráficas */}
      {allCourses.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2 bg-white rounded-lg border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-800 mb-4">
              Top 10 — Cursos con mayor tasa de reprobación
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={barData} layout="vertical" margin={{ left: 0, right: 20, top: 0, bottom: 0 }}>
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} tickFormatter={v => `${v}%`} />
                <YAxis type="category" dataKey="materia" tick={{ fontSize: 10 }} width={130} />
                <Tooltip content={<CustomBarTooltip />} />
                <Bar dataKey="tasa" radius={[0, 4, 4, 0]}>
                  {barData.map((entry, index) => (
                    <Cell key={index} fill={entry.tasa >= UMBRAL_CRITICO ? '#EF4444' : entry.tasa >= 15 ? '#F59E0B' : '#22C55E'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-800 mb-4">Distribución de estados</h3>
            {donaData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={donaData} cx="50%" cy="45%" innerRadius={55} outerRadius={80} paddingAngle={3} dataKey="value">
                    {donaData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value, name) => [`${value} cursos`, name]} />
                  <Legend iconType="circle" iconSize={8} formatter={(value) => <span style={{ fontSize: 11 }}>{value}</span>} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-xs text-gray-400">Sin datos para este periodo</div>
            )}
          </div>
        </div>
      )}

      {/* Filtros */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex-1 min-w-[220px] relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text" value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar por materia o código..."
              className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent text-sm"
            />
          </div>
          <select value={periodoAnio} onChange={(e) => { setPeriodoAnio(e.target.value); setCurrentPage(1); }}
            className="px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] bg-white text-sm">
            <option value="todos">Todos los periodos</option>
            <option value="2024">2024</option>
            <option value="2025">2025</option>
            <option value="2026">2026</option>
          </select>
          {periodoAnio !== 'todos' && (
            <select value={periodoSemestre} onChange={(e) => { setPeriodoSemestre(e.target.value); setCurrentPage(1); }}
              className="px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] bg-white text-sm">
              <option value="1">Semestre 1</option>
              <option value="2">Semestre 2</option>
            </select>
          )}
          <select value={estadoFilter} onChange={(e) => { setEstadoFilter(e.target.value); setCurrentPage(1); }}
            className="px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] bg-white text-sm">
            <option value="">Todos los cursos</option>
            <option value="CRÍTICO">Solo críticos</option>
            <option value="EN OBSERVACIÓN">Riesgo medio</option>
            <option value="ESTABLE">Sin riesgo crítico</option>
          </select>
          <button onClick={() => { fetchCourses(); fetchAllForCharts(); }}
            className="p-2.5 rounded-lg border border-gray-300 hover:bg-gray-50 text-gray-500 hover:text-[#C8102E] transition-colors" title="Actualizar">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabla */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">
            {loading ? 'Cargando...' : `${total} curso${total !== 1 ? 's' : ''} encontrado${total !== 1 ? 's' : ''}`}
          </h2>
          <span className="text-xs text-gray-400">Página {currentPage} de {pages}</span>
        </div>

        {error && (
          <div className="p-8 text-center">
            <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-3" />
            <p className="text-sm text-red-600 font-medium">{error}</p>
            <button onClick={fetchCourses} className="mt-3 text-sm text-[#C8102E] underline hover:no-underline">Reintentar</button>
          </div>
        )}

        {!loading && !error && courses.length === 0 && (
          <div className="p-12 text-center">
            <Search className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500 font-medium">No se encontraron cursos</p>
            <p className="text-xs text-gray-400 mt-1">Intenta con otros filtros o periodo</p>
          </div>
        )}

        {!error && courses.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[#C8102E] text-white">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider">Código</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider">Materia</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider">Grupo</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider">Docente</th>
                  <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wider">
                    <span className="flex items-center justify-center gap-1"><Users className="w-3.5 h-3.5" />Matrícula</span>
                  </th>
                  <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wider">Reprobados</th>
                  <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wider">Tasa Rep.</th>
                  <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wider">Promedio</th>
                  <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wider">Zona Riesgo</th>
                  <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wider">No Present.</th>
                  <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wider">Tendencia</th>
                  <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wider">Estado</th>
                  <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wider">Umbral Inasist.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {courses.map((course, index) => {
                  const risk = getRiskLevel(course.tasa_reprobacion);
                  return (
                    <tr
                      key={course.curso_id}
                      onClick={() => setSelectedCourseDetail(course.curso_id)}
                      className={`${index % 2 === 0 ? 'bg-white' : 'bg-gray-50'} ${course.es_critico ? '!bg-red-50' : ''} hover:bg-red-50 transition-colors duration-100 cursor-pointer`}
                    >
                      <td className="px-5 py-3.5 text-sm font-mono font-medium text-gray-700">{course.codigo_materia}</td>
                      <td className="px-5 py-3.5 text-sm text-gray-900 max-w-[200px] truncate font-medium">{course.materia}</td>
                      <td className="px-5 py-3.5 text-sm text-gray-600">G-{course.grupo}</td>
                      <td className="px-5 py-3.5 text-sm text-gray-700 max-w-[160px] truncate">{course.docente}</td>
                      <td className="px-5 py-3.5 text-sm text-center font-semibold text-gray-900">{course.matriculados}</td>
                      <td className="px-5 py-3.5 text-sm text-center">
                        <span className={`font-semibold ${course.reprobados > 0 ? 'text-red-600' : 'text-gray-400'}`}>{course.reprobados}</span>
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-16 bg-gray-200 rounded-full h-1.5">
                            <div className={`h-1.5 rounded-full ${risk === 'high' ? 'bg-red-500' : risk === 'medium' ? 'bg-yellow-400' : 'bg-green-500'}`}
                              style={{ width: `${Math.min(course.tasa_reprobacion, 100)}%` }} />
                          </div>
                          <span className={`text-sm font-bold ${risk === 'high' ? 'text-red-600' : risk === 'medium' ? 'text-yellow-600' : 'text-green-600'}`}>
                            {course.tasa_reprobacion.toFixed(1)}%
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        <span className={`text-sm font-bold ${course.promedio_curso === null ? 'text-gray-400' : course.promedio_curso < 3.0 ? 'text-red-600' : course.promedio_curso < 3.5 ? 'text-yellow-600' : 'text-green-600'}`}>
                          {course.promedio_curso !== null ? course.promedio_curso.toFixed(2) : '—'}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        <span className={`text-sm font-semibold ${course.zona_riesgo > 0 ? 'text-yellow-600' : 'text-gray-400'}`}>
                          {course.zona_riesgo > 0 ? course.zona_riesgo : '—'}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        <div className="flex flex-col items-center">
                          <span className={`text-sm font-semibold ${course.no_presentados > 0 ? 'text-red-500' : 'text-gray-400'}`}>
                            {course.no_presentados > 0 ? course.no_presentados : '—'}
                          </span>
                          {course.no_presentados > 0 && <span className="text-xs text-red-400">{course.tasa_no_presentados.toFixed(1)}%</span>}
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <TendenciaIcon puntos={course.tendencia_puntos} />
                          <span className={`text-xs font-medium ${course.tendencia_puntos === null ? 'text-gray-400 italic' : course.tendencia_puntos > 0 ? 'text-red-500' : course.tendencia_puntos < 0 ? 'text-green-600' : 'text-gray-500'}`}>
                            {course.tendencia_puntos === null ? 'Sin datos' : course.tendencia_puntos > 0 ? `+${course.tendencia_puntos.toFixed(1)}%` : `${course.tendencia_puntos.toFixed(1)}%`}
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        {course.es_critico ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-red-100 text-red-700 border border-red-200">
                            <AlertTriangle className="w-3 h-3" /> CRÍTICO
                          </span>
                        ) : risk === 'medium' ? (
                          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-yellow-100 text-yellow-700 border border-yellow-200">MEDIO</span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-green-100 text-green-700 border border-green-200">OK</span>
                        )}
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        <div className="flex items-center justify-center gap-2">
                          {course.umbral_inasistencia === null ? (
                            <span className="text-xs text-gray-400 italic">Sin umbral</span>
                          ) : (
                            <div className="flex flex-col items-center">
                              <span className="text-sm font-semibold text-gray-900">{course.umbral_inasistencia}%</span>
                              <span className={`text-[10px] font-semibold uppercase ${course.origen_umbral_inasistencia === 'curso' ? 'text-[#C8102E]' : 'text-gray-400'}`}>
                                {course.origen_umbral_inasistencia === 'curso' ? 'Propio' : 'General'}
                              </span>
                            </div>
                          )}
                          {puedeEditarUmbral && (
                            <button
                              type="button"
                              title="Editar umbral de inasistencia del curso"
                              onClick={(e) => { e.stopPropagation(); abrirEdicionUmbral(course); }}
                              className="p-1 rounded hover:bg-gray-200 text-gray-500 hover:text-gray-800 transition-colors"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {loading && !error && (
          <div className="divide-y divide-gray-100">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-5 py-4 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-16 flex-shrink-0" />
                <div className="h-4 bg-gray-200 rounded w-40" />
                <div className="h-4 bg-gray-200 rounded w-10 flex-shrink-0" />
                <div className="h-4 bg-gray-200 rounded w-32" />
                <div className="h-4 bg-gray-200 rounded w-10 flex-shrink-0" />
                <div className="h-4 bg-gray-200 rounded w-10 flex-shrink-0" />
                <div className="h-4 bg-gray-200 rounded w-20 flex-shrink-0" />
                <div className="h-4 bg-gray-200 rounded w-16 flex-shrink-0" />
              </div>
            ))}
          </div>
        )}

        {!error && pages > 1 && (
          <div className="border-t border-gray-100 px-6 py-3 flex items-center justify-between">
            <p className="text-xs text-gray-500">
              Mostrando {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, total)} de {total}
            </p>
            <div className="flex items-center gap-1">
              <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}
                className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
                <ChevronLeft className="w-4 h-4 text-gray-600" />
              </button>
              {Array.from({ length: Math.min(pages, 7) }, (_, i) => {
                const p = i + 1;
                return (
                  <button key={p} onClick={() => setCurrentPage(p)}
                    className={`w-7 h-7 rounded text-xs font-medium transition-colors ${p === currentPage ? 'bg-[#C8102E] text-white' : 'text-gray-600 hover:bg-gray-100'}`}>
                    {p}
                  </button>
                );
              })}
              <button onClick={() => setCurrentPage(p => Math.min(pages, p + 1))} disabled={currentPage === pages}
                className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
                <ChevronRight className="w-4 h-4 text-gray-600" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── HU-35: Modal de umbral de inasistencia del curso ─────────────── */}
      {umbralEditando && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}>
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-md">
            <div className="bg-[#C8102E] text-white px-6 py-4 flex items-center justify-between rounded-t-lg">
              <div>
                <h2 className="text-lg font-bold">Umbral de inasistencia</h2>
                <p className="text-xs opacity-90">
                  {umbralEditando.codigo_materia} G-{umbralEditando.grupo} · {umbralEditando.materia}
                </p>
              </div>
              <button onClick={cerrarEdicionUmbral} className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg p-1.5">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form
              className="p-6 space-y-4"
              onSubmit={(e) => { e.preventDefault(); guardarUmbral(umbralValor.trim() === '' ? null : Number(umbralValor)); }}
            >
              <p className="text-sm text-gray-600">
                {umbralEditando.origen_umbral_inasistencia === 'curso'
                  ? 'Este curso tiene un umbral propio.'
                  : umbralEditando.umbral_inasistencia !== null
                    ? `Este curso usa el umbral general (${umbralEditando.umbral_inasistencia}%).`
                    : 'No hay un umbral general activo.'}
              </p>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Umbral propio del curso (%)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={umbralValor}
                  autoFocus
                  onChange={(e) => setUmbralValor(e.target.value)}
                  placeholder="Entre 0 y 100"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                />
                <p className="text-xs text-gray-500 mt-1">Déjelo vacío o use "Volver al general" para usar el umbral general.</p>
              </div>
              {umbralError && (
                <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2" role="alert">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                  <span>{umbralError}</span>
                </div>
              )}
              <div className="flex items-center justify-between gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => guardarUmbral(null)}
                  disabled={umbralGuardando || umbralEditando.origen_umbral_inasistencia !== 'curso'}
                  className="text-sm text-gray-600 hover:text-gray-900 underline disabled:opacity-40 disabled:no-underline"
                >
                  Volver al general
                </button>
                <div className="flex gap-2">
                  <button type="button" onClick={cerrarEdicionUmbral}
                    className="px-4 py-2 text-sm rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50">
                    Cancelar
                  </button>
                  <button type="submit" disabled={umbralGuardando}
                    className="px-4 py-2 text-sm rounded-md bg-[#C8102E] text-white hover:bg-[#a00d25] disabled:opacity-50">
                    {umbralGuardando ? 'Guardando…' : 'Guardar'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal de Detalle de Curso (Alumnos inscritos) ────────────────── */}
      {selectedCourseDetail !== null && (
        <>
          <div
            className="fixed inset-0 z-40 transition-opacity"
            style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
            onClick={() => { setSelectedCourseDetail(null); setCourseDetailData(null); }}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-lg shadow-2xl border border-gray-200 w-full max-w-4xl max-h-[85vh] overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200">
              {/* Header */}
              <div className="bg-[#C8102E] text-white px-6 py-4 flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold">Detalle del Curso</h2>
                  <p className="text-xs opacity-90">Consulta de estudiantes matriculados</p>
                </div>
                <button
                  onClick={() => { setSelectedCourseDetail(null); setCourseDetailData(null); }}
                  className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg p-1.5 transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              {/* Content */}
              <div className="p-6 overflow-y-auto flex-1 space-y-4">
                {detailLoading ? (
                  <div className="py-12 text-center text-gray-500">Cargando información del curso...</div>
                ) : detailError ? (
                  <div className="p-4 bg-red-50 text-red-700 rounded-lg border border-red-200 flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 flex-shrink-0" />
                    {detailError}
                  </div>
                ) : courseDetailData ? (
                  <>
                    {/* Course Metadata Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 bg-gray-50 p-4 rounded-lg border border-gray-200">
                      <div>
                        <span className="text-[10px] text-gray-500 uppercase font-bold block">Materia</span>
                        <span className="text-sm font-semibold text-gray-900">{courseDetailData.materia}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-gray-500 uppercase font-bold block">Código / Grupo</span>
                        <span className="text-sm font-semibold text-gray-900 font-mono">{courseDetailData.codigo_materia} / G-{courseDetailData.grupo}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-gray-500 uppercase font-bold block">Profesor</span>
                        <span className="text-sm font-semibold text-gray-900">{courseDetailData.docente}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-gray-500 uppercase font-bold block">Total Estudiantes</span>
                        <span className="text-sm font-semibold text-gray-900">{courseDetailData.estudiantes.length} inscritos</span>
                      </div>
                    </div>

                    {/* Table of Enrolled Students */}
                    <div className="flex flex-col flex-1">
                      <h3 className="text-sm font-bold text-gray-700 mb-2">Listado de Estudiantes</h3>
                      <div className="overflow-x-auto border border-gray-200 rounded-lg max-h-[350px] overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-[#C8102E] text-white sticky top-0 z-10">
                            <tr>
                              <th className="px-4 py-3 text-left font-medium uppercase tracking-wider">Estudiante</th>
                              <th className="px-4 py-3 text-left font-medium uppercase tracking-wider">Código</th>
                              <th className="px-4 py-3 text-center font-medium uppercase tracking-wider">Periodo</th>
                              <th className="px-4 py-3 text-center font-medium uppercase tracking-wider">Nota Definitiva</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-200">
                            {courseDetailData.estudiantes.length === 0 ? (
                              <tr>
                                <td colSpan={4} className="px-4 py-6 text-center text-gray-500">
                                  No hay registros de notas/estudiantes asignados a este curso.
                                </td>
                              </tr>
                            ) : (
                              courseDetailData.estudiantes.map((est, idx) => (
                                <tr key={`${est.codigo}-${idx}`} className={idx % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5] hover:bg-red-50 transition-colors'}>
                                  <td className="px-4 py-2.5 font-medium text-gray-900">{est.nombre}</td>
                                  <td className="px-4 py-2.5 text-gray-600 font-mono">{est.codigo}</td>
                                  <td className="px-4 py-2.5 text-center text-gray-600 font-semibold">{est.periodo}</td>
                                  <td className="px-4 py-2.5 text-center">
                                    <span className={`font-mono font-bold ${est.definitiva === null ? 'text-gray-400' : est.definitiva < 3.0 ? 'text-red-600' : 'text-green-600'}`}>
                                      {est.definitiva !== null ? est.definitiva.toFixed(2) : '—'}
                                    </span>
                                  </td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
