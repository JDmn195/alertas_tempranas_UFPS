import { useState } from 'react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { X, ClipboardList, CheckCircle2, AlertTriangle } from 'lucide-react';

const API_BASE = 'https://alertas-tempranas-ufps.vercel.app';

const tabs = ['Activas', 'En Seguimiento', 'Atendidas', 'Cerradas'];

const alerts = [
  {
    id: '1',
    studentName: 'María Alejandra Ramírez González',
    studentCode: '1151234',
    riskLevel: 'high',
    alertType: 'Bajo Promedio - Crítico',
    generatedDate: '2026-04-05',
    assignedTeacher: 'Prof. Juan Pérez',
    status: 'active',
  },
  {
    id: '2',
    studentName: 'Carlos Andrés Mendoza Pérez',
    studentCode: '1151567',
    riskLevel: 'high',
    alertType: 'Múltiples Cursos Reprobados',
    generatedDate: '2026-04-04',
    assignedTeacher: 'Prof. María García',
    status: 'active',
  },
  {
    id: '3',
    studentName: 'Diego Fernando Castillo Ruiz',
    studentCode: '1152134',
    riskLevel: 'medium',
    alertType: 'Baja Tasa de Asistencia',
    generatedDate: '2026-04-03',
    assignedTeacher: 'Prof. Ana López',
    status: 'monitoring',
  },
  {
    id: '4',
    studentName: 'Ana María López Martínez',
    studentCode: '1152456',
    riskLevel: 'high',
    alertType: 'Tendencia Decreciente de Promedio',
    generatedDate: '2026-04-02',
    assignedTeacher: 'Prof. Juan Pérez',
    status: 'active',
  },
  {
    id: '5',
    studentName: 'Isabella Sofía Rodríguez Cruz',
    studentCode: '1153012',
    riskLevel: 'medium',
    alertType: 'Un Curso Reprobado',
    generatedDate: '2026-04-01',
    assignedTeacher: 'Prof. Carlos Ruiz',
    status: 'monitoring',
  },
  {
    id: '6',
    studentName: 'Valentina Andrea Morales Vargas',
    studentCode: '1153678',
    riskLevel: 'high',
    alertType: 'Bajo Promedio - Crítico',
    generatedDate: '2026-03-28',
    assignedTeacher: 'Prof. María García',
    status: 'active',
  },
];

// ─── Tipos ────────────────────────────────────────────────────────────────────
interface AlertItem {
  id: string;
  studentName: string;
  studentCode: string;
  riskLevel: string;
  alertType: string;
  generatedDate: string;
  assignedTeacher: string;
  status: string;
}

interface Intervencion {
  id: number;
  tipo: string;
  observaciones: string;
  fecha: string;
  usuario: string;
  usuario_rol: string;
}

// ─── Modal Registrar Intervención ─────────────────────────────────────────────
function ModalRegistrar({
  alerta,
  onClose,
  onSuccess,
}: {
  alerta: AlertItem;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [tipo, setTipo] = useState('');
  const [observaciones, setObservaciones] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const userJson = localStorage.getItem('user');
  const user = userJson ? JSON.parse(userJson) : null;

  const handleSubmit = async () => {
    if (!tipo) { setError('Selecciona el tipo de intervención'); return; }
    if (!observaciones.trim()) { setError('Las observaciones son obligatorias'); return; }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/${alerta.id}/intervenciones/registrar/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          usuario_id:    user?.id,
          tipo,
          observaciones: observaciones.trim(),
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || 'Error al registrar la intervención');
        return;
      }

      onSuccess();
      onClose();
    } catch {
      setError('No se pudo conectar con el servidor');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 z-10">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <ClipboardList className="w-5 h-5 text-[#C8102E]" />
            <h2 className="text-base font-bold text-gray-900">Registrar Intervención</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Info estudiante */}
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-100">
          <p className="text-xs text-gray-500">Estudiante</p>
          <p className="text-sm font-semibold text-gray-800">{alerta.studentName}</p>
          <p className="text-xs text-gray-500 mt-0.5">{alerta.alertType}</p>
        </div>

        {/* Formulario */}
        <div className="px-6 py-5 space-y-4">

          {/* Tipo */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tipo de intervención <span className="text-red-500">*</span>
            </label>
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] bg-white text-sm"
            >
              <option value="">Selecciona un tipo...</option>
              <option value="TUTORIA">Tutoría</option>
              <option value="CITACION">Citación</option>
              <option value="REMISION">Remisión</option>
            </select>
          </div>

          {/* Observaciones */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Observaciones <span className="text-red-500">*</span>
            </label>
            <textarea
              value={observaciones}
              onChange={(e) => setObservaciones(e.target.value)}
              rows={4}
              placeholder="Describe las acciones realizadas con el estudiante..."
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] text-sm resize-none"
            />
            <p className="text-xs text-gray-400 mt-1">{observaciones.length} caracteres</p>
          </div>

          {/* Responsable (solo lectura) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Responsable</label>
            <input
              type="text"
              value={user?.nombre || 'Usuario actual'}
              readOnly
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg bg-gray-50 text-sm text-gray-500 cursor-not-allowed"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
              <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-white bg-[#C8102E] rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {loading ? (
              <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Guardando...</>
            ) : (
              <><CheckCircle2 className="w-4 h-4" /> Guardar intervención</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Modal Historial ──────────────────────────────────────────────────────────
function ModalHistorial({
  alerta,
  onClose,
}: {
  alerta: AlertItem;
  onClose: () => void;
}) {
  const [intervenciones, setIntervenciones] = useState<Intervencion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const TIPO_LABEL: Record<string, string> = {
    TUTORIA: 'Tutoría',
    CITACION: 'Citación',
    REMISION: 'Remisión',
  };

  const TIPO_COLOR: Record<string, string> = {
    TUTORIA:  'bg-blue-100 text-blue-700',
    CITACION: 'bg-yellow-100 text-yellow-700',
    REMISION: 'bg-purple-100 text-purple-700',
  };

  // Cargar al abrir
  useState(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API_BASE}/${alerta.id}/intervenciones/`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        setIntervenciones(data.intervenciones);
      } catch {
        setError('No se pudo cargar el historial');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 z-10 max-h-[80vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <ClipboardList className="w-5 h-5 text-[#C8102E]" />
            <h2 className="text-base font-bold text-gray-900">Historial de Intervenciones</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Info estudiante */}
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-100">
          <p className="text-sm font-semibold text-gray-800">{alerta.studentName}</p>
          <p className="text-xs text-gray-500">{alerta.alertType}</p>
        </div>

        {/* Contenido */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="animate-pulse bg-gray-100 rounded-lg h-20" />
              ))}
            </div>
          )}

          {error && (
            <div className="text-center py-8">
              <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
              <p className="text-sm text-red-500">{error}</p>
            </div>
          )}

          {!loading && !error && intervenciones.length === 0 && (
            <div className="text-center py-10">
              <ClipboardList className="w-10 h-10 text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">No hay intervenciones registradas</p>
            </div>
          )}

          {!loading && !error && intervenciones.length > 0 && (
            <div className="space-y-3">
              {intervenciones.map((item) => (
                <div key={item.id} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-xs font-semibold px-2 py-1 rounded-full ${TIPO_COLOR[item.tipo] || 'bg-gray-100 text-gray-600'}`}>
                      {TIPO_LABEL[item.tipo] || item.tipo}
                    </span>
                    <span className="text-xs text-gray-400">{item.fecha}</span>
                  </div>
                  <p className="text-sm text-gray-700">{item.observaciones}</p>
                  <p className="text-xs text-gray-400 mt-2">Registrado por: <span className="font-medium text-gray-600">{item.usuario}</span></p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────
export default function AlertManagement() {
  const [activeTab, setActiveTab] = useState('Activas');
  const [modalRegistrar, setModalRegistrar] = useState<AlertItem | null>(null);
  const [modalHistorial, setModalHistorial] = useState<AlertItem | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const filteredAlerts = alerts.filter((alert) => {
    if (activeTab === 'Activas') return alert.status === 'active';
    if (activeTab === 'En Seguimiento') return alert.status === 'monitoring';
    return false;
  });

  const handleSuccess = () => {
    setSuccessMsg('Intervención registrada exitosamente');
    setTimeout(() => setSuccessMsg(null), 4000);
  };

  return (
    <div className="space-y-6">

      {/* Modales */}
      {modalRegistrar && (
        <ModalRegistrar
          alerta={modalRegistrar}
          onClose={() => setModalRegistrar(null)}
          onSuccess={handleSuccess}
        />
      )}
      {modalHistorial && (
        <ModalHistorial
          alerta={modalHistorial}
          onClose={() => setModalHistorial(null)}
        />
      )}

      {/* Header */}
      <div className="border-l-4 border-[#C8102E] pl-4">
        <h1 className="text-2xl font-bold text-gray-900">Gestión de Alertas</h1>
        <p className="text-sm text-gray-600 mt-1">
          Monitorear y gestionar alertas de riesgo de estudiantes en todos los programas
        </p>
      </div>

      {/* Toast éxito */}
      {successMsg && (
        <div className="flex items-center gap-2 p-4 bg-green-50 border border-green-200 rounded-lg">
          <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
          <p className="text-sm font-medium text-green-700">{successMsg}</p>
        </div>
      )}

      {/* Tabs y tabla */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200">
          <div className="flex">
            {tabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-6 py-4 text-sm font-medium transition-colors relative ${
                  activeTab === tab ? 'text-[#C8102E]' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab}
                {activeTab === tab && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#C8102E]" />}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#C8102E] text-white">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Estudiante</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Código</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Nivel de Riesgo</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Tipo de Alerta</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Fecha</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Docente Asignado</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Estado</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredAlerts.length > 0 ? (
                filteredAlerts.map((alert, index) => (
                  <tr key={alert.id} className={index % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5]'}>
                    <td className="px-6 py-4 text-sm text-gray-900">{alert.studentName}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{alert.studentCode}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {alert.riskLevel === 'high' && <Badge variant="high">ALTO</Badge>}
                      {alert.riskLevel === 'medium' && <Badge variant="medium">MEDIO</Badge>}
                      {alert.riskLevel === 'low' && <Badge variant="low">BAJO</Badge>}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{alert.alertType}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{alert.generatedDate}</td>
                    <td className="px-6 py-4 text-sm text-gray-900">{alert.assignedTeacher}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {alert.status === 'active' && <Badge variant="error" size="sm">Activa</Badge>}
                      {alert.status === 'monitoring' && <Badge variant="gray" size="sm">En seguimiento</Badge>}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => setModalHistorial(alert)}>
                          Ver historial
                        </Button>
                        <Button variant="primary" size="sm" onClick={() => setModalRegistrar(alert)}>
                          Registrar intervención
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center">
                    <div className="flex flex-col items-center">
                      <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mb-3">
                        <svg className="w-8 h-8 text-[#C8102E]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <p className="text-gray-500 text-sm">No se encontraron alertas en esta categoría</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {filteredAlerts.length > 0 && (
          <div className="border-t border-gray-200 px-6 py-4 bg-gray-50">
            <p className="text-sm text-gray-600">Mostrando {filteredAlerts.length} alertas</p>
          </div>
        )}
      </div>
    </div>
  );
}