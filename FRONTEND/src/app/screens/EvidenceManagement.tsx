import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router';
import { 
  Upload, 
  FileText, 
  Image as ImageIcon, 
  Trash2, 
  ArrowLeft, 
  Download, 
  Plus, 
  File,
  AlertCircle,
  CheckCircle2,
  Loader2,
  MessageSquare,
  Send,
  Lock,
  CheckCircle
} from 'lucide-react';
import { evidenceService, Evidencia, Anotacion, IntervencionDetalle } from '../../services/evidenceService';

export default function EvidenceManagement() {
  const { intervencionId } = useParams<{ intervencionId: string }>();
  const navigate = useNavigate();
  const [evidencias, setEvidencias] = useState<Evidencia[]>([]);
  const [anotaciones, setAnotaciones] = useState<Anotacion[]>([]);
  const [intervencionInfo, setIntervencionInfo] = useState<IntervencionDetalle | null>(null);
  
  const [nuevaAnotacion, setNuevaAnotacion] = useState('');
  const [resumenFinal, setResumenFinal] = useState('');
  
  const [loading, setLoading] = useState(true);
  const [loadingAnotaciones, setLoadingAnotaciones] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [enviandoAnotacion, setEnviandoAnotacion] = useState(false);
  const [concluding, setConcluding] = useState(false);
  const [showConcludeModal, setShowConcludeModal] = useState(false);
  
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const id = parseInt(intervencionId || '0');
  
  const userJson = localStorage.getItem('user');
  const currentUser = userJson ? JSON.parse(userJson) : null;

  const loadEvidencias = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      const data = await evidenceService.getByIntervencion(id);
      setEvidencias(data.evidencias);
      setIntervencionInfo(data.intervencion);
    } catch (err) {
      setError('No se pudieron cargar las evidencias');
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadAnotaciones = useCallback(async () => {
    if (!id) return;
    try {
      setLoadingAnotaciones(true);
      const data = await evidenceService.getAnotaciones(id);
      setAnotaciones(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingAnotaciones(false);
    }
  }, [id]);

  useEffect(() => {
    loadEvidencias();
    loadAnotaciones();
  }, [loadEvidencias, loadAnotaciones]);

  const isClosed = intervencionInfo?.alerta_estado.toLowerCase() === 'cerrada' || intervencionInfo?.alerta_estado.toLowerCase() === 'atendida';

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !id || isClosed) return;

    if (file.size > 5 * 1024 * 1024) {
      setError('El archivo es demasiado grande (máximo 5MB)');
      return;
    }

    setUploading(true);
    setError(null);
    try {
      await evidenceService.upload(id, file);
      setSuccessMsg('Archivo subido con éxito');
      loadEvidencias();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Error al subir el archivo');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = async (evidenciaId: number) => {
    if (isClosed) return;
    if (!window.confirm('¿Estás seguro de eliminar esta evidencia?')) return;

    try {
      await evidenceService.delete(evidenciaId);
      setEvidencias(evidencias.filter(e => e.id !== evidenciaId));
      setSuccessMsg('Evidencia eliminada');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError('No se pudo eliminar el archivo');
    }
  };

  const handleAnotacionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isClosed || !nuevaAnotacion.trim() || !id || !currentUser?.id) {
      if (!isClosed) setError('Asegúrate de haber iniciado sesión y no enviar observaciones vacías');
      return;
    }
    
    setEnviandoAnotacion(true);
    setError(null);
    try {
      await evidenceService.createAnotacion(id, currentUser.id, nuevaAnotacion.trim());
      setNuevaAnotacion('');
      loadAnotaciones();
    } catch (err: any) {
      setError(err.message || 'Error al guardar la observación');
    } finally {
      setEnviandoAnotacion(false);
    }
  };

  const handleDeleteAnotacion = async (anotacionId: number) => {
    if (isClosed) return;
    if (!window.confirm('¿Eliminar esta observación?')) return;

    try {
      await evidenceService.deleteAnotacion(anotacionId);
      setAnotaciones(anotaciones.filter(a => a.id !== anotacionId));
    } catch (err) {
      setError('Error al eliminar la observación');
    }
  };

  const handleConcluir = async () => {
    if (!resumenFinal.trim() || !id) return;
    
    setConcluding(true);
    setError(null);
    try {
      await evidenceService.concluirIntervencion(id, resumenFinal.trim());
      setShowConcludeModal(false);
      setSuccessMsg('Intervención concluida y alerta cerrada con éxito.');
      loadEvidencias(); // Recargar para actualizar el estado a cerrado
    } catch (err: any) {
      setError(err.message || 'Error al concluir la intervención');
    } finally {
      setConcluding(false);
    }
  };

  const getFileIcon = (tipo: string) => {
    if (tipo.includes('image')) return <ImageIcon className="w-8 h-8 text-blue-500" />;
    if (tipo.includes('pdf')) return <FileText className="w-8 h-8 text-red-500" />;
    return <File className="w-8 h-8 text-gray-500" />;
  };

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-8 animate-in fade-in duration-500">
      
      {/* Header */}
      <div className="flex items-center justify-between">
        <button 
          onClick={() => navigate('/dashboard/alerts')}
          className="flex items-center gap-2 text-gray-500 hover:text-[#C8102E] transition-colors font-medium"
        >
          <ArrowLeft className="w-5 h-5" />
          Volver a Intervenciones
        </button>
        
        <div className="flex flex-col items-end text-right">
          <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">
            {intervencionInfo ? `Estudiante: ${intervencionInfo.estudiante_nombre}` : 'Gestión de Evidencias'}
          </h1>
          {intervencionInfo && (
            <div className="flex items-center gap-3 mt-1">
              <span className="text-sm font-bold text-gray-400 bg-gray-100 px-2 py-0.5 rounded-md">
                Cód: {intervencionInfo.estudiante_codigo}
              </span>
              {isClosed ? (
                <span className="text-xs font-bold bg-gray-200 text-gray-600 px-2 py-1 rounded-full flex items-center gap-1">
                  <Lock className="w-3 h-3" /> ALERTA CERRADA
                </span>
              ) : (
                <span className="text-xs font-bold bg-green-100 text-green-700 px-2 py-1 rounded-full flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span> ACTIVA
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {isClosed && intervencionInfo?.resultado && (
        <div className="bg-gray-800 text-white rounded-2xl p-6 shadow-lg relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-10">
            <CheckCircle className="w-24 h-24" />
          </div>
          <h2 className="text-lg font-bold flex items-center gap-2 mb-3 text-gray-100">
            <CheckCircle2 className="w-5 h-5 text-green-400" />
            Resumen Final de Intervención
          </h2>
          <p className="text-gray-300 leading-relaxed max-w-3xl relative z-10">
            {intervencionInfo.resultado}
          </p>
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Upload Section */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-4">
            <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
              <Upload className="w-5 h-5 text-[#C8102E]" />
              {isClosed ? 'Evidencias (Solo lectura)' : 'Subir Evidencia'}
            </h2>
            <p className="text-sm text-gray-500 leading-relaxed">
              {isClosed 
                ? 'Esta alerta ha sido cerrada. No se pueden adjuntar más archivos.'
                : 'Sube fotos, actas escaneadas o reportes en PDF que sirvan como soporte.'}
            </p>
            
            {!isClosed && (
              <>
                <div className="relative group">
                  <input 
                    type="file" 
                    onChange={handleFileUpload}
                    disabled={uploading}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10 disabled:cursor-not-allowed"
                    accept="image/*,.pdf"
                  />
                  <div className={`
                    border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center gap-3 transition-all
                    ${uploading ? 'bg-gray-50 border-gray-200' : 'group-hover:border-[#C8102E] group-hover:bg-red-50/30 border-gray-200'}
                  `}>
                    {uploading ? (
                      <Loader2 className="w-10 h-10 text-[#C8102E] animate-spin" />
                    ) : (
                      <Plus className="w-10 h-10 text-gray-300 group-hover:text-[#C8102E] transition-colors" />
                    )}
                    <span className="text-xs font-bold text-gray-400 group-hover:text-[#C8102E] uppercase tracking-wider">
                      {uploading ? 'Subiendo...' : 'Seleccionar Archivo'}
                    </span>
                  </div>
                </div>
                <p className="text-[10px] text-center text-gray-400 uppercase font-bold tracking-widest">
                  Formatos: PDF, JPG, PNG (Max 5MB)
                </p>
              </>
            )}
          </div>

          {error && (
            <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-xl flex items-start gap-3 shadow-sm animate-in slide-in-from-left">
              <AlertCircle className="w-5 h-5 text-red-500 mt-0.5" />
              <p className="text-sm text-red-700 font-medium">{error}</p>
            </div>
          )}
          {successMsg && (
            <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl flex items-start gap-3 shadow-sm animate-in slide-in-from-left">
              <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5" />
              <p className="text-sm text-green-700 font-medium">{successMsg}</p>
            </div>
          )}

          {!isClosed && (
            <button
              onClick={() => setShowConcludeModal(true)}
              className="w-full py-4 bg-gray-900 hover:bg-black text-white font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2"
            >
              <CheckCircle2 className="w-5 h-5" />
              Concluir Intervención
            </button>
          )}
        </div>

        {/* Gallery Section */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-gray-900">Archivos Adjuntos ({evidencias.length})</h3>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
              <Loader2 className="w-10 h-10 text-gray-200 animate-spin" />
              <p className="text-gray-400 font-medium italic">Cargando galería...</p>
            </div>
          ) : evidencias.length === 0 ? (
            <div className="bg-gray-50 border-2 border-dotted border-gray-200 rounded-3xl py-20 flex flex-col items-center justify-center gap-4">
              <div className="bg-white p-4 rounded-2xl shadow-sm">
                <FileText className="w-8 h-8 text-gray-300" />
              </div>
              <p className="text-gray-400 font-medium">Aún no hay evidencias para esta intervención</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {evidencias.map((evidencia) => (
                <div 
                  key={evidencia.id}
                  className="group bg-white border border-gray-100 rounded-2xl p-4 flex items-center gap-4 hover:shadow-xl hover:shadow-gray-100 transition-all hover:-translate-y-1"
                >
                  <div className="bg-gray-50 p-3 rounded-xl group-hover:bg-white transition-colors">
                    {getFileIcon(evidencia.tipo)}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-gray-800 truncate" title={evidencia.nombre}>
                      {evidencia.nombre}
                    </p>
                    <p className="text-[10px] text-gray-400 font-bold uppercase tracking-tighter mt-1">
                      {evidencia.fecha}
                    </p>
                  </div>

                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <a 
                      href={evidencia.url} 
                      target="_blank" 
                      rel="noreferrer"
                      className="p-2 text-gray-400 hover:text-[#C8102E] transition-colors"
                      title="Ver/Descargar"
                    >
                      <Download className="w-4 h-4" />
                    </a>
                    {!isClosed && (
                      <button 
                        onClick={() => handleDelete(evidencia.id)}
                        className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                        title="Eliminar"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Seccion de Anotaciones / Observaciones */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-6 mt-8">
        <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-[#C8102E]" />
          Historial de Observaciones
        </h2>
        
        {!isClosed && (
          <form onSubmit={handleAnotacionSubmit} className="flex gap-3">
            <input
              type="text"
              value={nuevaAnotacion}
              onChange={(e) => setNuevaAnotacion(e.target.value)}
              placeholder="Añadir una nueva observación o nota sobre esta intervención..."
              className="flex-1 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-[#C8102E]/20 focus:border-[#C8102E] outline-none text-sm transition-all"
            />
            <button
              type="submit"
              disabled={!nuevaAnotacion.trim() || enviandoAnotacion}
              className="px-6 bg-[#C8102E] hover:bg-red-700 text-white font-medium text-sm rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {enviandoAnotacion ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Agregar
            </button>
          </form>
        )}

        <div className="space-y-4 pt-4">
          {loadingAnotaciones ? (
            <p className="text-sm text-gray-400">Cargando observaciones...</p>
          ) : anotaciones.length === 0 ? (
            <p className="text-sm text-gray-400 italic bg-gray-50 p-4 rounded-xl text-center border border-dashed border-gray-200">
              No hay observaciones registradas aún.
            </p>
          ) : (
            <div className="space-y-3">
              {anotaciones.map((anota) => (
                <div key={anota.id} className="group bg-gray-50 border border-gray-100 p-4 rounded-xl flex gap-4 animate-in slide-in-from-bottom-2">
                  <div className="w-10 h-10 bg-[#C8102E]/10 rounded-full flex items-center justify-center flex-shrink-0">
                    <span className="text-[#C8102E] font-bold text-sm">
                      {anota.usuario.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-baseline justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-gray-900">{anota.usuario}</h4>
                        <span className="text-[10px] bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full uppercase font-bold tracking-wider">
                          {anota.usuario_rol}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-400 font-medium">{anota.fecha}</span>
                        {!isClosed && (
                          <button
                            onClick={() => handleDeleteAnotacion(anota.id)}
                            className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                            title="Eliminar observación"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                    <p className="text-sm text-gray-700 leading-relaxed mt-1">{anota.texto}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Modal de Conclusión */}
      {showConcludeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-6">
            <div>
              <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                <CheckCircle2 className="w-6 h-6 text-[#C8102E]" />
                Concluir Intervención
              </h3>
              <p className="text-sm text-gray-500 mt-2">
                Escribe un resumen final. Al confirmar, la alerta pasará a estado cerrado y no se podrán agregar más evidencias ni observaciones.
              </p>
            </div>
            
            <textarea
              value={resumenFinal}
              onChange={(e) => setResumenFinal(e.target.value)}
              placeholder="Ej: El estudiante se comprometió a asistir a tutorías semanales y firmó el acta. Mejora esperada..."
              className="w-full h-32 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-[#C8102E]/20 focus:border-[#C8102E] outline-none text-sm resize-none"
            />
            
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowConcludeModal(false)}
                disabled={concluding}
                className="px-5 py-2.5 text-gray-600 font-bold hover:bg-gray-100 rounded-xl transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleConcluir}
                disabled={concluding || !resumenFinal.trim()}
                className="px-5 py-2.5 bg-[#C8102E] hover:bg-red-700 text-white font-bold rounded-xl transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {concluding ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Confirmar Cierre'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}


