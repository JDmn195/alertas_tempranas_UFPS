import { useState } from 'react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

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

export default function AlertManagement() {
  const [activeTab, setActiveTab] = useState('Activas');

  const filteredAlerts = alerts.filter((alert) => {
    if (activeTab === 'Activas') return alert.status === 'active';
    if (activeTab === 'En Seguimiento') return alert.status === 'monitoring';
    return false;
  });

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="border-l-4 border-[#C8102E] pl-4">
        <h1 className="text-2xl font-bold text-gray-900">Gestión de Alertas</h1>
        <p className="text-sm text-gray-600 mt-1">
          Monitorear y gestionar alertas de riesgo de estudiantes en todos los programas
        </p>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200">
          <div className="flex">
            {tabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-6 py-4 text-sm font-medium transition-colors relative ${
                  activeTab === tab
                    ? 'text-[#C8102E]'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab}
                {activeTab === tab && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#C8102E]" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Alerts table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#C8102E] text-white">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Estudiante
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Código
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Nivel de Riesgo
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Tipo de Alerta
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Fecha de Generación
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Docente Asignado
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Estado
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredAlerts.length > 0 ? (
                filteredAlerts.map((alert, index) => (
                  <tr
                    key={alert.id}
                    className={index % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5]'}
                  >
                    <td className="px-6 py-4 text-sm text-gray-900">{alert.studentName}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {alert.studentCode}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {alert.riskLevel === 'high' && <Badge variant="high">ALTO</Badge>}
                      {alert.riskLevel === 'medium' && <Badge variant="medium">MEDIO</Badge>}
                      {alert.riskLevel === 'low' && <Badge variant="low">BAJO</Badge>}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{alert.alertType}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {alert.generatedDate}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {alert.assignedTeacher}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {alert.status === 'active' && (
                        <Badge variant="error" size="sm">
                          Activa
                        </Badge>
                      )}
                      {alert.status === 'monitoring' && (
                        <Badge variant="gray" size="sm">
                          En seguimiento
                        </Badge>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm">
                          Ver
                        </Button>
                        <Button variant="primary" size="sm">
                          Registrar Intervención
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
                        <svg
                          className="w-8 h-8 text-[#C8102E]"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                          />
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
            <p className="text-sm text-gray-600">
              Mostrando {filteredAlerts.length} alertas
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
