import { useState, useEffect } from 'react';
import { Plus, Settings, X, Trash2, AlertTriangle, Play, CheckCircle, CalendarX } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { ruleService, Rule } from '../../services/ruleService';

const CORTE_CLAVE_LABEL: Record<string, string> = {
  C1: 'Corte 1 — Alerta temprana',
  C2A: 'Corte 2 — Sostenido bajo',
  C2B: 'Corte 2 — Bajo con Corte 1 bajo',
  C3: 'Corte 3 — Nota necesaria moderada',
  C4: 'Corte 3 — Nota necesaria crítica',
};

const EVALUA_LABEL: Record<string, string> = {
  CORTE: 'Nota del corte',
  NOTA_NECESARIA: 'Nota necesaria en examen final',
};

export default function RiskRules() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [errorModal, setErrorModal] = useState<{ show: boolean; message: string }>({ show: false, message: '' });
  const [evaluandoCortes, setEvaluandoCortes] = useState(false);
  const [evaluacionOk, setEvaluacionOk] = useState(false);
  const [errorInasistencia, setErrorInasistencia] = useState<string | null>(null);

  // Obtener usuario de la sesión real (localStorage)
  const getSessionUser = () => {
    const savedUser = localStorage.getItem('user');
    return savedUser ? JSON.parse(savedUser) : null;
  };

  const currentUser = getSessionUser();
  const usuarioId = currentUser?.id;

  const [formData, setFormData] = useState<Rule>({
    nombre: '',
    tipo: 'PROMEDIO',
    valor_umbral: 3.0,
    operador: '<',
    nivel: 'medium',
    activo: true,
    descripcion: '',
  });

  useEffect(() => {
    loadRules();
  }, []);

  const loadRules = async () => {
    try {
      const data = await ruleService.getRules();
      setRules(data);
    } catch (error) {
      console.error('Error loading rules:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (rule: Rule) => {
    if (!rule.id) return;
    if (!usuarioId) {
      alert('Debes iniciar sesión para realizar esta acción');
      return;
    }
    try {
      await ruleService.updateRule(rule.id, { activo: !rule.activo });
      loadRules();
    } catch (error) {
      alert('Error al cambiar estado de la regla');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('¿Estás seguro de eliminar esta regla?')) return;
    if (!usuarioId) {
      alert('Debes iniciar sesión para realizar esta acción');
      return;
    }
    try {
      await ruleService.deleteRule(id);
      loadRules();
    } catch (error: any) {
      const msg = error.message || '';
      if (msg === 'protected_error' || msg.includes('protected') || msg.includes('referenced')) {
        setErrorModal({
          show: true,
          message: 'No se puede eliminar esta regla porque existen alertas académicas asociadas a ella. Se recomienda desactivarla en su lugar para conservar el historial.'
        });
      } else {
        alert('Error al eliminar la regla: ' + msg);
      }
    }
  };

  const handleUpdateUmbral = async (rule: Rule) => {
    if (!rule.id) return;
    try {
      await ruleService.updateRule(rule.id, {
        valor_umbral: rule.valor_umbral,
        parametros: rule.parametros,
      });
      loadRules();
    } catch (error: any) {
      alert(error.message || 'Error al actualizar el umbral');
    }
  };

  // HU-35: el backend valida el rango y que haya una sola regla INASISTENCIA activa
  const handleToggleInasistencia = async (rule: Rule) => {
    if (!rule.id) return;
    setErrorInasistencia(null);
    try {
      await ruleService.updateRule(rule.id, { activo: !rule.activo });
      loadRules();
    } catch (error: any) {
      setErrorInasistencia(error.message || 'Error al cambiar el estado de la regla');
    }
  };

  const handleSaveInasistencia = async (rule: Rule, valorUmbral: number, minClases: number) => {
    if (!rule.id) return false;
    setErrorInasistencia(null);
    try {
      await ruleService.updateRule(rule.id, {
        valor_umbral: valorUmbral,
        parametros: { ...(rule.parametros || {}), min_clases: minClases },
      });
      loadRules();
      return true;
    } catch (error: any) {
      setErrorInasistencia(error.message || 'Error al actualizar el umbral de inasistencia');
      return false;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usuarioId) {
      alert('Debes iniciar sesión para realizar esta acción');
      return;
    }
    try {
      if (editingId) {
        await ruleService.updateRule(editingId, formData);
      } else {
        await ruleService.createRule(formData);
      }
      setShowModal(false);
      resetForm();
      loadRules();
    } catch (error: any) {
      alert(error.message || 'Error al guardar la regla');
    }
  };

  const handleEvaluarCortes = async () => {
    setEvaluandoCortes(true);
    setEvaluacionOk(false);
    try {
      await ruleService.evaluarCortes();
      setEvaluacionOk(true);
      setTimeout(() => setEvaluacionOk(false), 4000);
    } catch (error: any) {
      alert(error.message || 'Error al evaluar alertas por corte');
    } finally {
      setEvaluandoCortes(false);
    }
  };

  const resetForm = () => {
    setFormData({
      nombre: '',
      tipo: 'PROMEDIO',
      valor_umbral: 3.0,
      operador: '<',
      nivel: 'medium',
      activo: true,
      descripcion: '',
    });
    setEditingId(null);
  };

  const openEdit = (rule: Rule) => {
    setFormData({
      nombre: rule.nombre,
      tipo: rule.tipo,
      valor_umbral: rule.valor_umbral,
      operador: rule.operador,
      nivel: rule.nivel,
      activo: rule.activo,
      descripcion: rule.descripcion || '',
      parametros: rule.parametros,
    });
    setEditingId(rule.id || null);
    setShowModal(true);
  };

  const rulesGeneral = rules.filter(r => r.tipo !== 'CORTE' && r.tipo !== 'INASISTENCIA');
  const rulesCorte = rules.filter(r => r.tipo === 'CORTE');
  const rulesInasistencia = rules.filter(r => r.tipo === 'INASISTENCIA');

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="border-l-4 border-[#C8102E] pl-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Configuración de Reglas de Riesgo</h1>
          <p className="text-sm text-gray-600 mt-1">
            Definir y gestionar reglas para la detección de riesgo estudiantil
          </p>
        </div>
        <Button onClick={() => { resetForm(); setShowModal(true); }}>
          <Plus className="w-4 h-4 mr-2" />
          Añadir Regla
        </Button>
      </div>

      {/* ── SECCIÓN HU-32: Alertas por Corte ── */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            <div>
              <h2 className="text-lg font-semibold text-gray-800">Alertas Tempranas por Corte</h2>
              <p className="text-xs text-gray-500">
                Reglas automáticas administradas por el sistema. Solo se puede editar el umbral y el estado.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {evaluacionOk && (
              <span className="flex items-center gap-1 text-green-600 text-sm font-medium">
                <CheckCircle className="w-4 h-4" /> Evaluación iniciada
              </span>
            )}
            <Button
              variant="outline"
              onClick={handleEvaluarCortes}
              disabled={evaluandoCortes}
              id="btn-evaluar-cortes"
            >
              <Play className="w-4 h-4 mr-2" />
              {evaluandoCortes ? 'Evaluando…' : 'Evaluar ahora'}
            </Button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-8 text-gray-500">Cargando reglas de corte…</div>
        ) : rulesCorte.length === 0 ? (
          <div className="text-center py-8 bg-amber-50 rounded-lg border border-dashed border-amber-300 text-amber-700 text-sm">
            No hay reglas de corte configuradas.
          </div>
        ) : (
          <div className="grid gap-3">
            {rulesCorte.map((rule) => {
              const params = rule.parametros || {};
              const clave = params.clave || '—';
              const evalua = params.evalua ? EVALUA_LABEL[params.evalua] || params.evalua : '—';
              const corteLabel = params.corte ? `Corte ${params.corte}` : null;
              const previoLabel = params.corte_previo
                ? `si Corte ${params.corte_previo} ${params.operador_previo} ${params.umbral_previo}`
                : null;
              return (
                <div
                  key={rule.id}
                  className={`bg-white rounded-lg border border-amber-200 p-5 hover:shadow-sm transition-shadow ${!rule.activo ? 'opacity-60' : ''}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-xs font-mono font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded">
                          {clave}
                        </span>
                        <h3 className="text-base font-semibold text-gray-900 truncate">
                          {CORTE_CLAVE_LABEL[clave] || rule.nombre}
                        </h3>
                        <Badge variant={rule.nivel}>
                          {rule.nivel === 'high' ? 'Alta' : rule.nivel === 'medium' ? 'Media' : 'Baja'}
                        </Badge>
                      </div>
                      <p className="text-xs text-gray-600 mb-1">
                        <span className="font-medium">Evalúa:</span> {evalua}
                        {corteLabel && <span className="ml-2 text-gray-400">— {corteLabel}</span>}
                        {previoLabel && <span className="ml-2 text-gray-400">({previoLabel})</span>}
                      </p>
                      <p className="text-xs text-gray-500 italic">{rule.descripcion}</p>
                    </div>

                    {/* Umbral editable */}
                    <div className="flex flex-col items-end gap-3 shrink-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500 font-medium">Umbral:</span>
                        <UmbralInline rule={rule} onSave={handleUpdateUmbral} />
                      </div>
                      {/* Toggle activo */}
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={rule.activo}
                          onChange={() => handleToggleActive(rule)}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500"></div>
                        <span className="ml-2 text-xs font-medium text-gray-600">
                          {rule.activo ? 'Activa' : 'Inactiva'}
                        </span>
                      </label>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* ── SECCIÓN HU-35: Umbral general de inasistencia ── */}
      <section className="space-y-4">
        <div className="flex items-center gap-3">
          <CalendarX className="w-5 h-5 text-[#C8102E]" />
          <div>
            <h2 className="text-lg font-semibold text-gray-800">Umbral de Inasistencia</h2>
            <p className="text-xs text-gray-500">
              Porcentaje máximo de faltas sin justificar permitido en un curso. Cada curso puede tener su propio umbral desde la lista de cursos; si no lo tiene, se usa este valor general.
            </p>
          </div>
        </div>

        {errorInasistencia && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3" role="alert">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span className="flex-1">{errorInasistencia}</span>
            <button type="button" onClick={() => setErrorInasistencia(null)} className="text-red-500 hover:text-red-700">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {loading ? (
          <div className="text-center py-8 text-gray-500">Cargando umbral de inasistencia…</div>
        ) : rulesInasistencia.length === 0 ? (
          <div className="text-center py-8 bg-gray-50 rounded-lg border border-dashed border-gray-300 text-gray-600 text-sm">
            No hay una regla de inasistencia configurada. Créala con "Añadir Regla" y la métrica "Porcentaje de Inasistencia".
          </div>
        ) : (
          <div className="grid gap-3">
            {rulesInasistencia.map((rule) => (
              <InasistenciaRuleCard
                key={`${rule.id}-${rule.valor_umbral}-${rule.parametros?.min_clases}`}
                rule={rule}
                onSave={handleSaveInasistencia}
                onToggle={handleToggleInasistencia}
              />
            ))}
          </div>
        )}
      </section>

      {/* ── Reglas Generales ── */}
      <section className="space-y-4">
        <div className="flex items-center gap-3">
          <Settings className="w-5 h-5 text-gray-500" />
          <h2 className="text-lg font-semibold text-gray-800">Reglas de Riesgo General</h2>
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-500">Cargando reglas…</div>
        ) : rulesGeneral.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg border border-dashed border-gray-300 text-gray-500">
            No hay reglas configuradas. Haz clic en "Añadir Regla" para empezar.
          </div>
        ) : (
          rulesGeneral.map((rule) => (
            <div
              key={rule.id}
              className={`bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition-shadow ${!rule.activo ? 'opacity-60' : ''}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-lg font-semibold text-gray-900">{rule.nombre}</h3>
                    <Badge variant={rule.nivel}>{rule.nivel === 'high' ? 'Severidad Alta' : rule.nivel === 'medium' ? 'Severidad Media' : 'Severidad Baja'}</Badge>
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                      {rule.tipo_display || rule.tipo}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">
                    <span className="font-medium">Condición:</span>{' '}
                    <code className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                      {rule.tipo} {rule.operador} {rule.valor_umbral}
                    </code>
                  </p>
                  {rule.descripcion && (
                    <p className="text-xs text-gray-500 italic">{rule.descripcion}</p>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  {/* Active toggle */}
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={rule.activo}
                      onChange={() => handleToggleActive(rule)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-red-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#C8102E]"></div>
                    <span className="ml-3 text-sm font-medium text-gray-700">
                      {rule.activo ? 'Activa' : 'Inactiva'}
                    </span>
                  </label>

                  <Button variant="outline" size="sm" onClick={() => openEdit(rule)}>
                    <Settings className="w-4 h-4 mr-2" />
                    Editar
                  </Button>
                  
                  <Button variant="outline" size="sm" className="text-red-600 hover:bg-red-50 border-red-200" onClick={() => { if(rule.id) handleDelete(rule.id); }}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          ))
        )}
      </section>

      {/* Add/Edit Rule Modal */}
      {showModal && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-20 flex items-center justify-center z-50 p-6"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.2)' }}
        >
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <form onSubmit={handleSubmit}>
              {/* Modal header */}
              <div className="bg-[#C8102E] text-white px-6 py-4 flex items-center justify-between sticky top-0">
                <h2 className="text-xl font-bold">{editingId ? 'Editar Regla' : 'Añadir Nueva Regla'}</h2>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg p-1"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              {/* Modal content */}
              <div className="p-6 space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Nombre de la Regla
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.nombre}
                    onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                    placeholder="e.g., Bajo Promedio - Crítico"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Métrica a Evaluar
                    </label>
                    <select
                      value={formData.tipo}
                      onChange={(e) => {
                        const tipo = e.target.value as Rule['tipo'];
                        setFormData(tipo === 'INASISTENCIA'
                          ? { ...formData, tipo, operador: '>', valor_umbral: 20, parametros: { min_clases: 4 } }
                          : { ...formData, tipo, parametros: undefined });
                      }}
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                    >
                      <option value="PROMEDIO">Promedio Acumulado</option>
                      <option value="REPROBACION">Materias Reprobadas</option>
                      <option value="ATRASO">Atraso Curricular</option>
                      <option value="INASISTENCIA">Porcentaje de Inasistencia</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Operador
                    </label>
                    <select
                      value={formData.operador}
                      onChange={(e) => setFormData({ ...formData, operador: e.target.value as any })}
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                    >
                      <option value="<">Menor que</option>
                      <option value=">">Mayor que</option>
                      <option value="<=">Menor o igual que</option>
                      <option value=">=">Mayor o igual que</option>
                      <option value="==">Igual a</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Valor Umbral
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formData.valor_umbral}
                    onChange={(e) => setFormData({ ...formData, valor_umbral: parseFloat(e.target.value) })}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                    placeholder="e.g., 3.0"
                  />
                  {formData.tipo === 'INASISTENCIA' && (
                    <p className="text-xs text-gray-500 mt-1">Porcentaje entre 0 y 100.</p>
                  )}
                </div>

                {formData.tipo === 'INASISTENCIA' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Mínimo de clases registradas
                    </label>
                    <input
                      type="number"
                      step="1"
                      min="1"
                      max="50"
                      required
                      value={formData.parametros?.min_clases ?? ''}
                      onChange={(e) => setFormData({
                        ...formData,
                        parametros: { ...(formData.parametros || {}), min_clases: parseInt(e.target.value, 10) },
                      })}
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Clases que deben estar registradas antes de evaluar a un estudiante (entre 1 y 50).
                    </p>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Nivel de Severidad
                  </label>
                  <div className="flex gap-3">
                    {['low', 'medium', 'high'].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setFormData({ ...formData, nivel: n as any })}
                        className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all flex items-center justify-center ${
                          formData.nivel === n
                            ? n === 'high' ? 'border-[#C8102E] bg-red-50' : n === 'medium' ? 'border-amber-400 bg-amber-50' : 'border-gray-400 bg-gray-50'
                            : 'border-gray-200 bg-white'
                        }`}
                      >
                        <Badge variant={n as any}>{n === 'high' ? 'Alta' : n === 'medium' ? 'Media' : 'Baja'}</Badge>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Descripción (Opcional)
                  </label>
                  <textarea
                    value={formData.descripcion}
                    onChange={(e) => setFormData({ ...formData, descripcion: e.target.value })}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                    rows={3}
                    placeholder="Explica el motivo de esta regla..."
                  />
                </div>
              </div>

              {/* Modal footer */}
              <div className="border-t border-gray-200 px-6 py-4 flex items-center justify-end gap-3">
                <Button variant="secondary" type="button" onClick={() => setShowModal(false)}>
                  Cancelar
                </Button>
                <Button type="submit">
                  {editingId ? 'Actualizar Regla' : 'Guardar Regla'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Error Modal */}
      {errorModal.show && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-20 flex items-center justify-center z-[60] p-6"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.2)' }}
        >
          <div className="bg-white rounded-lg max-w-md w-full shadow-2xl">
            <div className="p-6">
              <div className="flex items-center gap-4 text-amber-600 mb-4">
                <div className="w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center">
                  <Settings className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold text-gray-900">Acción Protegida</h3>
              </div>
              <p className="text-gray-600 leading-relaxed">
                {errorModal.message}
              </p>
            </div>
            <div className="bg-gray-50 px-6 py-4 rounded-b-lg flex justify-end">
              <Button onClick={() => setErrorModal({ show: false, message: '' })}>
                Entendido
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Componente inline para editar umbral de una regla CORTE ──
function UmbralInline({ rule, onSave }: { rule: Rule; onSave: (r: Rule) => void }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(rule.valor_umbral);

  const handleSave = () => {
    onSave({ ...rule, valor_umbral: val });
    setEditing(false);
  };

  if (!editing) {
    return (
      <button
        className="text-sm font-mono font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-0.5 hover:bg-amber-100 transition-colors"
        title="Haz clic para editar el umbral"
        onClick={() => setEditing(true)}
      >
        {rule.operador} {val}
      </button>
    );
  }

  return (
    <span className="flex items-center gap-1">
      <span className="text-xs text-gray-500">{rule.operador}</span>
      <input
        type="number"
        step="0.1"
        min="0"
        max="5"
        value={val}
        autoFocus
        onChange={(e) => setVal(parseFloat(e.target.value))}
        className="w-16 text-sm border border-amber-400 rounded px-1 py-0.5 focus:outline-none focus:ring-1 focus:ring-amber-400"
      />
      <button
        onClick={handleSave}
        className="text-xs bg-amber-500 text-white px-2 py-0.5 rounded hover:bg-amber-600"
      >
        ✓
      </button>
      <button
        onClick={() => { setVal(rule.valor_umbral); setEditing(false); }}
        className="text-xs text-gray-500 hover:text-gray-700"
      >
        ✕
      </button>
    </span>
  );
}

// ── HU-35: tarjeta de la regla INASISTENCIA (umbral general y mínimo de clases) ──
function InasistenciaRuleCard({ rule, onSave, onToggle }: {
  rule: Rule;
  onSave: (r: Rule, valorUmbral: number, minClases: number) => Promise<boolean>;
  onToggle: (r: Rule) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [umbral, setUmbral] = useState(String(rule.valor_umbral));
  const [minClases, setMinClases] = useState(String(rule.parametros?.min_clases ?? ''));
  const [saving, setSaving] = useState(false);

  const cancelar = () => {
    setUmbral(String(rule.valor_umbral));
    setMinClases(String(rule.parametros?.min_clases ?? ''));
    setEditing(false);
  };

  const guardar = async () => {
    setSaving(true);
    // Se envía tal cual: el backend responde 400 con el mensaje si el valor no es válido
    const ok = await onSave(rule, Number(umbral), Number(minClases));
    setSaving(false);
    if (ok) setEditing(false);
  };

  return (
    <div className={`bg-white rounded-lg border border-red-200 p-5 ${!rule.activo ? 'opacity-60' : ''}`}>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h3 className="text-base font-semibold text-gray-900">{rule.nombre}</h3>
            <Badge variant={rule.nivel}>
              {rule.nivel === 'high' ? 'Alta' : rule.nivel === 'medium' ? 'Media' : 'Baja'}
            </Badge>
          </div>
          {rule.descripcion && <p className="text-xs text-gray-500 italic">{rule.descripcion}</p>}
        </div>

        <label className="relative inline-flex items-center cursor-pointer shrink-0">
          <input
            type="checkbox"
            checked={rule.activo}
            onChange={() => onToggle(rule)}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#C8102E]"></div>
          <span className="ml-2 text-xs font-medium text-gray-600">
            {rule.activo ? 'Activa' : 'Inactiva'}
          </span>
        </label>
      </div>

      <div className="mt-4 flex items-end gap-6 flex-wrap">
        {editing ? (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Umbral general (%)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={umbral}
                autoFocus
                onChange={(e) => setUmbral(e.target.value)}
                className="w-28 text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[#C8102E]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Mínimo de clases</label>
              <input
                type="number"
                step="1"
                min="1"
                max="50"
                value={minClases}
                onChange={(e) => setMinClases(e.target.value)}
                className="w-24 text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[#C8102E]"
              />
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={guardar} disabled={saving}>
                {saving ? 'Guardando…' : 'Guardar'}
              </Button>
              <Button size="sm" variant="secondary" onClick={cancelar} disabled={saving}>
                Cancelar
              </Button>
            </div>
          </>
        ) : (
          <>
            <div>
              <p className="text-xs text-gray-500">Umbral general</p>
              <p className="text-lg font-semibold text-gray-900">{rule.operador} {rule.valor_umbral}%</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Mínimo de clases</p>
              <p className="text-lg font-semibold text-gray-900">{rule.parametros?.min_clases ?? '—'}</p>
            </div>
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              <Settings className="w-4 h-4 mr-2" />
              Editar
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
