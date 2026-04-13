import { useState } from 'react';
import { Plus, Settings, X } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

const riskRules = [
  {
    id: '1',
    name: 'Bajo Promedio - Crítico',
    condition: 'Promedio < 3.0',
    severity: 'high',
    active: true,
  },
  {
    id: '2',
    name: 'Bajo Promedio - Advertencia',
    condition: 'Promedio < 3.5',
    severity: 'medium',
    active: true,
  },
  {
    id: '3',
    name: 'Múltiples Cursos Reprobados',
    condition: 'Cursos reprobados >= 2 en el mismo semestre',
    severity: 'high',
    active: true,
  },
  {
    id: '4',
    name: 'Un Curso Reprobado',
    condition: 'Cursos reprobados = 1 en el semestre',
    severity: 'medium',
    active: true,
  },
  {
    id: '5',
    name: 'Baja Tasa de Asistencia',
    condition: 'Asistencia < 75%',
    severity: 'medium',
    active: true,
  },
  {
    id: '6',
    name: 'Tendencia Decreciente de Promedio',
    condition: 'Caída de promedio > 0.5 en 2 semestres',
    severity: 'high',
    active: false,
  },
];

export default function RiskRules() {
  const [showModal, setShowModal] = useState(false);
  const [newRule, setNewRule] = useState({
    name: '',
    conditionType: 'gpa',
    threshold: '',
    severity: 'medium',
    roles: [] as string[],
  });

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
        <Button onClick={() => setShowModal(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Añadir Regla
        </Button>
      </div>

      {/* Rules list */}
      <div className="space-y-4">
        {riskRules.map((rule) => (
          <div
            key={rule.id}
            className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-lg font-semibold text-gray-900">{rule.name}</h3>
                  {rule.severity === 'high' && <Badge variant="high">Severidad Alta</Badge>}
                  {rule.severity === 'medium' && <Badge variant="medium">Severidad Media</Badge>}
                  {rule.severity === 'low' && <Badge variant="low">Severidad Baja</Badge>}
                </div>
                <p className="text-sm text-gray-600">
                  <span className="font-medium">Condición:</span>{' '}
                  <code className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                    {rule.condition}
                  </code>
                </p>
              </div>

              <div className="flex items-center gap-3">
                {/* Active toggle */}
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={rule.active}
                    className="sr-only peer"
                    readOnly
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-red-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#C8102E]"></div>
                  <span className="ml-3 text-sm font-medium text-gray-700">
                    {rule.active ? 'Activa' : 'Inactiva'}
                  </span>
                </label>

                <Button variant="outline" size="sm">
                  <Settings className="w-4 h-4 mr-2" />
                  Editar
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Add Rule Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-6">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal header */}
            <div className="bg-[#C8102E] text-white px-6 py-4 flex items-center justify-between sticky top-0">
              <h2 className="text-xl font-bold">Añadir Nueva Regla de Riesgo</h2>
              <button
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
                  value={newRule.name}
                  onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                  placeholder="e.g., Low GPA - Critical"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Tipo de Condición
                </label>
                <select
                  value={newRule.conditionType}
                  onChange={(e) => setNewRule({ ...newRule, conditionType: e.target.value })}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                >
                  <option value="gpa">Límite de Promedio</option>
                  <option value="failed_courses">Cantidad de Cursos Reprobados</option>
                  <option value="attendance">Tasa de Asistencia</option>
                  <option value="gpa_trend">Tendencia de Promedio</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Valor Límite
                </label>
                <input
                  type="text"
                  value={newRule.threshold}
                  onChange={(e) => setNewRule({ ...newRule, threshold: e.target.value })}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
                  placeholder="e.g., 3.0"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Nivel de Severidad
                </label>
                <div className="flex gap-3">
                  <button
                    onClick={() => setNewRule({ ...newRule, severity: 'low' })}
                    className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all ${
                      newRule.severity === 'low'
                        ? 'border-gray-400 bg-gray-50'
                        : 'border-gray-200 bg-white'
                    }`}
                  >
                    <Badge variant="low">Baja</Badge>
                  </button>
                  <button
                    onClick={() => setNewRule({ ...newRule, severity: 'medium' })}
                    className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all ${
                      newRule.severity === 'medium'
                        ? 'border-amber-400 bg-amber-50'
                        : 'border-gray-200 bg-white'
                    }`}
                  >
                    <Badge variant="medium">Media</Badge>
                  </button>
                  <button
                    onClick={() => setNewRule({ ...newRule, severity: 'high' })}
                    className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all ${
                      newRule.severity === 'high'
                        ? 'border-[#C8102E] bg-red-50'
                        : 'border-gray-200 bg-white'
                    }`}
                  >
                    <Badge variant="high">Alta</Badge>
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Roles a Notificar
                </label>
                <div className="space-y-2">
                  {['Director Académico', 'Docente', 'Tutor', 'Personal de Bienestar'].map((role) => (
                    <label key={role} className="flex items-center">
                      <input
                        type="checkbox"
                        className="w-4 h-4 text-[#C8102E] border-gray-300 rounded focus:ring-[#C8102E]"
                      />
                      <span className="ml-2 text-sm text-gray-700">{role}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            {/* Modal footer */}
            <div className="border-t border-gray-200 px-6 py-4 flex items-center justify-end gap-3">
              <Button variant="secondary" onClick={() => setShowModal(false)}>
                Cancelar
              </Button>
              <Button onClick={() => setShowModal(false)}>
                Guardar Regla
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
