import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Search, RefreshCw, ChevronLeft, ChevronRight,
  AlertTriangle, TrendingUp, TrendingDown, Minus,
  BookOpen, Users, BarChart2,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, PieChart, Pie, Legend,
} from 'recharts';

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
}

interface ApiResponse {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  results: CourseIndicator[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const API_BASE = 'http://localhost:8000/api/academico';
const PAGE_SIZE = 15;
const UMBRAL_CRITICO = 30;

function getRiskLevel(tasa: number): 'high' | 'medium' | 'low' {
  if (tasa >= UMBRAL_CRITICO) return 'high';
  if (tasa >= 15) return 'medium';
  return 'low';
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
  const [periodoAnio, setPeriodoAnio] = useState('2025');
  const [periodoSemestre, setPeriodoSemestre] = useState('1');

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const userJson = localStorage.getItem('user');
  const user = userJson ? JSON.parse(userJson) : null;
  const usuarioId = user?.id;

  const countCriticos = allCourses.filter(c => c.es_critico).length;
  const countMedio    = allCourses.filter(c => !c.es_critico && getRiskLevel(c.tasa_reprobacion) === 'medium').length;
  const countOk       = allCourses.filter(c => getRiskLevel(c.tasa_reprobacion) === 'low').length;

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
      usuario_id: String(usuarioId),
      periodo_anio: periodoAnio,
      periodo_semestre: periodoSemestre,
    });
    if (debouncedSearch) params.append('search', debouncedSearch);
    if (estadoFilter) params.append('estado', estadoFilter);
    try {
      const res = await fetch(`${API_BASE}/courses/indicators/?${params.toString()}`);
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data: ApiResponse = await res.json();
      setCourses(data.results);
      setTotal(data.total);
      setPages(data.pages);
    } catch {
      setError('No se pudo conectar con el servidor. Verifica que el backend esté activo.');
      setCourses([]);
    } finally {
      setLoading(false);
    }
  }, [currentPage, debouncedSearch, estadoFilter, periodoAnio, periodoSemestre, usuarioId]);

  const fetchAllForCharts = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        page: '1', page_size: '200',
        usuario_id: String(usuarioId),
        periodo_anio: periodoAnio,
        periodo_semestre: periodoSemestre,
      });
      const res = await fetch(`${API_BASE}/courses/indicators/?${params.toString()}`);
      if (!res.ok) return;
      const data: ApiResponse = await res.json();
      setAllCourses(data.results);
    } catch { /* silencioso */ }
  }, [periodoAnio, periodoSemestre, usuarioId]);

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
            <option value="2024">2024</option>
            <option value="2025">2025</option>
            <option value="2026">2026</option>
          </select>
          <select value={periodoSemestre} onChange={(e) => { setPeriodoSemestre(e.target.value); setCurrentPage(1); }}
            className="px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] bg-white text-sm">
            <option value="1">Semestre 1</option>
            <option value="2">Semestre 2</option>
          </select>
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
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {courses.map((course, index) => {
                  const risk = getRiskLevel(course.tasa_reprobacion);
                  return (
                    <tr key={course.curso_id} className={`${index % 2 === 0 ? 'bg-white' : 'bg-gray-50'} ${course.es_critico ? '!bg-red-50' : ''} hover:bg-red-50 transition-colors duration-100`}>
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
    </div>
  );
}
