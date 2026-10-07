import { useRef, useState } from 'react';
import { Upload, CheckCircle, AlertCircle } from 'lucide-react';
import { apiFetch } from '../../services/apiFetch';
import { Button } from './ui/Button';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface ErrorFila {
  fila: number;
  campo: string;
  valor: string | null;
  mensaje: string;
}

// HU-33: carga de asistencia por archivo para los cursos del docente
export default function AttendanceImport() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [exito, setExito] = useState(false);
  const [errores, setErrores] = useState<ErrorFila[]>([]);

  const uploadFile = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    setUploading(true);
    setMensaje(null);
    setErrores([]);
    try {
      const res = await apiFetch(`${BASE_URL}/api/academico/import/asistencia/`, {
        method: 'POST',
        body: formData,
      });
      const json = await res.json();
      setExito(res.ok);
      setMensaje(json.mensaje || json.error || (res.ok ? 'Asistencia importada.' : 'No se pudo importar el archivo.'));
      setErrores(Array.isArray(json.errores) ? json.errores : []);
    } catch {
      setExito(false);
      setMensaje('Error de conexión con el servidor.');
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
      <div className="border-b border-gray-100 px-6 py-4 flex items-center gap-2">
        <Upload className="w-5 h-5 text-[#C8102E]" />
        <h2 className="text-base font-bold text-gray-900">Cargar asistencia desde archivo</h2>
      </div>
      <div className="p-6 space-y-4">
        <div className="text-sm text-gray-600">
          Archivo Excel o CSV con las columnas{' '}
          <strong>Periodo | Codigo Estudiante | Materia | Fecha | Estado</strong>.
          <ul className="list-disc ml-5 mt-1 text-xs text-gray-500 space-y-0.5">
            <li>Periodo: AAAA-S, por ejemplo 2026-2.</li>
            <li>Materia: código y grupo como en la oferta, por ejemplo 1155501A. Solo cursos asignados a usted.</li>
            <li>Fecha: fecha de Excel o texto AAAA-MM-DD. No se aceptan fechas futuras.</li>
            <li>Estado: A, F, FJ o ASISTIO, FALTA, FALTA_JUSTIFICADA.</li>
            <li>Si una fila tiene errores no se guarda nada. Las fechas ya registradas se actualizan.</li>
          </ul>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
        />
        <Button
          variant="outline"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="text-[#C8102E] border-[#C8102E]/30 hover:bg-red-50"
        >
          <Upload className="w-4 h-4 mr-2" />
          {uploading ? 'Importando...' : 'Seleccionar archivo'}
        </Button>

        {mensaje && (
          <div className={`p-3 rounded-lg border text-sm flex items-center gap-2 ${exito ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-700'}`}>
            {exito ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            {mensaje}
          </div>
        )}

        {errores.length > 0 && (
          <div className="max-h-60 overflow-y-auto border border-red-200 rounded-lg">
            <table className="w-full text-xs">
              <thead className="bg-red-100 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold text-red-800">Fila</th>
                  <th className="px-3 py-2 text-left font-semibold text-red-800">Campo</th>
                  <th className="px-3 py-2 text-left font-semibold text-red-800">Valor</th>
                  <th className="px-3 py-2 text-left font-semibold text-red-800">Detalle</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-red-100">
                {errores.map((err, i) => (
                  <tr key={i}>
                    <td className="px-3 py-1.5 text-red-700">{err.fila}</td>
                    <td className="px-3 py-1.5 text-red-700">{err.campo}</td>
                    <td className="px-3 py-1.5 text-red-700 font-mono">{err.valor}</td>
                    <td className="px-3 py-1.5 text-red-600">{err.mensaje}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
