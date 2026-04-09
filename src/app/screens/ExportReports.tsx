import { useState } from 'react';
import { FileText, Download } from 'lucide-react';
import { Button } from '../components/ui/Button';

const reportTypes = [
  'Reporte de Riesgo Estudiantil',
  'Reporte Resumen de Alertas',
  'Reporte de Rendimiento Académico',
  'Análisis de Reprobación de Cursos',
  'Reporte de Seguimiento de Intervenciones',
  'Reporte de Análisis de Cohortes',
];

const sampleData = [
  { code: '1151234', name: 'María Alejandra Ramírez González', risk: 'ALTO', gpa: 3.2, alerts: 3 },
  { code: '1151567', name: 'Carlos Andrés Mendoza Pérez', risk: 'ALTO', gpa: 2.8, alerts: 5 },
  { code: '1151890', name: 'Laura Valentina Torres Silva', risk: 'BAJO', gpa: 4.1, alerts: 0 },
  { code: '1152134', name: 'Diego Fernando Castillo Ruiz', risk: 'MEDIO', gpa: 3.5, alerts: 2 },
  { code: '1152456', name: 'Ana María López Martínez', risk: 'ALTO', gpa: 2.9, alerts: 4 },
];

export default function ExportReports() {
  const [selectedReport, setSelectedReport] = useState('Reporte de Riesgo Estudiantil');
  const [dateFrom, setDateFrom] = useState('2026-01-01');
  const [dateTo, setDateTo] = useState('2026-04-08');
  const [format, setFormat] = useState<'pdf' | 'excel'>('pdf');

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="border-l-4 border-[#C8102E] pl-4">
        <h1 className="text-2xl font-bold text-gray-900">Exportar Reportes</h1>
        <p className="text-sm text-gray-600 mt-1">
          Genera y descarga reportes para análisis y documentación
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Left panel - filters */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Configuración del Reporte</h2>
          </div>

          {/* Report type selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Tipo de Reporte
            </label>
            <select
              value={selectedReport}
              onChange={(e) => setSelectedReport(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
            >
              {reportTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          {/* Date range */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Fecha Desde
              </label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Fecha Hasta
              </label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent"
              />
            </div>
          </div>

          {/* Additional filters */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Nivel de Riesgo (Opcional)
            </label>
            <select className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent">
              <option value="">Todos los Niveles</option>
              <option value="high">Solo Riesgo Alto</option>
              <option value="medium">Solo Riesgo Medio</option>
              <option value="low">Solo Riesgo Bajo</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Programa (Opcional)
            </label>
            <select className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent">
              <option value="">Todos los Programas</option>
              <option value="systems">Ingeniería de Sistemas</option>
              <option value="industrial">Ingeniería Industrial</option>
              <option value="civil">Ingeniería Civil</option>
              <option value="mechanical">Ingeniería Mecánica</option>
            </select>
          </div>

          {/* Format selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Formato de Exportación
            </label>
            <div className="flex gap-3">
              <button
                onClick={() => setFormat('pdf')}
                className={`flex-1 px-4 py-3 rounded-lg border-2 font-medium transition-all flex items-center justify-center gap-2 ${
                  format === 'pdf'
                    ? 'border-[#C8102E] bg-red-50 text-[#C8102E]'
                    : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
                }`}
              >
                <FileText className="w-4 h-4" />
                PDF
              </button>
              <button
                onClick={() => setFormat('excel')}
                className={`flex-1 px-4 py-3 rounded-lg border-2 font-medium transition-all flex items-center justify-center gap-2 ${
                  format === 'excel'
                    ? 'border-[#C8102E] bg-red-50 text-[#C8102E]'
                    : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
                }`}
              >
                <FileText className="w-4 h-4" />
                Excel
              </button>
            </div>
          </div>

          {/* Generate button */}
          <Button fullWidth size="lg">
            <Download className="w-4 h-4 mr-2" />
            Generar y Descargar
          </Button>
        </div>

        {/* Right panel - preview */}
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="border-b border-gray-200 px-6 py-4 bg-gray-50">
            <h2 className="text-lg font-semibold text-gray-900">Vista Previa del Reporte</h2>
            <p className="text-sm text-gray-500 mt-1">Datos de muestra para {selectedReport}</p>
          </div>

          <div className="p-6">
            {/* Report header preview */}
            <div className="mb-6 pb-4 border-b border-gray-200">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-12 h-12 bg-[#C8102E] rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-xl">U</span>
                </div>
                <div>
                  <h3 className="font-bold text-gray-900">UFPS</h3>
                  <p className="text-xs text-gray-500">Universidad Francisco de Paula Santander</p>
                </div>
              </div>
              <h4 className="font-semibold text-gray-900">{selectedReport}</h4>
              <p className="text-xs text-gray-500">
                Período: {dateFrom} a {dateTo}
              </p>
            </div>

            {/* Sample table preview */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#C8102E] text-white">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium uppercase">
                      Código
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium uppercase">
                      Nombre del Estudiante
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium uppercase">
                      Riesgo
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium uppercase">
                      Promedio
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium uppercase">
                      Alertas
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {sampleData.map((row, index) => (
                    <tr
                      key={index}
                      className={index % 2 === 0 ? 'bg-white' : 'bg-[#F5F5F5]'}
                    >
                      <td className="px-3 py-2 text-xs text-gray-900">{row.code}</td>
                      <td className="px-3 py-2 text-xs text-gray-900">{row.name}</td>
                      <td className="px-3 py-2 text-xs">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                            row.risk === 'ALTO'
                              ? 'bg-[#C8102E] text-white'
                              : row.risk === 'MEDIO'
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {row.risk}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs font-semibold text-gray-900">
                        {row.gpa.toFixed(1)}
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-900">{row.alerts}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 pt-4 border-t border-gray-200 text-xs text-gray-500 text-center">
              Esta es una vista previa. El reporte final incluirá todos los registros filtrados.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
