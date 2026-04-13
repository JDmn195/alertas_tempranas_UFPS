import { Link } from 'react-router';
import { AlertTriangle, Users, BookOpen } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

const atRiskStudents = [
  {
    id: '1',
    name: 'María Alejandra Ramírez González',
    course: 'Base de Datos I',
    riskLevel: 'high',
    alertCount: 3,
  },
  {
    id: '2',
    name: 'Carlos Andrés Mendoza Pérez',
    course: 'Programación II',
    riskLevel: 'high',
    alertCount: 5,
  },
  {
    id: '4',
    name: 'Diego Fernando Castillo Ruiz',
    course: 'Estructuras de Datos',
    riskLevel: 'medium',
    alertCount: 2,
  },
  {
    id: '5',
    name: 'Ana María López Martínez',
    course: 'Base de Datos I',
    riskLevel: 'high',
    alertCount: 4,
  },
];

const courses = [
  {
    id: '1',
    name: 'Base de Datos I',
    code: 'BD-101',
    enrollment: 45,
    atRisk: 12,
    atRiskPercentage: 27,
  },
  {
    id: '2',
    name: 'Programación II',
    code: 'PROG-202',
    enrollment: 38,
    atRisk: 8,
    atRiskPercentage: 21,
  },
  {
    id: '3',
    name: 'Estructuras de Datos',
    code: 'ED-301',
    enrollment: 32,
    atRisk: 5,
    atRiskPercentage: 16,
  },
];

export default function TeacherDashboard() {
  return (
    <div className="space-y-6">
      {/* Welcome banner */}
      <div className="bg-[#C8102E] text-white rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold mb-2">Bienvenido, Prof. Juan Pérez</h1>
            <p className="text-sm opacity-90">
              Departamento de Ingeniería de Sistemas · Período Académico 2026-1
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm opacity-90 mb-1">Último acceso</p>
            <p className="font-semibold">7 de Abril, 2026 - 3:45 PM</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* My students at risk */}
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-[#C8102E]" />
              <h2 className="text-lg font-semibold text-gray-900">Mis Estudiantes en Riesgo</h2>
            </div>
            <Badge variant="error" size="sm">
              {atRiskStudents.length} Activos
            </Badge>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[#C8102E] text-white">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                    Nombre del Estudiante
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                    Curso
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                    Riesgo
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                    Alertas
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {atRiskStudents.map((student, index) => (
                  <tr
                    key={student.id}
                    className={index % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5]'}
                  >
                    <td className="px-6 py-4 text-sm text-gray-900">{student.name}</td>
                    <td className="px-6 py-4 text-sm text-gray-900">{student.course}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {student.riskLevel === 'high' && <Badge variant="high">ALTO</Badge>}
                      {student.riskLevel === 'medium' && <Badge variant="medium">MEDIO</Badge>}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#C8102E] text-white text-xs font-bold">
                        {student.alertCount}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="border-t border-gray-200 px-6 py-4 bg-gray-50">
            <Link to="/dashboard/students">
              <Button variant="outline" size="sm" fullWidth>
                Ver Todos los Estudiantes
              </Button>
            </Link>
          </div>
        </div>

        {/* My courses */}
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="border-b border-gray-200 px-6 py-4 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-[#C8102E]" />
            <h2 className="text-lg font-semibold text-gray-900">Mis Cursos</h2>
          </div>

          <div className="p-6 space-y-6">
            {courses.map((course) => (
              <div
                key={course.id}
                className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-gray-900">{course.name}</h3>
                    <p className="text-sm text-gray-500">{course.code}</p>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Users className="w-4 h-4 text-gray-400" />
                    <span className="font-medium text-gray-900">{course.enrollment}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Estudiantes en riesgo</span>
                    <span className="font-semibold text-[#C8102E]">
                      {course.atRisk} ({course.atRiskPercentage}%)
                    </span>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                    <div
                      className="bg-[#C8102E] h-2.5 rounded-full transition-all"
                      style={{ width: `${course.atRiskPercentage}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-gray-200 px-6 py-4 bg-gray-50">
            <Button variant="outline" size="sm" fullWidth>
              Ver Detalles del Curso
            </Button>
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Acciones Rápidas</h2>
        <div className="grid grid-cols-4 gap-4">
          <Button variant="outline">
            Registrar Intervención
          </Button>
          <Link to="/dashboard/alerts">
            <Button variant="outline" fullWidth>
              Ver Todas las Alertas
            </Button>
          </Link>
          <Link to="/dashboard/reports">
            <Button variant="outline" fullWidth>
              Generar Reporte
            </Button>
          </Link>
          <Button variant="primary">
            Programar Reunión
          </Button>
        </div>
      </div>
    </div>
  );
}
