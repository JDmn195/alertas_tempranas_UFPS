import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router';
import { AlertTriangle, BookOpen, Users, ChevronLeft, ChevronRight, RefreshCw, X } from 'lucide-react';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { apiFetch } from '../../services/apiFetch';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface EstudianteRiesgo {
  codigo: string;
  nombre: string;
  nivel_riesgo: 'high' | 'medium';
  alertas_activas: number;
}

interface CursoDoc {
  curso_id: number;
  materia: string;
  codigo: string;
  grupo: string;
  matriculados: number;
  en_riesgo: number;
  estado: string;
}

interface DashboardData {
  nombre_docente: string;
  cursos: CursoDoc[];
  total_en_riesgo: number;
}

export default function TeacherDashboard() {
  // Nombre del docente desde localStorage (JWT data)
  const userJson = localStorage.getItem('user');
  const user = userJson ? JSON.parse(userJson) : null;
  const nombreDocente = user?.nombre || 'Docente';

  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal detail states
  const [selectedCurso, setSelectedCurso] = useState<CursoDoc | null>(null);
  const [modalStudents, setModalStudents] = useState<EstudianteRiesgo[]>([]);
  const [modalPage, setModalPage] = useState(1);
  const [modalPages, setModalPages] = useState(1);
  const [modalTotal, setModalTotal] = useState(0);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(
        `${BASE_URL}/api/academico/teacher/dashboard/?page=1&page_size=100`
      );
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
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Error al cargar estudiantes del curso');
      }
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

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  useEffect(() => {
    if (selectedCurso) {
      fetchCursoStudents(selectedCurso.curso_id, modalPage);
    }
  }, [selectedCurso, modalPage, fetchCursoStudents]);

  const estadoBadge = (estado: string) => {
    if (estado === 'CRÍTICO') return 'bg-red-100 text-red-800';
    if (estado === 'EN OBSERVACIÓN') return 'bg-amber-100 text-amber-800';
    if (estado === 'ESTABLE') return 'bg-green-100 text-green-800';
    return 'bg-gray-100 text-gray-600';
  };

  const cursosEnRiesgo = data?.cursos.filter((c) => c.en_riesgo > 0) || [];

  return (
    <div className="space-y-6">
      {/* ── Banner de bienvenida ─────────────────────────────── */}
      <div className="bg-[#C8102E] text-white rounded-lg p-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold mb-1">Bienvenido, Prof. {nombreDocente}</h1>
          <p className="text-sm opacity-90">
            Panel de seguimiento · Cursos y estudiantes en riesgo asignados
          </p>
        </div>
        <button
          onClick={fetchDashboard}
          className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
          title="Actualizar"
        >
          <RefreshCw className={`w-5 h-5 text-white ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* ── Error ───────────────────────────────────────────── */}
      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-lg border border-red-200 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* ── Mis Cursos en Riesgo ─────────────────────────────────── */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-[#C8102E]" />
            <h2 className="text-lg font-semibold text-gray-900">Mis Cursos en Riesgo</h2>
          </div>
          {data && (
            <Badge variant="error" size="sm">
              {cursosEnRiesgo.length} cursos con riesgo
            </Badge>
          )}
        </div>

        {loading && !data ? (
          <div className="px-6 py-12 text-center text-gray-500">Cargando cursos...</div>
        ) : cursosEnRiesgo.length === 0 ? (
          <div className="px-6 py-12 text-center text-gray-500">No tienes cursos con estudiantes en riesgo.</div>
        ) : (
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {cursosEnRiesgo.map((curso) => (
              <div
                key={curso.curso_id}
                onClick={() => {
                  setSelectedCurso(curso);
                  setModalPage(1);
                  setModalStudents([]);
                }}
                className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow cursor-pointer hover:border-[#C8102E] flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-xs font-mono text-gray-500">
                      {curso.codigo} · Grupo {curso.grupo}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${estadoBadge(curso.estado)}`}>
                      {curso.estado}
                    </span>
                  </div>
                  <h3 className="font-semibold text-gray-900 line-clamp-1 mb-3">
                    {curso.materia}
                  </h3>
                </div>

                <div className="flex items-center justify-between text-sm text-gray-600 border-t border-gray-100 pt-3">
                  <span className="flex items-center gap-1">
                    <Users className="w-4 h-4 text-gray-400" />
                    {curso.matriculados} inscritos
                  </span>
                  <span className="flex items-center gap-1 text-[#C8102E] font-semibold">
                    <AlertTriangle className="w-4 h-4" />
                    {curso.en_riesgo} en riesgo
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Modal de Estudiantes en Riesgo del Curso ────────────────── */}
      {selectedCurso && (
        <>
          <div
            className="fixed inset-0 z-40 transition-opacity"
            style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
            onClick={() => setSelectedCurso(null)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-lg shadow-2xl border border-gray-200 w-full max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
              {/* Header */}
              <div className="bg-[#C8102E] text-white px-6 py-4 flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold">{selectedCurso.materia}</h2>
                  <p className="text-xs opacity-90">{selectedCurso.codigo} · Grupo {selectedCurso.grupo}</p>
                </div>
                <button
                  onClick={() => setSelectedCurso(null)}
                  className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg p-1.5 transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              {/* Content */}
              <div className="p-6 overflow-y-auto flex-1 space-y-4">
                {modalLoading && modalStudents.length === 0 ? (
                  <div className="py-12 text-center text-gray-500">Cargando estudiantes en riesgo...</div>
                ) : modalError ? (
                  <div className="p-4 bg-red-50 text-red-700 rounded-lg border border-red-200 flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 flex-shrink-0" />
                    {modalError}
                  </div>
                ) : modalStudents.length === 0 ? (
                  <div className="py-12 text-center text-gray-500">No hay estudiantes en riesgo registrados en este curso.</div>
                ) : (
                  <>
                    <div className="overflow-x-auto border border-gray-200 rounded-lg">
                      <table className="w-full text-sm">
                        <thead className="bg-[#C8102E] text-white">
                          <tr>
                            <th className="px-4 py-3 text-left font-medium uppercase tracking-wider">Estudiante</th>
                            <th className="px-4 py-3 text-left font-medium uppercase tracking-wider">Código</th>
                            <th className="px-4 py-3 text-left font-medium uppercase tracking-wider">Nivel Riesgo</th>
                            <th className="px-4 py-3 text-center font-medium uppercase tracking-wider">Alertas Activas</th>
                            <th className="px-4 py-3 text-center font-medium uppercase tracking-wider">Acciones</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          {modalStudents.map((est, idx) => (
                            <tr key={est.codigo} className={idx % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5] hover:bg-red-50 transition-colors'}>
                              <td className="px-4 py-3 font-medium text-gray-900">{est.nombre}</td>
                              <td className="px-4 py-3 text-gray-600 font-mono">{est.codigo}</td>
                              <td className="px-4 py-3">
                                {est.nivel_riesgo === 'high' && <Badge variant="high">ALTO</Badge>}
                                {est.nivel_riesgo === 'medium' && <Badge variant="medium">MEDIO</Badge>}
                              </td>
                              <td className="px-4 py-3 text-center">
                                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#C8102E] text-white text-xs font-bold">
                                  {est.alertas_activas}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-center">
                                <Link to={`/dashboard/students/${est.codigo}`}>
                                  <Button variant="outline" size="sm">Ver perfil</Button>
                                </Link>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Modal Pagination */}
                    {modalPages > 1 && (
                      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
                        <p className="text-xs text-gray-500">
                          Página {modalPage} de {modalPages} · {modalTotal} estudiantes
                        </p>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setModalPage((p) => Math.max(1, p - 1))}
                            disabled={modalPage <= 1 || modalLoading}
                          >
                            <ChevronLeft className="w-4 h-4 mr-1" /> Anterior
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setModalPage((p) => p + 1)}
                            disabled={modalPage >= modalPages || modalLoading}
                          >
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
