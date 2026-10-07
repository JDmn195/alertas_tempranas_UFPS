import { useState, useEffect } from 'react';
import { X, Save, AlertTriangle, Users, CheckSquare } from 'lucide-react';
import { apiFetch } from '../../services/apiFetch';
import { Button } from './ui/Button';
import { toast } from 'sonner';

interface AttendanceModalProps {
  curso: any;
  onClose: () => void;
}

interface EstudianteAsistencia {
  codigo: string;
  nombre: string;
  estado: string | null;
  observacion: string | null;
}

interface AttendanceResponse {
  fecha: string;
  periodo: string;
  ya_registrada: boolean;
  fechas_registradas: string[];
  estudiantes: EstudianteAsistencia[];
}

interface ErrorEstudiante {
  codigo_estudiante: string | null;
  campo: string;
  mensaje: string;
}

// Fecha local en formato AAAA-MM-DD (toISOString usa UTC y puede adelantar un día)
const hoyLocal = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

export default function AttendanceModal({ curso, onClose }: AttendanceModalProps) {
  const [selectedDate, setSelectedDate] = useState<string>(hoyLocal());
  const [attendanceData, setAttendanceData] = useState<AttendanceResponse | null>(null);
  const [records, setRecords] = useState<Record<string, string>>({});
  const [observaciones, setObservaciones] = useState<Record<string, string>>({});
  const [saveErrors, setSaveErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    if (curso && selectedDate) {
      fetchAttendance();
    }
  }, [curso, selectedDate]);

  const fetchAttendance = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`${BASE_URL}/api/academico/cursos/${curso.curso_id}/asistencia/?fecha=${selectedDate}`);
      const json = await res.json();
      
      if (!res.ok) {
        throw new Error(json.mensaje || json.error || 'Error al cargar asistencia');
      }

      setAttendanceData(json);
      
      const newRecords: Record<string, string> = {};
      const newObservaciones: Record<string, string> = {};
      json.estudiantes.forEach((est: EstudianteAsistencia) => {
        newRecords[est.codigo] = est.estado || 'ASISTIO';
        newObservaciones[est.codigo] = est.observacion || '';
      });
      setRecords(newRecords);
      setObservaciones(newObservaciones);
      setSaveErrors({});
    } catch (err: any) {
      setError(err.message);
      setAttendanceData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleStateChange = (codigo: string, value: string) => {
    setRecords(prev => ({ ...prev, [codigo]: value }));
  };

  const markAllPresent = () => {
    const newRecords = { ...records };
    Object.keys(newRecords).forEach(key => {
      newRecords[key] = 'ASISTIO';
    });
    setRecords(newRecords);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveErrors({});
    try {
      const payload = {
        fecha: selectedDate,
        registros: Object.entries(records).map(([codigo, estado]) => ({
          codigo_estudiante: codigo,
          estado,
          observacion: observaciones[codigo]?.trim() || null,
        }))
      };

      const res = await apiFetch(`${BASE_URL}/api/academico/cursos/${curso.curso_id}/asistencia/`, {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      
      const json = await res.json();
      if (!res.ok) {
        if (Array.isArray(json.errores)) {
          const porEstudiante: Record<string, string> = {};
          json.errores.forEach((e: ErrorEstudiante) => {
            if (e.codigo_estudiante) porEstudiante[e.codigo_estudiante] = e.mensaje;
          });
          setSaveErrors(porEstudiante);
        }
        throw new Error(json.mensaje || json.error || 'Error al guardar');
      }
      
      toast.success(`Asistencia guardada: ${json.creados} nuevos, ${json.actualizados} actualizados.`);
      fetchAttendance(); // Refresca "ya_registrada" y las fechas registradas
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const faltasCount = Object.values(records).filter(v => v === 'FALTA' || v === 'FALTA_JUSTIFICADA').length;

  return (
    <>
      <div className="fixed inset-0 z-[60] bg-black/50" onClick={onClose} />
      <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
          <div className="bg-[#C8102E] text-white px-6 py-4 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Tomar Asistencia: {curso.materia}</h2>
              <p className="text-xs opacity-80">{curso.codigo} · Grupo {curso.grupo}</p>
            </div>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/20 transition-colors">
              <X className="w-6 h-6" />
            </button>
          </div>

          <div className="p-6 flex flex-col flex-1 overflow-hidden">
            <div className="flex flex-col md:flex-row gap-4 justify-between items-start md:items-center mb-6">
              <div className="flex items-center gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-600 mb-1">Fecha de clase</label>
                  <input 
                    type="date" 
                    value={selectedDate}
                    max={hoyLocal()}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-[#C8102E] focus:border-[#C8102E] outline-none"
                  />
                </div>
                {attendanceData?.estudiantes && attendanceData.estudiantes.length > 0 && (
                  <Button variant="outline" size="sm" onClick={markAllPresent} className="mt-5">
                    <CheckSquare className="w-4 h-4 mr-2" />
                    Marcar todos presentes
                  </Button>
                )}
              </div>

              {attendanceData?.estudiantes && attendanceData.estudiantes.length > 0 && (
                <div className="flex flex-col items-end">
                  <div className="text-sm">
                    <span className="font-bold">{faltasCount}</span> faltas / <span className="font-bold">{attendanceData.estudiantes.length}</span> estudiantes
                  </div>
                  {attendanceData.ya_registrada && (
                    <span className="text-xs font-bold text-amber-600 bg-amber-50 px-2 py-1 rounded mt-1 border border-amber-200">
                      Modificando registro existente
                    </span>
                  )}
                </div>
              )}
            </div>

            {attendanceData && attendanceData.fechas_registradas.length > 0 && (
              <div className="mb-4">
                <p className="text-xs font-bold text-gray-600 mb-1">
                  Fechas registradas en {attendanceData.periodo} (selecciona una para corregirla)
                </p>
                <div className="flex flex-wrap gap-2">
                  {attendanceData.fechas_registradas.map(f => (
                    <button
                      key={f}
                      type="button"
                      onClick={() => setSelectedDate(f)}
                      className={`px-2.5 py-1 rounded-full text-xs font-mono border transition-colors ${f === selectedDate ? 'bg-[#C8102E] border-[#C8102E] text-white' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex-1 overflow-y-auto border border-gray-200 rounded-xl">
              {loading ? (
                <div className="py-12 text-center text-gray-400">Cargando estudiantes...</div>
              ) : error ? (
                <div className="m-4 p-4 bg-red-50 text-red-700 rounded-xl border border-red-200 flex items-center gap-2 text-sm">
                  <AlertTriangle className="w-4 h-4" /> {error}
                </div>
              ) : !attendanceData?.estudiantes || attendanceData.estudiantes.length === 0 ? (
                <div className="py-12 text-center text-gray-400 flex flex-col items-center">
                  <Users className="w-12 h-12 mb-3 opacity-20" />
                  <p>No hay estudiantes matriculados en este curso en el periodo actual.</p>
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-700 sticky top-0 z-10 shadow-sm">
                    <tr>
                      <th className="px-4 py-3 text-left font-bold">Estudiante</th>
                      <th className="px-4 py-3 text-left font-bold">Estado de Asistencia</th>
                      <th className="px-4 py-3 text-left font-bold">Observación</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {attendanceData.estudiantes.map((est, idx) => (
                      <tr key={est.codigo} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/50 hover:bg-gray-100/50 transition-colors'}>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-gray-900">{est.nombre}</p>
                          <p className="text-gray-500 font-mono text-xs">{est.codigo}</p>
                          {saveErrors[est.codigo] && (
                            <p className="text-xs text-red-600 mt-1">{saveErrors[est.codigo]}</p>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-2">
                            <label className={`cursor-pointer px-3 py-1.5 rounded-full text-xs font-bold border transition-colors ${records[est.codigo] === 'ASISTIO' ? 'bg-green-100 border-green-300 text-green-800' : 'bg-white border-gray-200 text-gray-500 hover:bg-gray-50'}`}>
                              <input 
                                type="radio" 
                                className="hidden" 
                                name={`att_${est.codigo}`}
                                checked={records[est.codigo] === 'ASISTIO'}
                                onChange={() => handleStateChange(est.codigo, 'ASISTIO')}
                              />
                              Asistió
                            </label>
                            <label className={`cursor-pointer px-3 py-1.5 rounded-full text-xs font-bold border transition-colors ${records[est.codigo] === 'FALTA' ? 'bg-red-100 border-red-300 text-red-800' : 'bg-white border-gray-200 text-gray-500 hover:bg-gray-50'}`}>
                              <input 
                                type="radio" 
                                className="hidden" 
                                name={`att_${est.codigo}`}
                                checked={records[est.codigo] === 'FALTA'}
                                onChange={() => handleStateChange(est.codigo, 'FALTA')}
                              />
                              Falta
                            </label>
                            <label className={`cursor-pointer px-3 py-1.5 rounded-full text-xs font-bold border transition-colors ${records[est.codigo] === 'FALTA_JUSTIFICADA' ? 'bg-amber-100 border-amber-300 text-amber-800' : 'bg-white border-gray-200 text-gray-500 hover:bg-gray-50'}`}>
                              <input 
                                type="radio" 
                                className="hidden" 
                                name={`att_${est.codigo}`}
                                checked={records[est.codigo] === 'FALTA_JUSTIFICADA'}
                                onChange={() => handleStateChange(est.codigo, 'FALTA_JUSTIFICADA')}
                              />
                              Falta Just.
                            </label>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <input
                            type="text"
                            maxLength={255}
                            value={observaciones[est.codigo] || ''}
                            onChange={(e) => setObservaciones(prev => ({ ...prev, [est.codigo]: e.target.value }))}
                            placeholder="Opcional"
                            className="w-full border border-gray-200 rounded-lg px-2 py-1 text-xs outline-none focus:border-[#C8102E]"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <Button variant="outline" onClick={onClose} disabled={saving}>
                Cancelar
              </Button>
              <Button 
                onClick={handleSave} 
                disabled={saving || loading || !attendanceData?.estudiantes || attendanceData.estudiantes.length === 0}
                className="bg-[#C8102E] hover:bg-red-700 text-white"
              >
                {saving ? (
                  <span className="flex items-center gap-2"><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"/> Guardando...</span>
                ) : (
                  <span className="flex items-center gap-2"><Save className="w-4 h-4"/> Guardar Asistencia</span>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
