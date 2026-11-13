import { useState, useEffect, useCallback } from 'react';
import { EncabezadoPagina, Seccion } from '../components/Panel';
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
import { AvisoError, CargandoBloque, EstadoVacio } from '../components/Estados';
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

  const isClosed = intervencionInfo?.alerta_estado.toLowerCase() === 'cerrada';

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
      setSuccessMsg('Intervención concluida correctamente.');
      loadEvidencias(); // Recargar para actualizar el estado
    } catch (err: any) {
      setError(err.message || 'Error al concluir la intervención');
    } finally {
      setConcluding(false);
    }
  };

  const getFileIcon = (tipo: string) => {
    if (tipo.includes('image')) return <ImageIcon className="w-8 h-8 text-blue-500" />;
    if (tipo.includes('pdf')) return <FileText className="w-8 h-8 text-red-500" />;
    return <File className="w-8 h-8 text-ink-muted" />;
  };

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      
      <EncabezadoPagina
        titulo={intervencionInfo ? `Evidencias: ${intervencionInfo.estudiante_nombre}` : 'Gestión de Evidencias'}
        detalle={intervencionInfo ? (
          <span className="flex flex-wrap items-center gap-2">
            <span className="tabular-nums">Código {intervencionInfo.estudiante_codigo}</span>
            {isClosed ? (
              <span className="text-xs font-semibold bg-wash text-ink-muted px-2 py-1 rounded-full inline-flex items-center gap-1">
                <Lock className="w-3 h-3" /> Alerta cerrada
              </span>
            ) : intervencionInfo?.alerta_estado.toLowerCase() === 'atendida' ? (
              <span className="text-xs font-semibold bg-primary-tint text-primary px-2 py-1 rounded-full inline-flex items-center gap-1">
                <CheckCircle className="w-3 h-3" /> Atendida
              </span>
            ) : (
              <span className="text-xs font-semibold bg-green-50 text-green-700 px-2 py-1 rounded-full inline-flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-600"></span> Activa
              </span>
            )}
          </span>
        ) : undefined}
      >
        <button
          onClick={() => navigate(-1)}
          className="h-10 px-3.5 inline-flex items-center gap-2 text-sm font-medium text-ink-soft border border-line-strong rounded-[10px] bg-white hover:border-ink-faint"
        >
          <ArrowLeft className="w-4 h-4" />
          Volver
        </button>
      </EncabezadoPagina>

      {intervencionInfo?.resultado && (
        <Seccion titulo={<span className="inline-flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-green-600" />Resumen final de la intervención</span>}>
          <p className="text-ink-soft leading-relaxed max-w-3xl">{intervencionInfo.resultado}</p>
        </Seccion>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
        
        {/* Upload Section */}
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white rounded-[14px] border border-line p-5 space-y-4">
            <h2 className="text-base font-semibold text-ink flex items-center gap-2">
              <Upload className="w-5 h-5 text-primary" />
              {isClosed ? 'Evidencias (solo lectura)' : 'Subir evidencia'}
            </h2>
            <p className="text-sm text-ink-muted leading-relaxed">
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
                    border-2 border-dashed rounded-[10px] p-8 flex flex-col items-center justify-center gap-3 transition-all
                    ${uploading ? 'bg-gray-50 border-gray-200' : 'group-hover:border-primary group-hover:bg-primary-tint border-gray-200'}
                  `}>
                    {uploading ? (
                      <Loader2 className="w-10 h-10 text-primary animate-spin" />
                    ) : (
                      <Plus className="w-10 h-10 text-gray-300 group-hover:text-primary transition-colors" />
                    )}
                    <span className="text-xs font-semibold text-ink-faint group-hover:text-primary uppercase tracking-wider">
                      {uploading ? 'Subiendo...' : 'Seleccionar Archivo'}
                    </span>
                  </div>
                </div>
                <p className="text-[10px] text-center text-ink-faint uppercase font-semibold tracking-widest">
                  Formatos: PDF, JPG, PNG (Max 5MB)
                </p>
              </>
            )}
          </div>

          {error && (
            <AvisoError
              mensaje={error}
              instruccion={
                /grande/i.test(error) ? 'Comprime el archivo o elige otro de máximo 5 MB.'
                : /subir|cargar/i.test(error) ? 'Revisa tu conexión y vuelve a intentarlo.'
                : 'Si el problema continúa, recarga la página o vuelve a iniciar sesión.'
              }
            />
          )}
          {successMsg && (
            <div className="bg-green-50 border border-green-200 p-4 rounded-[10px] flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5" />
              <p className="text-sm text-green-700 font-medium">{successMsg}</p>
            </div>
          )}

          {!isClosed && !intervencionInfo?.concluida && (
            <button
              onClick={() => setShowConcludeModal(true)}
              className="w-full h-11 bg-ink hover:bg-ink-soft text-white font-semibold rounded-[10px] transition-colors flex items-center justify-center gap-2"
            >
              <CheckCircle2 className="w-5 h-5" />
              Concluir Intervención
            </button>
          )}
        </div>

        {/* Gallery Section */}
        <div className="lg:col-span-2 bg-white rounded-[14px] border border-line p-5 space-y-4">
          <h2 className="text-base font-semibold text-ink">Archivos adjuntos ({evidencias.length})</h2>

          {loading ? (
            <div role="status" aria-live="polite" className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[0, 1, 2, 3].map((n) => (
                <div key={n} className="bg-white border border-line rounded-[10px] p-3 flex items-center gap-3">
                  <div className="w-12 h-12 rounded-[10px] bg-wash animate-pulse shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 rounded-md bg-wash animate-pulse w-3/4" />
                    <div className="h-3 rounded-md bg-wash animate-pulse w-1/2" />
                  </div>
                </div>
              ))}
              <span className="sr-only">Cargando galería…</span>
            </div>
          ) : evidencias.length === 0 ? (
            <div className="bg-white border-2 border-dashed border-line-strong rounded-[10px]">
              <EstadoVacio
                icono={FileText}
                titulo="Esta intervención aún no tiene evidencias"
                detalle={isClosed
                  ? 'La alerta está cerrada, por eso ya no se pueden adjuntar archivos.'
                  : 'Adjunta fotos, actas escaneadas o reportes en PDF desde «Seleccionar Archivo» (máximo 5 MB) para dejar soporte del seguimiento.'}
              />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {evidencias.map((evidencia) => (
                <div 
                  key={evidencia.id}
                  className="group bg-white border border-line rounded-[10px] p-3 flex items-center gap-3 hover:border-line-strong transition-colors"
                >
                  <div className="bg-paper p-2.5 rounded-[10px]">
                    {getFileIcon(evidencia.tipo)}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-ink truncate" title={evidencia.nombre}>
                      {evidencia.nombre}
                    </p>
                    <p className="text-[10px] text-ink-faint font-semibold uppercase tracking-tighter mt-1">
                      {evidencia.fecha}
                    </p>
                  </div>

                  <div className="flex items-center gap-1">
                    <a 
                      href={evidencia.url} 
                      target="_blank" 
                      rel="noreferrer"
                      className="p-2 text-ink-faint hover:text-primary transition-colors"
                      title="Ver/Descargar"
                    >
                      <Download className="w-4 h-4" />
                    </a>
                    {!isClosed && (
                      <button 
                        onClick={() => handleDelete(evidencia.id)}
                        className="p-2 text-ink-faint hover:text-red-600 transition-colors"
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
      <div className="bg-white rounded-[14px] border border-line p-5 space-y-5">
        <h2 className="text-base font-semibold text-ink flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-primary" />
          Historial de Observaciones
        </h2>
        
        {!isClosed && (
          <form onSubmit={handleAnotacionSubmit} className="flex gap-3">
            <input
              type="text"
              value={nuevaAnotacion}
              onChange={(e) => setNuevaAnotacion(e.target.value)}
              placeholder="Añadir una nueva observación o nota sobre esta intervención..."
              className="flex-1 h-10 px-3.5 bg-white border border-line-strong rounded-[10px] outline-none focus:border-primary text-sm"
            />
            <button
              type="submit"
              disabled={!nuevaAnotacion.trim() || enviandoAnotacion}
              className="px-5 h-10 bg-primary hover:bg-primary-strong text-white font-medium text-sm rounded-[10px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {enviandoAnotacion ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Agregar
            </button>
          </form>
        )}

        <div className="space-y-4">
          {loadingAnotaciones ? (
            <CargandoBloque texto="Cargando observaciones…" filas={2} />
          ) : anotaciones.length === 0 ? (
            <div className="bg-white border border-dashed border-line-strong rounded-[10px]">
              <EstadoVacio
                icono={MessageSquare}
                titulo="Aún no hay observaciones"
                detalle={isClosed
                  ? 'No se registraron observaciones antes de cerrar la alerta.'
                  : 'Escribe la primera para dejar constancia de lo conversado con el estudiante.'}
              />
            </div>
          ) : (
            <div className="space-y-3">
              {anotaciones.map((anota) => (
                <div key={anota.id} className="group bg-paper border border-line p-4 rounded-[10px] flex gap-4">
                  <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center flex-shrink-0">
                    <span className="text-primary font-semibold text-sm">
                      {anota.usuario.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-baseline justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-semibold text-ink">{anota.usuario}</h4>
                        <span className="text-[10px] bg-wash text-ink-muted px-2 py-0.5 rounded-full font-semibold">
                          {anota.usuario_rol}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-ink-faint font-medium">{anota.fecha}</span>
                        {!isClosed && (
                          <button
                            onClick={() => handleDeleteAnotacion(anota.id)}
                            className="text-ink-faint hover:text-riesgo-critico"
                            title="Eliminar observación"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                    <p className="text-sm text-ink-soft leading-relaxed mt-1">{anota.texto}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Modal de Conclusión */}
      {showConcludeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/50 animate-in fade-in">
          <div className="bg-white rounded-[14px] shadow-xl w-full max-w-lg p-6 space-y-6">
            <div>
              <h3 className="text-xl font-semibold text-ink flex items-center gap-2">
                <CheckCircle2 className="w-6 h-6 text-primary" />
                Concluir Intervención
              </h3>
              <p className="text-sm text-ink-muted mt-2">
                Escribe un resumen final de esta intervención. Al confirmar, la intervención quedará marcada como concluida. Si todas las intervenciones de la alerta están concluidas, la alerta pasará a estado "Atendida".
              </p>
            </div>
            
            <textarea
              value={resumenFinal}
              onChange={(e) => setResumenFinal(e.target.value)}
              placeholder="Ej: El estudiante se comprometió a asistir a tutorías semanales y firmó el acta. Mejora esperada..."
              className="w-full h-32 px-4 py-3 bg-gray-50 border border-gray-200 rounded-[10px] focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none text-sm resize-none"
            />
            
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowConcludeModal(false)}
                disabled={concluding}
                className="px-5 py-2.5 text-ink-muted font-semibold hover:bg-gray-100 rounded-[10px] transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleConcluir}
                disabled={concluding || !resumenFinal.trim()}
                className="px-5 py-2.5 bg-primary hover:bg-primary-strong text-white font-semibold rounded-[10px] transition-colors disabled:opacity-50 flex items-center gap-2"
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


