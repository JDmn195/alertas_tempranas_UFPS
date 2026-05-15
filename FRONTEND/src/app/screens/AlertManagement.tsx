import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { X, ClipboardList, CheckCircle2, AlertTriangle, Filter, ExternalLink, RefreshCw, ChevronRight } from 'lucide-react';

const API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/alertas`;

const RISK_CONFIG: Record<string, { label: string; variant: 'high' | 'medium' | 'low' }> = {
  high: { label: 'ALTO', variant: 'high' },
  medium: { label: 'MEDIO', variant: 'medium' },
  low: { label: 'BAJO', variant: 'low' },
  alto: { label: 'ALTO', variant: 'high' },
  medio: { label: 'MEDIO', variant: 'medium' },
  bajo: { label: 'BAJO', variant: 'low' },
  ALTO: { label: 'ALTO', variant: 'high' },
  MEDIO: { label: 'MEDIO', variant: 'medium' },
  BAJO: { label: 'BAJO', variant: 'low' },
};

const tabMapping: Record<string, string> = {
  'Activas': 'activa',
  'En Seguimiento': 'en_monitoreo',
  'Atendidas': 'atendida',
  'Cerradas': 'cerrada'
};

// ─── Tipos ────────────────────────────────────────────────────────────────────
interface AlertItem {
  id: string | number;
  studentName: string;
  studentCode: string;
  riskLevel: string;
  alertType: string;
  generatedDate: string;
  status: string;
  tipo_regla: string;
  valor_causa?: number;
  metadata?: any;
}

interface Intervencion {
  id: number;
  tipo: string;
  observaciones: string;
  fecha: string;
  usuario: string;
}

interface Conteos {
  activa: number;
  en_monitoreo: number;
  atendida: number;
  cerrada: number;
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
          usuario_id: user?.id,
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
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 z-10">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <ClipboardList className="w-5 h-5 text-[#C8102E]" />
            <h2 className="text-base font-bold text-gray-900">Registrar Intervención</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-100">
          <p className="text-xs text-gray-500">Estudiante</p>
          <p className="text-sm font-semibold text-gray-800">{alerta.studentName}</p>
          <p className="text-xs text-gray-500 mt-0.5">{alerta.alertType}</p>
        </div>
        <div className="px-6 py-5 space-y-4">
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
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Observaciones <span className="text-red-500">*</span>
            </label>
            <textarea
              value={observaciones}
              onChange={(e) => setObservaciones(e.target.value)}
              rows={4}
              placeholder="Describe las acciones realizadas..."
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] text-sm resize-none"
            />
          </div>
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
              <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}
        </div>
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
            Cancelar
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-white bg-[#C8102E] rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {loading ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            Guardar intervención
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
  const navigate = useNavigate();

  const TIPO_LABEL: Record<string, string> = { TUTORIA: 'Tutoría', CITACION: 'Citación', REMISION: 'Remisión' };
  const TIPO_COLOR: Record<string, string> = { TUTORIA: 'bg-blue-100 text-blue-700', CITACION: 'bg-yellow-100 text-yellow-700', REMISION: 'bg-purple-100 text-purple-700' };

  useEffect(() => {
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
  }, [alerta.id]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 z-10 max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <ClipboardList className="w-5 h-5 text-[#C8102E]" />
            <h2 className="text-base font-bold text-gray-900">Historial de Intervenciones</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-100">
          <p className="text-sm font-semibold text-gray-800">{alerta.studentName}</p>
          <p className="text-xs text-gray-500">{alerta.alertType}</p>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && <div className="text-center py-10">Cargando...</div>}
          {error && <p className="text-sm text-red-500 text-center">{error}</p>}
          {!loading && intervenciones.length === 0 && <p className="text-sm text-gray-500 text-center py-10">Sin intervenciones registradas</p>}
          {!loading && intervenciones.map((item) => (
            <div key={item.id} className="border border-gray-200 rounded-lg p-4 mb-3">
              <div className="flex items-center justify-between mb-2">
                <span className={`text-xs font-semibold px-2 py-1 rounded-full ${TIPO_COLOR[item.tipo] || 'bg-gray-100 text-gray-600'}`}>
                  {TIPO_LABEL[item.tipo] || item.tipo}
                </span>
                <span className="text-xs text-gray-400">{item.fecha}</span>
              </div>
              <p className="text-sm text-gray-700">{item.observaciones}</p>
              <div className="flex justify-between items-center mt-3 pt-3 border-t border-gray-100">
                <p className="text-xs text-gray-400">Por: <span className="font-medium text-gray-600">{item.usuario}</span></p>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-7 text-[10px] gap-1 hover:bg-gray-50"
                  onClick={() => navigate(`/dashboard/intervenciones/${item.id}/evidencias`)}
                >
                  <ExternalLink className="w-3 h-3" /> Ver Evidencias
                </Button>
              </div>
            </div>
          ))}
        </div>
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <Button variant="outline" size="sm" onClick={onClose}>Cerrar</Button>
        </div>
      </div>
    </div>
  );
}

// ─── Componente Principal ─────────────────────────────────────────────────────
export default function AlertManagement() {
  const [activeTab, setActiveTab] = useState('Activas');
  const [filterType, setFilterType] = useState('all');
  const [alertsList, setAlertsList] = useState<AlertItem[]>([]);
  const [conteos, setConteos] = useState<Conteos>({ activa: 0, en_monitoreo: 0, atendida: 0, cerrada: 0 });
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [expandedStudents, setExpandedStudents] = useState<Record<string, boolean>>({});

  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const navigate = useNavigate();

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const stateParam = tabMapping[activeTab];
      const res = await fetch(`${API_BASE}/?estado=${stateParam}&tipo_regla=${filterType}`);
      const data = await res.json();
      setAlertsList(data.alertas);
      setConteos(data.conteos);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [activeTab, filterType]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const handleGenerateAlerts = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/alertas/generar/`, {
        method: 'POST'
      });
      const data = await res.json();
      setSuccessMsg(`Proceso completado: ${data.nuevas_alertas} alertas procesadas.`);
      fetchAlerts();
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err) {
      alert('Error al conectar con el servicio de alertas');
    } finally {
      setGenerating(false);
    }
  };

  const handleCerrarAlerta = async (id: string | number) => {
    try {
      await fetch(`${API_BASE}/${id}/cerrar/`, { method: 'POST' });
      setSuccessMsg('Alerta cerrada correctamente');
      fetchAlerts();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (e) {
      console.error(e);
    }
  };

  const toggleStudent = (code: string) => {
    setExpandedStudents(prev => ({ ...prev, [code]: !prev[code] }));
  };

  // Agrupar alertas por estudiante
  const groupedAlerts = alertsList.reduce((acc: Record<string, any>, alert) => {
    if (!acc[alert.studentCode]) {
      acc[alert.studentCode] = {
        studentName: alert.studentName,
        studentCode: alert.studentCode,
        alerts: []
      };
    }
    acc[alert.studentCode].alerts.push(alert);
    return acc;
  }, {});

  const studentGroups = Object.values(groupedAlerts);

  return (
    <div className="space-y-6 pb-20 max-w-7xl mx-auto px-4 sm:px-6">
      {showModal && selectedAlert && (
        <ModalRegistrar 
          alerta={selectedAlert} 
          onClose={() => setShowModal(false)} 
          onSuccess={() => { setSuccessMsg('Intervención registrada'); fetchAlerts(); setTimeout(() => setSuccessMsg(null), 3000); }} 
        />
      )}
      {showHistory && selectedAlert && (
        <ModalHistorial 
          alerta={selectedAlert} 
          onClose={() => setShowHistory(false)} 
        />
      )}

      {/* Header section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mt-4">
        <div className="border-l-4 border-[#C8102E] pl-4">
          <h1 className="text-2xl font-extrabold text-gray-900">Gestión de Alertas</h1>
          <p className="text-sm text-gray-500 font-medium">Monitoreo y seguimiento del riesgo académico estudiantil.</p>
        </div>
        
        <div className="flex items-center gap-3 bg-white p-1.5 rounded-2xl border border-gray-200 shadow-sm">
          <div className="flex items-center gap-2 px-3 border-r border-gray-100">
            <Filter className="w-4 h-4 text-gray-400" />
            <select 
              value={filterType} 
              onChange={(e) => setFilterType(e.target.value)}
              className="text-xs font-bold text-gray-700 border-none focus:ring-0 bg-transparent cursor-pointer uppercase"
            >
              <option value="all">TODOS LOS TIPOS</option>
              <option value="PROMEDIO">PROMEDIO</option>
              <option value="REPROBACION">REPROBACIÓN</option>
              <option value="ATRASO">ATRASO</option>
            </select>
          </div>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={handleGenerateAlerts} 
            disabled={generating}
            className="text-[#C8102E] hover:bg-red-50 gap-2 h-9 px-4 rounded-xl"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
            <span className="text-[11px] font-extrabold uppercase tracking-widest">{generating ? 'Procesando...' : 'Actualizar'}</span>
          </Button>
        </div>
      </div>

      {successMsg && (
        <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-2xl animate-in fade-in slide-in-from-top-4">
          <CheckCircle2 className="w-5 h-5 text-green-500" />
          <p className="text-sm font-semibold text-green-700">{successMsg}</p>
        </div>
      )}

      {/* Tabs Control */}
      <div className="bg-white rounded-3xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="flex border-b border-gray-100 bg-gray-50/50 p-1.5">
          {Object.keys(tabMapping).map((tab) => {
            const state = tabMapping[tab] as keyof Conteos;
            const count = conteos[state] || 0;
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 py-3 px-4 text-[10px] font-extrabold uppercase tracking-widest transition-all relative flex items-center justify-center gap-2 rounded-xl ${isActive ? 'bg-white text-[#C8102E] shadow-sm ring-1 ring-black/5' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100/50'}`}
              >
                {tab}
                <span className={`px-2 py-0.5 rounded-full text-[9px] ${isActive ? 'bg-[#C8102E] text-white' : 'bg-gray-200 text-gray-500'}`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Content List */}
        <div className="divide-y divide-gray-50">
          {loading ? (
            <div className="py-24 flex flex-col items-center justify-center space-y-4">
              <div className="w-12 h-12 border-4 border-gray-100 border-t-[#C8102E] rounded-full animate-spin" />
              <p className="text-xs text-gray-400 font-bold uppercase tracking-widest">Cargando información...</p>
            </div>
          ) : studentGroups.length === 0 ? (
            <div className="py-32 text-center space-y-4">
              <div className="w-20 h-20 bg-gray-50 rounded-full flex items-center justify-center mx-auto border border-gray-100">
                <CheckCircle2 className="w-10 h-10 text-gray-200" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-gray-900 uppercase tracking-widest">No hay registros</h3>
                <p className="text-xs text-gray-400 font-medium">Todo está bajo control en esta categoría.</p>
              </div>
            </div>
          ) : (
            studentGroups.map((group: any) => (
              <div key={group.studentCode} className="group border-b border-gray-50 last:border-0">
                {/* Header: Student Name */}
                <div 
                  onClick={() => toggleStudent(group.studentCode)}
                  className={`px-8 py-5 flex items-center justify-between cursor-pointer transition-all ${expandedStudents[group.studentCode] ? 'bg-gray-50' : 'hover:bg-gray-50/50'}`}
                >
                  <div className="flex items-center gap-5">
                    <div className="w-12 h-12 rounded-2xl bg-white border border-gray-200 shadow-sm flex items-center justify-center text-[#C8102E] font-extrabold text-sm group-hover:scale-105 transition-transform">
                      {group.studentName.split(' ').filter(Boolean).map((n: string) => n[0]).join('').substring(0, 2)}
                    </div>
                    <div>
                      <h3 className="text-sm font-extrabold text-gray-900 group-hover:text-[#C8102E] transition-colors tracking-tight uppercase">
                        {group.studentName}
                      </h3>
                      <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest mt-0.5">{group.studentCode}</p>
                    </div>
                    <Badge variant="gray" size="sm" className="text-[9px] font-extrabold px-2 py-0.5">
                      {group.alerts.length} {group.alerts.length === 1 ? 'ALERTA' : 'ALERTAS'}
                    </Badge>
                  </div>
                  <ChevronRight className={`w-5 h-5 text-gray-300 transition-all duration-300 ${expandedStudents[group.studentCode] ? 'rotate-90 text-[#C8102E]' : 'group-hover:text-gray-400'}`} />
                </div>

                {/* Expanded: Alerts List */}
                {expandedStudents[group.studentCode] && (
                  <div className="px-8 pb-8 pt-2 bg-gray-50/50 space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                    {group.alerts.map((alert: AlertItem) => (
                      <div key={alert.id} className="bg-white p-5 rounded-3xl border border-gray-100 shadow-sm flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6 hover:shadow-md transition-all border-l-4 border-l-[#C8102E]/20">
                        <div className="space-y-2 flex-1">
                          <div className="flex items-center gap-3">
                            <span className="text-sm font-extrabold text-gray-800 uppercase tracking-tight">{alert.alertType}</span>
                            {RISK_CONFIG[alert.riskLevel] && (
                              <Badge variant={RISK_CONFIG[alert.riskLevel].variant} size="xs" className="text-[9px] font-extrabold">
                                {RISK_CONFIG[alert.riskLevel].label}
                              </Badge>
                            )}
                          </div>
                          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] text-gray-400 font-semibold">
                            <div className="flex items-center gap-1.5">
                              <RefreshCw className="w-3 h-3" />
                              <span>Creada: {alert.generatedDate}</span>
                            </div>
                            <span>•</span>
                            <span className="text-[#C8102E] font-bold uppercase tracking-wider">
                              {alert.tipo_regla === 'PROMEDIO' ? `Promedio: ${alert.valor_causa?.toFixed(2)}` : `${Math.round(alert.valor_causa || 0)} ${alert.tipo_regla === 'REPROBACION' ? 'Materias Perdidas' : 'Materias Pendientes'}`}
                            </span>
                          </div>
                          
                          {/* Metadata Badges */}
                          {(alert.metadata?.materias || alert.metadata?.materias_atrasadas) && (
                            <div className="flex flex-wrap gap-1.5 mt-3">
                              {(alert.metadata.materias || alert.metadata.materias_atrasadas).map((m: string, i: number) => (
                                <span key={i} className={`text-[9px] font-extrabold px-2.5 py-1 rounded-lg border tracking-wide uppercase ${alert.tipo_regla === 'REPROBACION' ? 'bg-red-50 text-red-700 border-red-100' : 'bg-amber-50 text-amber-700 border-amber-100'}`}>
                                  {m}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Actions */}
                        <div className="flex flex-wrap items-center gap-2 w-full lg:w-auto pt-4 lg:pt-0 border-t lg:border-0 border-gray-50">
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-9 px-4 text-gray-500 hover:bg-gray-100 rounded-xl flex-1 lg:flex-none"
                            onClick={() => navigate(`/dashboard/students/${alert.studentCode}`)}
                          >
                            <ExternalLink className="w-3.5 h-3.5 mr-2" />
                            <span className="text-[10px] font-extrabold uppercase tracking-widest">Perfil</span>
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-9 px-4 text-gray-500 hover:bg-gray-100 rounded-xl flex-1 lg:flex-none"
                            onClick={() => { setSelectedAlert(alert); setShowHistory(true); }}
                          >
                            <ClipboardList className="w-3.5 h-3.5 mr-2" />
                            <span className="text-[10px] font-extrabold uppercase tracking-widest">Historial</span>
                          </Button>
                          
                          {activeTab !== 'Atendidas' && activeTab !== 'Cerradas' && (
                            <>
                              <Button 
                                size="sm" 
                                className="h-9 px-5 bg-[#C8102E] text-white hover:bg-red-700 shadow-md shadow-red-100 rounded-xl flex-1 lg:flex-none"
                                onClick={() => { setSelectedAlert(alert); setShowModal(true); }}
                              >
                                <span className="text-[10px] font-extrabold uppercase tracking-widest">Intervenir</span>
                              </Button>
                              <Button 
                                variant="outline" 
                                size="sm" 
                                className="h-9 px-3 border-gray-200 text-gray-400 hover:text-red-600 hover:bg-red-50 hover:border-red-100 rounded-xl"
                                onClick={() => { if(window.confirm('¿Seguro que deseas cerrar esta alerta?')) handleCerrarAlerta(alert.id); }}
                              >
                                <X className="w-4 h-4" />
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}