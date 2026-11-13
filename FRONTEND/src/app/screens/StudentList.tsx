import { useState, useEffect, useCallback, useRef } from 'react';
import { Link, useNavigate } from 'react-router';
import { Search, AlertTriangle, CheckCircle, Activity, RefreshCw, ChevronLeft, ChevronRight, Bell, UserMinus } from 'lucide-react';
import { EncabezadoPagina } from '../components/Panel';
import { MedidorRiesgo, NivelRiesgoChip } from '../components/Riesgo';
import { Button } from '../components/ui/Button';
import { apiFetch } from '../../services/apiFetch';

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
const API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/academico`;
const PAGE_SIZE = 15;

const RISK_LABEL: Record<string, string> = {
  high: 'ALTO',
  medium: 'MEDIO',
  low: 'BAJO',
  unknown: 'SIN DATO',
};

const SEMESTRES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

// Chip de riesgo local: punto de color + texto, mismo lenguaje en toda la lista
const CHIP_RIESGO: Record<'high' | 'medium' | 'low', { texto: string; clase: string; punto: string }> = {
  high:   { texto: 'ALTO',  clase: 'bg-primary-tint text-[#9B0B22] ring-primary-tint', punto: 'bg-primary' },
  medium: { texto: 'MEDIO', clase: 'bg-amber-50 text-amber-800 ring-amber-200',   punto: 'bg-amber-500' },
  low:    { texto: 'BAJO',  clase: 'bg-green-50 text-green-800 ring-green-200', punto: 'bg-green-500' },
};

function ChipRiesgo({ nivel }: { nivel: 'high' | 'medium' | 'low' }) {
  const c = CHIP_RIESGO[nivel];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${c.clase}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.punto}`} aria-hidden="true" />
      {c.texto}
    </span>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function StudentList() {
  const navigate = useNavigate();
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

  // Summary counts per risk level and other indicators
  const countHigh     = students.filter(s => s.nivel_riesgo === 'high').length;
  const countMedium   = students.filter(s => s.nivel_riesgo === 'medium').length;
  const countLow      = students.filter(s => s.nivel_riesgo === 'low').length;
  const countAlerts   = students.reduce((sum, s) => sum + (s.alertas_activas || 0), 0);
  
  // Lógica corregida: Considerar inactivos solo estados terminales (Retirado, Graduado, Cancelado)
  const countInactive = students.filter(s => {
    if (!s.estado_matricula) return false;
    const est = s.estado_matricula.toLowerCase();
    return est.includes('retirado') || est.includes('graduado') || est.includes('cancelado');
  }).length;

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
      const res = await apiFetch(`${API_BASE}/students/?${params.toString()}`);
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

  const hayFiltros = Boolean(searchTerm || semesterFilter || riskFilter);
  const limpiarFiltros = () => { setSearchTerm(''); setSemesterFilter(''); setRiskFilter(''); setCurrentPage(1); };
  const alternarRiesgo = (nivel: string) => handleRiskChange(riskFilter === nivel ? '' : nivel);

  const campo = 'h-10 px-3.5 border border-line-strong rounded-[10px] bg-white text-sm text-ink';

  // Tarjetas de riesgo: también filtran la lista al hacer clic
  const tarjetasRiesgo = [
    { nivel: 'high',   etiqueta: 'Riesgo Alto',  valor: countHigh,   icono: AlertTriangle, tono: 'border-red-200 bg-red-50 text-red-700 hover:border-red-300',          circulo: 'bg-red-100 text-red-600' },
    { nivel: 'medium', etiqueta: 'Riesgo Medio', valor: countMedium, icono: Activity,      tono: 'border-amber-200 bg-amber-50 text-amber-800 hover:border-amber-300',  circulo: 'bg-amber-100 text-amber-600' },
    { nivel: 'low',    etiqueta: 'Riesgo Bajo',  valor: countLow,    icono: CheckCircle,   tono: 'border-green-200 bg-green-50 text-green-800 hover:border-green-300', circulo: 'bg-green-100 text-green-600' },
  ] as const;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-5">

      <EncabezadoPagina
        titulo="Directorio de Estudiantes"
        detalle="Busca un estudiante o filtra por nivel de riesgo para ver quién necesita seguimiento."
      >
        <p className="text-sm text-ink-muted">
          <span className="font-semibold text-ink tabular-nums">{loading ? '—' : countAlerts}</span> alertas activas
          <span className="mx-2 text-line-strong" aria-hidden="true">|</span>
          <span className="font-semibold text-ink tabular-nums">{loading ? '—' : countInactive}</span> inactivos
        </p>
      </EncabezadoPagina>

      {/* Filtros: el nivel de riesgo es el filtro principal y muestra cuántos hay en cada uno */}
      <div className="bg-white border border-line rounded-[14px]">
        <div className="flex flex-wrap items-stretch gap-px bg-line border-b border-line rounded-t-[14px] overflow-hidden" role="group" aria-label="Filtrar por nivel de riesgo">
          <button
            type="button"
            onClick={() => handleRiskChange('')}
            aria-pressed={riskFilter === ''}
            className={`flex-1 min-w-[8rem] text-left px-4 py-3 ${riskFilter === '' ? 'bg-primary-tint' : 'bg-white hover:bg-paper'}`}
          >
            <span className="block text-sm font-medium text-ink-muted">Todos</span>
            <span className="block mt-1 text-xl font-semibold text-ink leading-none">{loading ? '—' : students.length}</span>
          </button>
          {tarjetasRiesgo.map(({ nivel, etiqueta, valor }) => (
            <button
              key={nivel}
              type="button"
              onClick={() => alternarRiesgo(nivel)}
              aria-pressed={riskFilter === nivel}
              title={riskFilter === nivel ? 'Quitar filtro' : `Ver solo ${etiqueta.toLowerCase()}`}
              className={`flex-1 min-w-[8rem] text-left px-4 py-3 ${riskFilter === nivel ? 'bg-primary-tint' : 'bg-white hover:bg-paper'}`}
            >
              <span className="flex items-center justify-between gap-2 text-sm font-medium text-ink-muted">
                {etiqueta}
                <MedidorRiesgo nivel={nivel} />
              </span>
              <span className="block mt-1 text-xl font-semibold text-ink leading-none">{loading ? '—' : valor}</span>
            </button>
          ))}
        </div>

        <div className="p-3 sm:p-4 flex items-center gap-3 flex-wrap">
          {/* Search bar */}
          <div className="flex-1 min-w-[220px] relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint" aria-hidden="true" />
            <input
              id="student-search"
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar por nombre o código..."
              aria-label="Buscar por nombre o código"
              className={`${campo} w-full pl-10 pr-4`}
            />
          </div>

          {/* Semester filter */}
          <select
            id="semester-filter"
            value={semesterFilter}
            onChange={(e) => handleSemesterChange(e.target.value)}
            aria-label="Filtrar por semestre"
            className={`${campo} flex-1 sm:flex-none min-w-[170px]`}
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
            aria-label="Filtrar por nivel de riesgo"
            className={`${campo} flex-1 sm:flex-none min-w-[220px] lg:hidden`}
          >
            <option value="">Todos los Niveles de Riesgo</option>
            <option value="high">Riesgo Alto   (Promedio &lt; 3.0)</option>
            <option value="medium">Riesgo Medio  (3.0 – 3.4)</option>
            <option value="low">Riesgo Bajo   (Promedio ≥ 3.5)</option>
          </select>

          {hayFiltros && (
            <button
              type="button"
              onClick={limpiarFiltros}
              className="h-10 px-3 text-sm font-medium text-primary rounded-[10px] hover:bg-primary-tint"
            >
              Limpiar filtros
            </button>
          )}

          {/* Refresh */}
          <button
            id="refresh-students"
            onClick={fetchStudents}
            className="h-10 w-10 flex items-center justify-center rounded-[10px] border border-line-strong text-ink-muted hover:text-ink hover:border-ink-faint"
            title="Actualizar"
            aria-label="Actualizar lista"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Student table */}
      <div className="bg-white rounded-[14px] border border-gray-200 overflow-hidden">
        <div className="border-b border-gray-200 px-5 sm:px-6 py-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">
            {loading
              ? 'Cargando...'
              : `${total} estudiante${total !== 1 ? 's' : ''} encontrado${total !== 1 ? 's' : ''}`}
          </h2>
          <span className="text-xs text-gray-500 tabular-nums">
            Página {currentPage} de {pages}
          </span>
        </div>

        {/* Error state */}
        {error && (
          <div className="p-8 text-center" role="alert">
            <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-3" />
            <p className="text-sm text-red-600 font-medium">{error}</p>
            <button
              onClick={fetchStudents}
              className="mt-3 text-sm text-primary underline hover:no-underline"
            >
              Reintentar
            </button>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && students.length === 0 && (
          <div className="p-12 text-center">
            <div className="w-14 h-14 rounded-full bg-wash flex items-center justify-center mx-auto mb-4">
              <Search className="w-6 h-6 text-gray-400" />
            </div>
            <p className="text-sm text-gray-700 font-semibold">No se encontraron estudiantes</p>
            <p className="text-sm text-gray-500 mt-1">Intenta con otros filtros o términos de búsqueda</p>
            {hayFiltros && (
              <button type="button" onClick={limpiarFiltros} className="mt-4 text-sm font-medium text-primary hover:underline">
                Quitar todos los filtros
              </button>
            )}
          </div>
        )}

        {/* Table */}
        {!error && students.length > 0 && (
          <div className="overflow-x-auto animate-in fade-in duration-200">
            <table className="w-full min-w-[720px]">
              <thead className="bg-paper text-ink-soft border-b border-line">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-semibold">Código</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold">Nombre</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold">Semestre</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold">Promedio</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold">Nivel de Riesgo</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold">Alertas Activas</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {students.map((student) => (
                  <tr
                    key={student.codigo}
                    onClick={() => navigate(`/dashboard/students/${student.codigo}`)}
                    className="cursor-pointer"
                  >
                    <td className="px-5 py-3.5 text-sm tabular-nums font-medium text-gray-700 tabular-nums">
                      {student.codigo}
                    </td>
                    <td className="px-5 py-3.5 text-sm font-medium text-gray-900 max-w-[240px] truncate">
                      {student.nombre}
                    </td>
                    <td className="px-5 py-3.5 text-sm text-gray-700 tabular-nums">
                      {student.semestre}°
                    </td>
                    <td className="px-5 py-3.5 text-sm font-semibold text-gray-900 tabular-nums">
                      {student.promedio !== null ? student.promedio.toFixed(2) : '—'}
                    </td>
                    <td className="px-5 py-3.5">
                      {student.nivel_riesgo !== 'unknown' && <NivelRiesgoChip nivel={student.nivel_riesgo} texto={RISK_LABEL[student.nivel_riesgo]} />}
                      {student.nivel_riesgo === 'unknown' && (
                        <span className="text-sm text-ink-muted">Sin dato</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      {student.alertas_activas > 0 ? (
                        <span className="inline-flex items-center justify-center min-w-6 h-6 px-1.5 rounded-full bg-riesgo-critico text-white text-xs font-semibold">
                          {student.alertas_activas}
                        </span>
                      ) : (
                        <span className="text-gray-300 text-sm">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      <Link to={`/dashboard/students/${student.codigo}`} onClick={(e) => e.stopPropagation()}>
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
          <div className="divide-y divide-gray-100" aria-busy="true" aria-label="Cargando estudiantes">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-5 py-4 animate-pulse">
                <div className="h-4 bg-gray-200 rounded-md w-20 flex-shrink-0" />
                <div className="h-4 bg-gray-200 rounded-md w-48" />
                <div className="h-4 bg-gray-200 rounded-md w-10 flex-shrink-0" />
                <div className="h-4 bg-gray-200 rounded-md w-12 flex-shrink-0" />
                <div className="h-6 bg-gray-200 rounded-full w-16 flex-shrink-0" />
                <div className="h-6 bg-gray-200 rounded-full w-6 flex-shrink-0" />
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {!error && pages > 1 && (
          <div className="border-t border-gray-100 px-5 sm:px-6 py-3 flex items-center justify-between gap-3 flex-wrap">
            <p className="text-xs text-gray-500 tabular-nums">
              Mostrando {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, total)} de {total}
            </p>
            <div className="flex items-center gap-1">
              <button
                id="prev-page"
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                aria-label="Página anterior"
                className="p-2 rounded-[10px] hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-4 h-4 text-gray-600" />
              </button>
              {Array.from({ length: Math.min(pages, 7) }, (_, i) => {
                const p = i + 1;
                return (
                  <button
                    key={p}
                    onClick={() => setCurrentPage(p)}
                    aria-current={p === currentPage ? 'page' : undefined}
                    className={`w-8 h-8 rounded-[10px] text-xs font-medium tabular-nums transition-colors ${
                      p === currentPage
                        ? 'bg-primary text-white'
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
                aria-label="Página siguiente"
                className="p-2 rounded-[10px] hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
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
