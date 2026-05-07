import { useState, useEffect } from 'react';
import { Plus, Settings, X, Trash2 } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { ruleService, Rule } from '../../services/ruleService';

export default function RiskRules() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [errorModal, setErrorModal] = useState<{ show: boolean; message: string }>({ show: false, message: '' });
  
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
      await ruleService.updateRule(rule.id, { activo: !rule.activo }, usuarioId);
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usuarioId) {
      alert('Debes iniciar sesión para realizar esta acción');
      return;
    }
    try {
      if (editingId) {
        await ruleService.updateRule(editingId, formData, usuarioId);
      } else {
        await ruleService.createRule(formData, usuarioId);
      }
      setShowModal(false);
      resetForm();
      loadRules();
    } catch (error: any) {
      alert(error.message || 'Error al guardar la regla');
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
    });
    setEditingId(rule.id || null);
    setShowModal(true);
  };

  return (
    <div className="space-y-6">
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

      {/* Rules list */}
      <div className="space-y-4">
        {loading ? (
          <div className="text-center py-12 text-gray-500">Cargando reglas...</div>
        ) : rules.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg border border-dashed border-gray-300 text-gray-500">
            No hay reglas configuradas. Haz clic en "Añadir Regla" para empezar.
          </div>
        ) : (
          rules.map((rule) => (
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
      </div>

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
                      onChange={(e) => setFormData({ ...formData, tipo: e.target.value as any })}
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                    >
                      <option value="PROMEDIO">Promedio Acumulado</option>
                      <option value="REPROBACION">Materias Reprobadas</option>
                      <option value="ATRASO">Atraso Curricular</option>
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
                </div>

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
