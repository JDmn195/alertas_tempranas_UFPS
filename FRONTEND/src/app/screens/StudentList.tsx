import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router';
import { Search, AlertTriangle, CheckCircle, Activity, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Student {
  codigo: string;
  nombre: string;
  semestre: number;
  promedio: number | null;
  nivel_riesgo: 'high' | 'medium' | 'low' | 'unknown';
  alertas_activas: number;
  estado_matricula: string;
}

interface ApiResponse {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  results: Student[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const API_BASE = 'http://localhost:8000/api/academico';
const PAGE_SIZE = 15;

const RISK_LABEL: Record<string, string> = {
  high: 'ALTO',
  medium: 'MEDIO',
  low: 'BAJO',
  unknown: 'SIN DATO',
};

const SEMESTRES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

// ─── Component ────────────────────────────────────────────────────────────────
export default function StudentList() {
  const [students, setStudents] = useState<Student[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [semesterFilter, setSemesterFilter] = useState('');
  const [riskFilter, setRiskFilter] = useState('');

  // Debounce ref for search
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Summary counts per risk level
  const countHigh   = students.filter(s => s.nivel_riesgo === 'high').length;
  const countMedium = students.filter(s => s.nivel_riesgo === 'medium').length;
  const countLow    = students.filter(s => s.nivel_riesgo === 'low').length;

  // ── Debounce search input ──────────────────────────────────────────────────
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setCurrentPage(1);
    }, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [searchTerm]);

  // ── Fetch students ─────────────────────────────────────────────────────────
  const fetchStudents = useCallback(async () => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams({
      page: String(currentPage),
      page_size: String(PAGE_SIZE),
    });
    if (debouncedSearch) params.append('search', debouncedSearch);
    if (semesterFilter) params.append('semester', semesterFilter);
    if (riskFilter)     params.append('risk', riskFilter);

    try {
      const res = await fetch(`${API_BASE}/students/?${params.toString()}`);
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data: ApiResponse = await res.json();
      setStudents(data.results);
      setTotal(data.total);
      setPages(data.pages);
    } catch (err) {
      setError('No se pudo conectar con el servidor. Verifica que el backend esté activo.');
      setStudents([]);
    } finally {
      setLoading(false);
    }
  }, [currentPage, debouncedSearch, semesterFilter, riskFilter]);

  useEffect(() => { fetchStudents(); }, [fetchStudents]);

  // Reset page when filters change
  const handleSemesterChange = (v: string) => { setSemesterFilter(v); setCurrentPage(1); };
  const handleRiskChange     = (v: string) => { setRiskFilter(v);     setCurrentPage(1); };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* Page header */}
      <div className="border-l-4 border-[#C8102E] pl-4">
        <h1 className="text-2xl font-bold text-gray-900">Directorio de Estudiantes</h1>
        <p className="text-sm text-gray-600 mt-1">
          Ver y filtrar registros de estudiantes registrados en el sistema
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-red-600" />
          </div>
          <div>
            <p className="text-xs text-red-600 font-medium uppercase tracking-wide">Riesgo Alto</p>
            <p className="text-2xl font-bold text-red-700">
              {loading ? '—' : countHigh}
            </p>
          </div>
        </div>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center">
            <Activity className="w-5 h-5 text-yellow-600" />
          </div>
          <div>
            <p className="text-xs text-yellow-600 font-medium uppercase tracking-wide">Riesgo Medio</p>
            <p className="text-2xl font-bold text-yellow-700">
              {loading ? '—' : countMedium}
            </p>
          </div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
            <CheckCircle className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <p className="text-xs text-green-600 font-medium uppercase tracking-wide">Riesgo Bajo</p>
            <p className="text-2xl font-bold text-green-700">
              {loading ? '—' : countLow}
            </p>
          </div>
        </div>
      </div>

      {/* Search and filters */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-center gap-3 flex-wrap">
          {/* Search bar */}
          <div className="flex-1 min-w-[220px] relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              id="student-search"
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar por nombre o código..."
              className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent text-sm"
            />
          </div>

          {/* Semester filter */}
          <select
            id="semester-filter"
            value={semesterFilter}
            onChange={(e) => handleSemesterChange(e.target.value)}
            className="px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent bg-white text-sm"
          >
            <option value="">Todos los Semestres</option>
            {SEMESTRES.map(s => (
              <option key={s} value={String(s)}>Semestre {s}</option>
            ))}
          </select>

          {/* Risk level filter */}
          <select
            id="risk-filter"
            value={riskFilter}
            onChange={(e) => handleRiskChange(e.target.value)}
            className="px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent bg-white text-sm"
          >
            <option value="">Todos los Niveles de Riesgo</option>
            <option value="high">Riesgo Alto   (Promedio &lt; 3.0)</option>
            <option value="medium">Riesgo Medio  (3.0 – 3.4)</option>
            <option value="low">Riesgo Bajo   (Promedio ≥ 3.5)</option>
          </select>

          {/* Refresh */}
          <button
            id="refresh-students"
            onClick={fetchStudents}
            className="p-2.5 rounded-lg border border-gray-300 hover:bg-gray-50 text-gray-500 hover:text-[#C8102E] transition-colors"
            title="Actualizar"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Student table */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">
            {loading
              ? 'Cargando...'
              : `${total} estudiante${total !== 1 ? 's' : ''} encontrado${total !== 1 ? 's' : ''}`}
          </h2>
          <span className="text-xs text-gray-400">
            Página {currentPage} de {pages}
          </span>
        </div>

        {/* Error state */}
        {error && (
          <div className="p-8 text-center">
            <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-3" />
            <p className="text-sm text-red-600 font-medium">{error}</p>
            <button
              onClick={fetchStudents}
              className="mt-3 text-sm text-[#C8102E] underline hover:no-underline"
            >
              Reintentar
            </button>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && students.length === 0 && (
          <div className="p-12 text-center">
            <Search className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500 font-medium">No se encontraron estudiantes</p>
            <p className="text-xs text-gray-400 mt-1">Intenta con otros filtros o términos de búsqueda</p>
          </div>
        )}

        {/* Table */}
        {!error && students.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[#C8102E] text-white">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider">Código</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider">Nombre</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider">Semestre</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider">Promedio</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider">Nivel de Riesgo</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider">Alertas Activas</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {students.map((student, index) => (
                  <tr
                    key={student.codigo}
                    className={`
                      ${index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                      ${student.nivel_riesgo === 'high' ? '!bg-red-50' : ''}
                      hover:bg-red-50 transition-colors duration-100
                    `}
                  >
                    <td className="px-5 py-3.5 text-sm font-mono font-medium text-gray-800">
                      {student.codigo}
                    </td>
                    <td className="px-5 py-3.5 text-sm text-gray-900 max-w-[240px] truncate">
                      {student.nombre}
                    </td>
                    <td className="px-5 py-3.5 text-sm text-gray-700">
                      {student.semestre}°
                    </td>
                    <td className="px-5 py-3.5 text-sm font-semibold text-gray-900">
                      {student.promedio !== null ? student.promedio.toFixed(2) : '—'}
                    </td>
                    <td className="px-5 py-3.5">
                      {student.nivel_riesgo === 'high'    && <Badge variant="high">ALTO</Badge>}
                      {student.nivel_riesgo === 'medium'  && <Badge variant="medium">MEDIO</Badge>}
                      {student.nivel_riesgo === 'low'     && <Badge variant="low">BAJO</Badge>}
                      {student.nivel_riesgo === 'unknown' && (
                        <span className="text-xs text-gray-400 italic">Sin dato</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      {student.alertas_activas > 0 ? (
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#C8102E] text-white text-xs font-bold">
                          {student.alertas_activas}
                        </span>
                      ) : (
                        <span className="text-gray-300 text-sm">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      <Link to={`/dashboard/students/${student.codigo}`}>
                        <Button variant="outline" size="sm">Ver Perfil</Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && !error && (
          <div className="divide-y divide-gray-100">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-5 py-4 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-20 flex-shrink-0" />
                <div className="h-4 bg-gray-200 rounded w-48" />
                <div className="h-4 bg-gray-200 rounded w-10 flex-shrink-0" />
                <div className="h-4 bg-gray-200 rounded w-12 flex-shrink-0" />
                <div className="h-4 bg-gray-200 rounded w-16 flex-shrink-0" />
                <div className="h-4 bg-gray-200 rounded w-10 flex-shrink-0" />
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {!error && pages > 1 && (
          <div className="border-t border-gray-100 px-6 py-3 flex items-center justify-between">
            <p className="text-xs text-gray-500">
              Mostrando {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, total)} de {total}
            </p>
            <div className="flex items-center gap-1">
              <button
                id="prev-page"
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-4 h-4 text-gray-600" />
              </button>
              {Array.from({ length: Math.min(pages, 7) }, (_, i) => {
                const p = i + 1;
                return (
                  <button
                    key={p}
                    onClick={() => setCurrentPage(p)}
                    className={`w-7 h-7 rounded text-xs font-medium transition-colors ${
                      p === currentPage
                        ? 'bg-[#C8102E] text-white'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    {p}
                  </button>
                );
              })}
              <button
                id="next-page"
                onClick={() => setCurrentPage(p => Math.min(pages, p + 1))}
                disabled={currentPage === pages}
                className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight className="w-4 h-4 text-gray-600" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
