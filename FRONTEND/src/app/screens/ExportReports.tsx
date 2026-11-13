import { useState, useMemo, useEffect } from 'react';
import { 
  FileText, 
  Download, 
  Search, 
  AlertCircle, 
  BookOpen, 
  GraduationCap, 
  UserCheck, 
  BarChart3, 
  Users,
  Calendar,
  SearchX
} from 'lucide-react';
import { EncabezadoPagina } from '../components/Panel';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { apiFetch } from '../../services/apiFetch';
import { EstadoVacio } from '../components/Estados';

// ─── Interfaces y Configuraciones ─────────────────────────────────────────────
interface ColumnConfig {
  header: string;
  key: string;
  render?: (val: any, row: any) => React.ReactNode;
}

interface ReportConfig {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  columns: ColumnConfig[];
  data: any[];
}

export default function ExportReports() {
  const [selectedReportId, setSelectedReportId] = useState('riesgo-estudiantil');
  const [dateFrom, setDateFrom] = useState('2026-01-01');
  const [dateTo, setDateTo] = useState('2026-06-30');
  const [selectedRisk, setSelectedRisk] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [format, setFormat] = useState<'pdf' | 'excel'>('pdf');
  const [isAccordionOpen, setIsAccordionOpen] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [liveData, setLiveData] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fetchError, setFetchError] = useState('');

  // ─── Fetch de datos reales desde el backend ───────────────────────────────
  useEffect(() => {
    const fetchReportData = async () => {
      setIsLoading(true);
      setFetchError('');
      try {
        const baseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
        const res = await apiFetch(`${baseUrl}/api/alertas/reportes/?tipo=${selectedReportId}`);
        if (!res.ok) throw new Error(`Error ${res.status}`);
        const json = await res.json();
        setLiveData(json.data || []);
      } catch (err) {
        console.error('Error al cargar reporte:', err);
        setFetchError('No se pudo conectar al servidor. Mostrando datos de demostración.');
        // Fallback a los datos maquetados del reporte activo
        setLiveData(reports[selectedReportId]?.data ?? []);
      } finally {
        setIsLoading(false);
      }
    };
    fetchReportData();
  }, [selectedReportId]);

  // ─── Definición de los Reportes y Datos Maquetados ──────────────────────────
  const reports: Record<string, ReportConfig> = useMemo(() => ({
    'riesgo-estudiantil': {
      id: 'riesgo-estudiantil',
      title: 'Reporte de Riesgo Estudiantil',
      description: 'Listado de estudiantes clasificados por nivel de riesgo académico de acuerdo con las reglas vigentes.',
      icon: <AlertCircle className="w-5 h-5" />,
      columns: [
        { header: 'Código', key: 'code' },
        { header: 'Estudiante', key: 'name' },
        { header: 'Semestre', key: 'semester', render: (val) => `Semestre ${val}` },
        { header: 'Promedio', key: 'gpa', render: (val) => <span className="font-semibold text-ink">{val != null ? Number(val).toFixed(2) : '—'}</span> },
        { header: 'Alertas Activas', key: 'alerts', render: (val) => (
          <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold ${
            val > 3 ? 'bg-red-100 text-red-700' : val > 0 ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-ink-muted'
          }`}>{val}</span>
        )},
        { header: 'Nivel de Riesgo', key: 'risk', render: (val) => (
          <Badge variant={val === 'ALTO' ? 'high' : val === 'MEDIO' ? 'medium' : 'low'} size="sm">
            {val}
          </Badge>
        )}
      ],
      data: [
        { code: '1151234', name: 'María Alejandra Ramírez González', semester: 4, gpa: 2.75, alerts: 4, risk: 'ALTO', program: 'systems', date: '2026-03-10' },
        { code: '1151567', name: 'Carlos Andrés Mendoza Pérez', semester: 6, gpa: 2.90, alerts: 5, risk: 'ALTO', program: 'systems', date: '2026-03-15' },
        { code: '1151890', name: 'Laura Valentina Torres Silva', semester: 2, gpa: 4.10, alerts: 0, risk: 'BAJO', program: 'civil', date: '2026-02-28' },
        { code: '1152134', name: 'Diego Fernando Castillo Ruiz', semester: 5, gpa: 3.25, alerts: 2, risk: 'MEDIO', program: 'industrial', date: '2026-04-05' },
        { code: '1152456', name: 'Ana María López Martínez', semester: 3, gpa: 2.85, alerts: 4, risk: 'ALTO', program: 'mechanical', date: '2026-03-22' },
        { code: '1153012', name: 'Isabella Sofía Rodríguez Cruz', semester: 7, gpa: 3.42, alerts: 1, risk: 'MEDIO', program: 'systems', date: '2026-04-12' },
        { code: '1153678', name: 'Valentina Andrea Morales Vargas', semester: 3, gpa: 2.68, alerts: 3, risk: 'ALTO', program: 'civil', date: '2026-03-01' }
      ]
    },
    'resumen-alertas': {
      id: 'resumen-alertas',
      title: 'Reporte Resumen de Alertas',
      description: 'Estadísticas y bitácora de todas las alertas del sistema y sus respectivos estados.',
      icon: <BookOpen className="w-5 h-5" />,
      columns: [
        { header: 'Código Est.', key: 'studentCode' },
        { header: 'Estudiante', key: 'studentName' },
        { header: 'Tipo de Alerta', key: 'alertType' },
        { header: 'Regla Aplicada', key: 'rule' },
        { header: 'Fecha Generación', key: 'date' },
        { header: 'Estado', key: 'status', render: (val) => (
          <Badge variant={val === 'Activa' ? 'error' : val === 'En Seguimiento' ? 'medium' : val === 'Atendida' ? 'success' : 'gray'} size="sm">
            {val}
          </Badge>
        )}
      ],
      data: [
        { studentCode: '1151234', studentName: 'María Alejandra Ramírez', alertType: 'Promedio Crítico', rule: 'PPA < 3.0', date: '2026-03-10', status: 'Activa', risk: 'ALTO', program: 'systems' },
        { studentCode: '1151567', studentName: 'Carlos Andrés Mendoza', alertType: 'Reprobación Múltiple', rule: 'Materias Perdidas > 2', date: '2026-03-15', status: 'Activa', risk: 'ALTO', program: 'systems' },
        { studentCode: '1152134', studentName: 'Diego Fernando Castillo', alertType: 'Alerta Preventiva', rule: 'PPA < 3.4', date: '2026-04-05', status: 'En Seguimiento', risk: 'MEDIO', program: 'industrial' },
        { studentCode: '1152456', studentName: 'Ana María López Martínez', alertType: 'Promedio Crítico', rule: 'PPA < 3.0', date: '2026-03-22', status: 'Activa', risk: 'ALTO', program: 'mechanical' },
        { studentCode: '1153012', studentName: 'Isabella Sofía Rodríguez', alertType: 'Alerta Preventiva', rule: 'PPA < 3.4', date: '2026-04-12', status: 'Atendida', risk: 'MEDIO', program: 'systems' },
        { studentCode: '1153678', studentName: 'Valentina Andrea Morales', alertType: 'Promedio Crítico', rule: 'PPA < 3.0', date: '2026-03-01', status: 'Cerrada', risk: 'ALTO', program: 'civil' }
      ]
    },
    'rendimiento-academico': {
      id: 'rendimiento-academico',
      title: 'Reporte de Rendimiento Académico',
      description: 'Análisis detallado del rendimiento de los estudiantes, créditos aprobados y asignaturas cursadas.',
      icon: <GraduationCap className="w-5 h-5" />,
      columns: [
        { header: 'Código', key: 'code' },
        { header: 'Estudiante', key: 'name' },
        { header: 'Semestre', key: 'semester', render: (val) => `Semestre ${val}` },
        { header: 'Promedio PPA', key: 'gpa', render: (val) => <span className="font-semibold text-ink">{val != null ? Number(val).toFixed(2) : '—'}</span> },
        { header: 'Aprobadas', key: 'passed', render: (val) => <span className="text-green-600 font-medium">{val}</span> },
        { header: 'Reprobadas', key: 'failed', render: (val) => <span className="text-red-600 font-medium">{val}</span> },
        { header: 'Créditos Aprobados', key: 'credits', render: (val) => `${val} / 165` }
      ],
      data: [
        { code: '1151234', name: 'María Alejandra Ramírez González', semester: 4, gpa: 2.75, passed: 12, failed: 5, credits: 45, risk: 'ALTO', program: 'systems', date: '2026-03-10' },
        { code: '1151567', name: 'Carlos Andrés Mendoza Pérez', semester: 6, gpa: 2.90, passed: 18, failed: 6, credits: 62, risk: 'ALTO', program: 'systems', date: '2026-03-15' },
        { code: '1151890', name: 'Laura Valentina Torres Silva', semester: 2, gpa: 4.10, passed: 8, failed: 0, credits: 28, risk: 'BAJO', program: 'civil', date: '2026-02-28' },
        { code: '1152134', name: 'Diego Fernando Castillo Ruiz', semester: 5, gpa: 3.25, passed: 15, failed: 2, credits: 54, risk: 'MEDIO', program: 'industrial', date: '2026-04-05' },
        { code: '1152456', name: 'Ana María López Martínez', semester: 3, gpa: 2.85, passed: 9, failed: 4, credits: 32, risk: 'ALTO', program: 'mechanical', date: '2026-03-22' }
      ]
    },
    'reprobacion-cursos': {
      id: 'reprobacion-cursos',
      title: 'Análisis de Reprobación de Cursos',
      description: 'Identificación de asignaturas críticas con alta tasa de reprobación y deserción semestral.',
      icon: <BarChart3 className="w-5 h-5" />,
      columns: [
        { header: 'Materia', key: 'subject' },
        { header: 'Código Curso', key: 'courseCode' },
        { header: 'Grupo', key: 'group', render: (val) => `Grupo ${val}` },
        { header: 'Docente', key: 'teacher' },
        { header: 'Matriculados', key: 'enrolled' },
        { header: 'Reprobados', key: 'failedCount', render: (val) => <span className="text-red-600 font-semibold">{val}</span> },
        { header: 'Tasa de Reprobación', key: 'rate', render: (val) => (
          <div className="flex items-center gap-2">
            <div className="w-16 bg-gray-200 h-2 rounded-full overflow-hidden">
              <div 
                className={`h-full rounded-full ${val > 35 ? 'bg-red-600' : val > 20 ? 'bg-amber-500' : 'bg-green-500'}`}
                style={{ width: `${val}%` }}
              />
            </div>
            <span className="font-semibold text-ink text-xs">{val}%</span>
          </div>
        )}
      ],
      data: [
        { courseCode: '1150001', subject: 'Cálculo Diferencial', group: 'A', teacher: 'Ing. Carlos Julio Patiño', enrolled: 42, failedCount: 16, rate: 38, program: 'systems', risk: 'ALTO', date: '2026-03-10' },
        { courseCode: '1150005', subject: 'Estructuras de Datos', group: 'B', teacher: 'Mag. Nancy Elizabeth', enrolled: 35, failedCount: 9, rate: 25, program: 'systems', risk: 'MEDIO', date: '2026-03-15' },
        { courseCode: '1150012', subject: 'Física Mecánica', group: 'C', teacher: 'Fis. Álvaro Mendoza', enrolled: 38, failedCount: 14, rate: 36, program: 'civil', risk: 'ALTO', date: '2026-02-28' },
        { courseCode: '1150020', subject: 'Introducción a la Ingeniería', group: 'A', teacher: 'Ing. Juan Carlos', enrolled: 45, failedCount: 2, rate: 4, program: 'industrial', risk: 'BAJO', date: '2026-04-05' },
        { courseCode: '1150035', subject: 'Diseño Mecánico I', group: 'B', teacher: 'Ing. Rodrigo Higuera', enrolled: 28, failedCount: 6, rate: 21, program: 'mechanical', risk: 'MEDIO', date: '2026-03-22' }
      ]
    },
    'seguimiento-intervenciones': {
      id: 'seguimiento-intervenciones',
      title: 'Reporte de Seguimiento de Intervenciones',
      description: 'Estado de las citas, asesorías y remisiones efectuadas con los estudiantes en riesgo.',
      icon: <UserCheck className="w-5 h-5" />,
      columns: [
        { header: 'Fecha', key: 'date' },
        { header: 'Estudiante', key: 'student' },
        { header: 'Tipo', key: 'type', render: (val) => (
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
            val === 'Tutoría' ? 'bg-blue-50 text-blue-700 border border-blue-200' :
            val === 'Citación' ? 'bg-amber-50 text-amber-700 border border-amber-200' :
            'bg-purple-50 text-purple-700 border border-purple-200'
          }`}>{val}</span>
        )},
        { header: 'Responsable', key: 'counselor' },
        { header: 'Resultado', key: 'result', render: (val) => (
          <Badge variant={val === 'Satisfactorio' ? 'success' : val === 'Pendiente' ? 'medium' : 'gray'} size="sm">
            {val}
          </Badge>
        )},
        { header: 'Evidencias', key: 'evidenceCount', render: (val) => (
          <span className="text-ink-muted text-xs font-medium">{val > 0 ? `📄 ${val} archivos` : '❌ Sin evidencia'}</span>
        )},
        { header: 'Observaciones', key: 'notes', render: (val) => (
          <span className="text-ink-muted max-w-[200px] truncate block text-xs" title={val}>{val}</span>
        )}
      ],
      data: [
        { date: '2026-04-10', student: 'María Alejandra Ramírez', type: 'Tutoría', counselor: 'Prof. Juan Pérez', result: 'Satisfactorio', evidenceCount: 2, notes: 'Se resolvieron dudas de matrices y cálculo de derivadas.', program: 'systems', risk: 'ALTO' },
        { date: '2026-04-12', student: 'Carlos Andrés Mendoza', type: 'Citación', counselor: 'Bienestar Universitario', result: 'Pendiente', evidenceCount: 0, notes: 'El estudiante no asistió a la primera citación de orientación.', program: 'systems', risk: 'ALTO' },
        { date: '2026-04-15', student: 'Diego Fernando Castillo', type: 'Remisión', counselor: 'Psicología Bienestar', result: 'En Proceso', evidenceCount: 1, notes: 'Se realiza remisión al área psicosocial por problemas familiares.', program: 'industrial', risk: 'MEDIO' },
        { date: '2026-04-18', student: 'Ana María López Martínez', type: 'Tutoría', counselor: 'Prof. Juan Pérez', result: 'Satisfactorio', evidenceCount: 3, notes: 'Asesoría en diseño conceptual y planos mecánicos.', program: 'mechanical', risk: 'ALTO' }
      ]
    },
    'analisis-cohortes': {
      id: 'analisis-cohortes',
      title: 'Reporte de Análisis de Cohortes',
      description: 'Comparativo global del rendimiento, promedio de notas y número de alertas por períodos académicos.',
      icon: <Users className="w-5 h-5" />,
      columns: [
        { header: 'Cohorte / Semestre', key: 'cohort', render: (val) => <span className="font-semibold text-ink">{val}</span> },
        { header: 'Total Estudiantes', key: 'totalStudents' },
        { header: 'Promedio Cohorte', key: 'averageGpa', render: (val) => <span className="font-semibold text-ink">{val != null ? Number(val).toFixed(2) : '—'}</span> },
        { header: 'Riesgo Alto', key: 'highRisk', render: (val) => <Badge variant="high" size="xs">{val} est.</Badge> },
        { header: 'Riesgo Medio', key: 'mediumRisk', render: (val) => <Badge variant="medium" size="xs">{val} est.</Badge> },
        { header: 'Riesgo Bajo', key: 'lowRisk', render: (val) => <Badge variant="low" size="xs">{val} est.</Badge> },
        { header: 'Total Alertas', key: 'totalAlerts', render: (val) => (
          <span className="bg-red-50 text-red-700 px-2 py-0.5 border border-red-200 rounded text-xs font-semibold">{val}</span>
        )}
      ],
      data: [
        { cohort: 'Periodo 2024-2', totalStudents: 185, averageGpa: 3.48, highRisk: 14, mediumRisk: 28, lowRisk: 143, totalAlerts: 42, program: 'systems', risk: 'BAJO', date: '2026-01-10' },
        { cohort: 'Periodo 2025-1', totalStudents: 210, averageGpa: 3.32, highRisk: 22, mediumRisk: 41, lowRisk: 147, totalAlerts: 68, program: 'systems', risk: 'MEDIO', date: '2026-03-10' },
        { cohort: 'Periodo 2025-2', totalStudents: 195, averageGpa: 3.15, highRisk: 31, mediumRisk: 52, lowRisk: 112, totalAlerts: 85, program: 'systems', risk: 'ALTO', date: '2026-04-10' }
      ]
    }
  }), []);

  // ─── Filtrado Interactivo de los Datos (SDAT-134 / Frontend reactive) ───────
  const activeReport = reports[selectedReportId];

  const filteredData = useMemo(() => {
    // Usa liveData (API real) si está disponible, si no los datos maquetados
    const source = liveData.length > 0 ? liveData : (activeReport?.data ?? []);
    return source.filter((item) => {
      // 1. Filtro por término de búsqueda
      const textToSearch = (
        (item.name || '') + ' ' +
        (item.code || '') + ' ' +
        (item.studentName || '') + ' ' +
        (item.studentCode || '') + ' ' +
        (item.subject || '') + ' ' +
        (item.student || '') + ' ' +
        (item.cohort || '')
      ).toLowerCase();
      if (searchTerm.trim() && !textToSearch.includes(searchTerm.toLowerCase())) {
        return false;
      }

      // 2. Filtro por nivel de riesgo
      if (selectedRisk) {
        const itemRisk = (item.risk || '').toLowerCase();
        const mappedRisk = selectedRisk === 'high' ? 'alto' : selectedRisk === 'medium' ? 'medio' : 'bajo';
        // Los datos de la API devuelven 'high'/'medium'/'low' directamente
        const apiRisk = selectedRisk;
        if (itemRisk !== mappedRisk && itemRisk !== apiRisk) return false;
      }

      // 3. Filtro por fecha (rango)
      if (item.date) {
        const itemDate = new Date(item.date);
        const fromDate = new Date(dateFrom);
        const toDate = new Date(dateTo);
        if (itemDate < fromDate || itemDate > toDate) {
          return false;
        }
      }

      return true;
    });
  }, [liveData, activeReport, searchTerm, selectedRisk, dateFrom, dateTo]);

  return (
    <div className="space-y-5">
      {/* Cabecera */}
      <EncabezadoPagina
        titulo="Reportes"
        detalle="Elige un reporte, ajusta el periodo y los filtros, revisa la vista previa y expórtalo."
      />

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* Panel Izquierdo: Configuración */}
        <div className="xl:col-span-5 bg-white rounded-[14px] border border-line p-5 space-y-5">
          <h2 className="text-base font-semibold text-ink">Configuración del Reporte</h2>

          {/* Tipo de Reporte */}
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-ink-muted">
              Tipo de Reporte
            </label>
            <select
              value={selectedReportId}
              onChange={(e) => setSelectedReportId(e.target.value)}
              className="w-full h-10 px-3.5 text-sm border border-line-strong rounded-[10px] bg-white text-ink font-medium"
            >
              {Object.values(reports).map((r) => (
                <option key={r.id} value={r.id}>{r.title}</option>
              ))}
            </select>
          </div>

          {/* Rango de Fechas */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-ink-muted">Fecha Desde</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full h-10 px-3.5 text-sm border border-line-strong rounded-[10px] bg-white text-ink"
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-ink-muted">Fecha Hasta</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full h-10 px-3.5 text-sm border border-line-strong rounded-[10px] bg-white text-ink"
              />
            </div>
          </div>

          {/* Nivel de Riesgo */}
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-ink-muted">
              Nivel de Riesgo <span className="text-ink-faint font-normal">(Opcional)</span>
            </label>
            <select
              value={selectedRisk}
              onChange={(e) => setSelectedRisk(e.target.value)}
              className="w-full h-10 px-3.5 text-sm border border-line-strong rounded-[10px] bg-white text-ink"
            >
              <option value="">Todos los Niveles</option>
              <option value="high">Riesgo Alto</option>
              <option value="medium">Riesgo Medio</option>
              <option value="low">Riesgo Bajo</option>
            </select>
          </div>

          {/* Formato de Exportación */}
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-ink-muted">Formato de Exportación</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setFormat('pdf')}
                className={`px-4 h-10 rounded-[10px] border font-medium transition-all text-sm flex items-center justify-center gap-2 ${
                  format === 'pdf'
                    ? 'border-primary bg-primary-tint text-primary'
                    : 'border-line-strong bg-white text-ink-muted hover:border-ink-faint'
                }`}
              >
                <FileText className="w-4 h-4" />
                PDF
              </button>
              <button
                type="button"
                onClick={() => setFormat('excel')}
                className={`px-4 h-10 rounded-[10px] border font-medium transition-all text-sm flex items-center justify-center gap-2 ${
                  format === 'excel'
                    ? 'border-primary bg-primary-tint text-primary'
                    : 'border-line-strong bg-white text-ink-muted hover:border-ink-faint'
                }`}
              >
                <FileText className="w-4 h-4" />
                Excel
              </button>
            </div>
          </div>

          {/* Botón principal */}
          <Button fullWidth size="lg" className="w-full font-semibold" onClick={async () => {
            const baseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
            const params = new URLSearchParams({
              tipo: selectedReportId,
              formato: format,
              fecha_desde: dateFrom,
              fecha_hasta: dateTo,
              ...(selectedRisk && { riesgo: selectedRisk }),
            });
            try {
              const res = await apiFetch(`${baseUrl}/api/alertas/reportes/exportar/?${params.toString()}`);
              if (!res.ok) throw new Error(`Error ${res.status}`);
              const blob = await res.blob();
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `reporte-${selectedReportId}-${dateFrom}.${format === 'pdf' ? 'pdf' : 'xlsx'}`;
              document.body.appendChild(a);
              a.click();
              a.remove();
              URL.revokeObjectURL(url);
            } catch (err) {
              console.error('Error al descargar reporte:', err);
            }
          }}>
            <Download className="w-4 h-4 mr-2" />
            Generar y Descargar
          </Button>
        </div>


        {/* Panel Derecho: Vista Previa Dinámica (7 columnas) */}
        <div className="xl:col-span-7 bg-white rounded-[14px] border border-line overflow-hidden flex flex-col">
          <div className="border-b border-line px-5 py-4 bg-paper flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-ink">Vista Previa Interactiva</h2>
              <p className="text-xs text-ink-muted mt-0.5">Mostrando estructura del {activeReport?.title}</p>
            </div>

            {/* Barra de Búsqueda Integrada (SDAT-134) */}
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-ink-faint" />
              <input
                type="text"
                placeholder="Buscar en el reporte..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full md:w-56 pl-9 pr-4 py-1.5 text-xs border border-line-strong rounded-[10px] focus:outline-none focus:ring-2 focus:ring-primary bg-white text-ink-soft placeholder-gray-400"
              />
            </div>
          </div>

          <div className="p-6 flex-1 flex flex-col">
            {/* Cabecera membretada de la previsualización */}
            <div className="mb-6 pb-4 border-b border-line flex justify-between items-start">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <img src="/logo-ufps.svg" alt="UFPS" className="h-8 w-auto" />
                  <div>
                    <h3 className="font-semibold text-ink text-xs">UFPS</h3>
                    <p className="text-[10px] text-ink-faint leading-none">División de Planificación y Sistemas</p>
                  </div>
                </div>
                <h4 className="font-semibold text-ink text-sm mt-2">{activeReport?.title}</h4>
                <p className="text-[11px] text-ink-muted mt-1 max-w-md">{activeReport?.description}</p>
              </div>

              <div className="text-right text-[10px] text-ink-faint">
                <p>Generado: {new Date().toLocaleDateString()}</p>
                <p className="mt-0.5">Filtro Período: {dateFrom} al {dateTo}</p>
              </div>
            </div>

            {/* Banner de error de conexión */}
            {fetchError && (
              <div className="mb-4 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-[10px] flex items-center gap-2 text-xs text-amber-700">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{fetchError} Revisa tu conexión y recarga la página para ver los datos reales.</span>
              </div>
            )}

            {/* Tabla Dinámica — preview de 5 filas */}
            <div className="overflow-x-auto flex-1 border border-line rounded-[10px]">
              <table className="tabular-nums w-full border-collapse text-left">
                <thead>
                  <tr className="bg-paper text-ink-soft border-b border-line">
                    {activeReport?.columns.map((col, idx) => (
                      <th key={idx} className="px-4 py-3 text-xs font-semibold">
                        {col.header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {isLoading ? (
                    Array.from({ length: 5 }).map((_, rowIdx) => (
                      <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-paper'}>
                        {activeReport?.columns.map((_, colIdx) => (
                          <td key={colIdx} className="px-4 py-3">
                            <div className="h-3 bg-wash rounded animate-pulse" style={{ width: `${60 + (colIdx * 13) % 35}%` }} />
                          </td>
                        ))}
                      </tr>
                    ))
                  ) : filteredData.slice(0, 5).length > 0 ? (
                    filteredData.slice(0, 5).map((row, rowIdx) => (
                      <tr
                        key={rowIdx}
                        className={`text-sm hover:bg-paper transition-colors ${
                          rowIdx % 2 === 0 ? 'bg-white' : 'bg-paper'
                        }`}
                      >
                        {activeReport!.columns.map((col, colIdx) => {
                          const cellVal = row[col.key];
                          return (
                            <td key={colIdx} className="px-4 py-3 text-xs text-ink-soft">
                              {col.render ? col.render(cellVal, row) : (cellVal ?? '—')}
                            </td>
                          );
                        })}
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={activeReport?.columns.length || 1}>
                        <EstadoVacio
                          icono={SearchX}
                          titulo="Sin registros para este reporte"
                          detalle={`No hay datos entre ${dateFrom} y ${dateTo}${selectedRisk || searchTerm.trim() ? ' con los filtros aplicados' : ''}. Amplía el rango de fechas o cambia el nivel de riesgo.`}
                        >
                          {(searchTerm.trim() || selectedRisk) && (
                            <Button variant="outline" size="sm" onClick={() => { setSearchTerm(''); setSelectedRisk(''); }}>
                              Quitar filtros
                            </Button>
                          )}
                        </EstadoVacio>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Botón Ver detalles */}
            {!isLoading && filteredData.length > 0 && (
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={() => setIsDetailOpen(true)}
                  className="px-3 py-1.5 text-xs font-semibold rounded-[10px] border border-primary text-primary hover:bg-primary-tint transition-colors"
                >
                  Ver detalles completos →
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ─── Modal de Detalle Completo ─────────────────────────────────────────── */}
      {isDetailOpen && (
        <div
          className="fixed inset-0 animate-in fade-in duration-150 z-50 flex items-center justify-center p-4"
          style={{ backgroundColor: 'rgba(0,0,0,0.55)' }}
          onClick={(e) => { if (e.target === e.currentTarget) setIsDetailOpen(false); }}
        >
          <div className="bg-white rounded-[14px] shadow-2xl w-full max-w-7xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-150">
            {/* Cabecera del modal */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-gray-50">
              <div className="flex items-center gap-3">
                <img src="/logo-ufps.svg" alt="UFPS" className="h-8 w-auto" />
                <div>
                  <h2 className="font-semibold text-ink text-base">{activeReport?.title}</h2>
                  <p className="text-xs text-ink-muted">{filteredData.length} registros · Generado {new Date().toLocaleDateString()}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsDetailOpen(false)}
                className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-gray-200 text-ink-muted transition-colors text-lg font-semibold"
              >
                ✕
              </button>
            </div>

            {/* Barra de búsqueda dentro del modal */}
            <div className="px-6 py-3 border-b border-line bg-white flex items-center gap-3">
              <Search className="w-4 h-4 text-ink-faint" />
              <input
                type="text"
                placeholder="Buscar en todos los registros..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="flex-1 text-sm border-0 outline-none text-ink-soft placeholder-gray-400"
              />
              <span className="text-xs text-ink-faint bg-gray-100 px-2 py-1 rounded">
                {filteredData.length} resultados
              </span>
            </div>

            {/* Tabla completa scrollable */}
            <div className="flex-1 overflow-auto">
              <table className="tabular-nums w-full border-collapse text-left">
                <thead className="sticky top-0 z-10">
                  <tr className="bg-paper text-ink-soft border-b border-line">
                    <th className="px-4 py-3 text-xs font-semibold">#</th>
                    {activeReport?.columns.map((col, idx) => (
                      <th key={idx} className="px-4 py-3 text-xs font-semibold whitespace-nowrap">
                        {col.header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {filteredData.map((row, rowIdx) => (
                    <tr
                      key={rowIdx}
                      className={`text-sm hover:bg-paper transition-colors ${
                        rowIdx % 2 === 0 ? 'bg-white' : 'bg-paper'
                      }`}
                    >
                      <td className="px-4 py-3 text-xs text-ink-faint tabular-nums">{rowIdx + 1}</td>
                      {activeReport!.columns.map((col, colIdx) => {
                        const cellVal = row[col.key];
                        return (
                          <td key={colIdx} className="px-4 py-3 text-xs text-ink-soft whitespace-nowrap">
                            {col.render ? col.render(cellVal, row) : (cellVal ?? '—')}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>


            {/* Footer del modal con botón de exportación */}
            <div className="px-6 py-4 border-t border-line bg-gray-50 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setIsDetailOpen(false)}
                className="px-4 py-2 text-sm font-medium text-ink-muted border border-line-strong rounded-[10px] hover:bg-gray-100 transition-colors"
              >
                Cerrar
              </button>
              <button
                type="button"
                onClick={() => {
                  const baseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
                  const params = new URLSearchParams({
                    tipo: selectedReportId,
                    formato: format,
                    fecha_desde: dateFrom,
                    fecha_hasta: dateTo,
                    ...(selectedRisk && { riesgo: selectedRisk }),
                  });
                  window.location.href = `${baseUrl}/api/alertas/reportes/exportar/?${params.toString()}`;
                }}
                className="px-4 py-2 text-sm font-semibold text-white bg-primary rounded-[10px] hover:bg-primary-strong transition-colors flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Exportar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
