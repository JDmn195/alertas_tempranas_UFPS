import { useState } from 'react';
import { Link } from 'react-router';
import { Search, Filter } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

const students = [
  {
    id: '1',
    code: '1151234',
    name: 'María Alejandra Ramírez González',
    semester: 5,
    gpa: 3.2,
    riskLevel: 'high',
    alerts: 3,
  },
  {
    id: '2',
    code: '1151567',
    name: 'Carlos Andrés Mendoza Pérez',
    semester: 3,
    gpa: 2.8,
    riskLevel: 'high',
    alerts: 5,
  },
  {
    id: '3',
    code: '1151890',
    name: 'Laura Valentina Torres Silva',
    semester: 7,
    gpa: 4.1,
    riskLevel: 'low',
    alerts: 0,
  },
  {
    id: '4',
    code: '1152134',
    name: 'Diego Fernando Castillo Ruiz',
    semester: 4,
    gpa: 3.5,
    riskLevel: 'medium',
    alerts: 2,
  },
  {
    id: '5',
    code: '1152456',
    name: 'Ana María López Martínez',
    semester: 6,
    gpa: 2.9,
    riskLevel: 'high',
    alerts: 4,
  },
  {
    id: '6',
    code: '1152789',
    name: 'Juan Pablo Hernández García',
    semester: 2,
    gpa: 3.8,
    riskLevel: 'low',
    alerts: 0,
  },
  {
    id: '7',
    code: '1153012',
    name: 'Isabella Sofía Rodríguez Cruz',
    semester: 5,
    gpa: 3.4,
    riskLevel: 'medium',
    alerts: 1,
  },
  {
    id: '8',
    code: '1153345',
    name: 'Sebastián Camilo Gómez Díaz',
    semester: 8,
    gpa: 4.3,
    riskLevel: 'low',
    alerts: 0,
  },
  {
    id: '9',
    code: '1153678',
    name: 'Valentina Andrea Morales Vargas',
    semester: 3,
    gpa: 2.7,
    riskLevel: 'high',
    alerts: 6,
  },
  {
    id: '10',
    code: '1153901',
    name: 'Miguel Ángel Sánchez Ortiz',
    semester: 4,
    gpa: 3.6,
    riskLevel: 'medium',
    alerts: 1,
  },
];

export default function StudentList() {
  const [searchTerm, setSearchTerm] = useState('');
  const [semesterFilter, setSemesterFilter] = useState('all');
  const [riskFilter, setRiskFilter] = useState('all');

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="border-l-4 border-[#C8102E] pl-4">
        <h1 className="text-2xl font-bold text-gray-900">Directorio de Estudiantes</h1>
        <p className="text-sm text-gray-600 mt-1">
          Ver y filtrar registros de estudiantes en todos los programas
        </p>
      </div>

      {/* Search and filters */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-4">
          {/* Search bar */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar por nombre o código de estudiante..."
              className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
            />
          </div>

          {/* Semester filter */}
          <select
            value={semesterFilter}
            onChange={(e) => setSemesterFilter(e.target.value)}
            className="px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent bg-white"
          >
            <option value="all">Todos los Semestres</option>
            <option value="1">Semestre 1</option>
            <option value="2">Semestre 2</option>
            <option value="3">Semestre 3</option>
            <option value="4">Semestre 4</option>
            <option value="5">Semestre 5</option>
            <option value="6">Semestre 6+</option>
          </select>

          {/* Risk level filter */}
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent bg-white"
          >
            <option value="all">Todos los Niveles</option>
            <option value="high">Riesgo Alto</option>
            <option value="medium">Riesgo Medio</option>
            <option value="low">Riesgo Bajo</option>
          </select>

          <Button variant="outline">
            <Filter className="w-4 h-4 mr-2" />
            Más Filtros
          </Button>
        </div>
      </div>

      {/* Student table */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Estudiantes ({students.length})
          </h2>
          <Button variant="outline" size="sm">
            Exportar a Excel
          </Button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#C8102E] text-white">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Código
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Nombre
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Semestre
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Promedio
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Nivel de Riesgo
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Alertas Activas
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {students.map((student, index) => (
                <tr
                  key={student.id}
                  className={`${
                    index % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5]'
                  } ${student.riskLevel === 'high' ? 'bg-[#FDECEA]' : ''}`}
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {student.code}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">{student.name}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {student.semester}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                    {student.gpa.toFixed(1)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {student.riskLevel === 'high' && <Badge variant="high">ALTO</Badge>}
                    {student.riskLevel === 'medium' && <Badge variant="medium">MEDIO</Badge>}
                    {student.riskLevel === 'low' && <Badge variant="low">BAJO</Badge>}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {student.alerts > 0 ? (
                      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#C8102E] text-white text-xs font-bold">
                        {student.alerts}
                      </span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Link to={`/dashboard/students/${student.id}`}>
                      <Button variant="outline" size="sm">
                        Ver Perfil
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
