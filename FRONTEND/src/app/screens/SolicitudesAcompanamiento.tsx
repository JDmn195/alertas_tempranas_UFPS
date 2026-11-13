import { useEffect, useState } from 'react';
import { CheckCircle2, Clock, HandHelping, Inbox, MessageSquareReply, UserCheck } from 'lucide-react';
import { apiFetch } from '../../services/apiFetch';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';

import { CargandoBloque } from '../components/Estados';
import { EncabezadoPagina } from '../components/Panel';
const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

type EstadoSolicitud = 'PENDIENTE' | 'EN_ATENCION' | 'ATENDIDA' | 'CANCELADA';

interface Solicitud {
  id: number;
  estudiante: { codigo: string; nombre: string; semestre: number; correo: string | null };
  motivo: string;
  motivo_texto: string;
  descripcion: string;
  alerta: { id: number; tipo: string; estado: string } | null;
  periodo: string | null;
  estado: EstadoSolicitud;
  estado_texto: string;
  responsable: { id: number; nombre: string } | null;
  respuesta: string | null;
  fecha_solicitud: string;
  fecha_atencion: string | null;
  transiciones: EstadoSolicitud[];
}

interface Bandeja {
  solicitudes: Solicitud[];
  conteos: Record<EstadoSolicitud | 'total', number>;
  periodos: string[];
  estados: { valor: EstadoSolicitud; texto: string }[];
}

const INSIGNIA_ESTADO: Record<EstadoSolicitud, string> = {
  PENDIENTE: 'bg-amber-50 text-amber-800',
  EN_ATENCION: 'bg-primary-tint text-primary',
  ATENDIDA: 'bg-green-50 text-green-700',
  CANCELADA: 'bg-wash text-ink-muted',
};

const fecha = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }) : '—';

type Accion = 'responder' | 'cerrar';

/**
 * HU-41: bandeja de solicitudes de acompañamiento de los estudiantes. Bienestar,
 * Dirección y Administración las toman, responden y cierran; el estudiante recibe
 * cada cambio por correo y en su portal.
 */
export default function SolicitudesAcompanamiento() {
  const [bandeja, setBandeja] = useState<Bandeja | null>(null);
  const [estado, setEstado] = useState('PENDIENTE');
  const [periodo, setPeriodo] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);
  const [recarga, setRecarga] = useState(0);
  const [dialogo, setDialogo] = useState<{ accion: Accion; solicitud: Solicitud } | null>(null);
  const [respuesta, setRespuesta] = useState('');
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    let activo = true;
    const params = new URLSearchParams();
    if (estado) params.set('estado', estado);
    if (periodo) params.set('periodo', periodo);
    const query = params.toString();
    apiFetch(`${baseUrl}/api/alertas/solicitudes/${query ? `?${query}` : ''}`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || 'No fue posible consultar las solicitudes.');
        if (activo) {
          setBandeja(json);
          setError(null);
        }
      })
      .catch((e: Error) => activo && setError(e.message));
    return () => {
      activo = false;
    };
  }, [estado, periodo, recarga]);

  const actualizar = async (solicitud: Solicitud, datos: Record<string, string>, exito: string) => {
    setGuardando(true);
    try {
      const res = await apiFetch(`${baseUrl}/api/alertas/solicitudes/${solicitud.id}/`, {
        method: 'PATCH',
        body: JSON.stringify(datos),
      });
      const json = await res.json();
      if (!res.ok) {
        setAviso({ tipo: 'error', texto: json.error || 'No fue posible actualizar la solicitud.' });
        return false;
      }
      setAviso({ tipo: 'ok', texto: exito });
      setRecarga((n) => n + 1);
      return true;
    } catch {
      setAviso({ tipo: 'error', texto: 'No fue posible actualizar la solicitud.' });
      return false;
    } finally {
      setGuardando(false);
    }
  };

  const abrirDialogo = (accion: Accion, solicitud: Solicitud) => {
    setRespuesta(solicitud.respuesta ?? '');
    setAviso(null);
    setDialogo({ accion, solicitud });
  };

  const confirmarDialogo = async () => {
    if (!dialogo) return;
    const texto = respuesta.trim();
    if (!texto) {
      setAviso({ tipo: 'error', texto: 'Escribe la respuesta para el estudiante.' });
      return;
    }
    const { accion, solicitud } = dialogo;
    const ok = accion === 'cerrar'
      ? await actualizar(solicitud, { estado: 'ATENDIDA', respuesta: texto }, 'La solicitud quedó atendida y se avisó al estudiante.')
      : await actualizar(solicitud, { respuesta: texto }, 'Respuesta registrada y enviada al estudiante.');
    if (ok) setDialogo(null);
  };

  const claseSelect = 'h-10 px-3.5 border border-line-strong rounded-[10px] bg-white text-sm text-ink';

  let contenido: React.ReactNode;
  if (error) {
    contenido = <p role="alert" className="text-sm text-red-700">{error}</p>;
  } else if (!bandeja) {
    contenido = <CargandoBloque texto="Cargando solicitudes…" filas={4} />;
  } else if (bandeja.solicitudes.length === 0) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-12 text-ink-muted">
        <Inbox className="w-8 h-8 mb-2 text-ink-faint" aria-hidden="true" />
        <p className="text-sm">No hay solicitudes con los filtros seleccionados.</p>
      </div>
    );
  } else {
    contenido = (
      <ul className="divide-y divide-line -mx-4 sm:-mx-5 -mb-4 sm:-mb-5 border-t border-line">
        {bandeja.solicitudes.map((s) => (
          <li key={s.id} className="px-4 sm:px-5 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-gray-900">
                  {s.estudiante.nombre} <span className="text-sm font-normal text-gray-500">· {s.estudiante.codigo} · Semestre {s.estudiante.semestre}</span>
                </p>
                <div className="flex flex-wrap items-center gap-2 mt-1">
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">{s.motivo_texto}</span>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${INSIGNIA_ESTADO[s.estado]}`}>{s.estado_texto}</span>
                  <span className="text-xs text-gray-500 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {fecha(s.fecha_solicitud)}{s.periodo && <> · Periodo {s.periodo}</>}
                  </span>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {s.estado === 'PENDIENTE' && (
                  <button type="button" disabled={guardando}
                    onClick={() => actualizar(s, { estado: 'EN_ATENCION' }, 'Tomaste la solicitud. El estudiante fue notificado.')}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm rounded-[10px] bg-primary text-white hover:bg-primary-strong disabled:opacity-50">
                    <UserCheck className="w-4 h-4" /> Tomar
                  </button>
                )}
                {s.transiciones.length > 0 && (
                  <>
                    <button type="button" disabled={guardando} onClick={() => abrirDialogo('responder', s)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-sm rounded-[10px] border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50">
                      <MessageSquareReply className="w-4 h-4" /> Responder
                    </button>
                    <button type="button" disabled={guardando} onClick={() => abrirDialogo('cerrar', s)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-sm rounded-[10px] border border-green-300 text-green-700 hover:bg-green-50 disabled:opacity-50">
                      <CheckCircle2 className="w-4 h-4" /> Cerrar como atendida
                    </button>
                  </>
                )}
              </div>
            </div>
            <p className="text-sm text-gray-700 mt-3 whitespace-pre-line">{s.descripcion}</p>
            <div className="text-xs text-gray-500 mt-2 space-y-0.5">
              {s.alerta && <p>Alerta relacionada: {s.alerta.tipo} (ID {s.alerta.id}, {s.alerta.estado})</p>}
              {s.estudiante.correo && <p>Correo: {s.estudiante.correo}</p>}
              {s.responsable && <p>Responsable: {s.responsable.nombre}</p>}
            </div>
            {s.respuesta && (
              <div className="mt-3 text-sm bg-gray-50 border border-gray-200 rounded-[10px] px-3 py-2">
                <p className="text-xs font-semibold text-gray-600 mb-0.5">
                  Respuesta al estudiante{s.fecha_atencion ? ` · ${fecha(s.fecha_atencion)}` : ''}
                </p>
                <p className="text-gray-800 whitespace-pre-line">{s.respuesta}</p>
              </div>
            )}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="space-y-5">
      <EncabezadoPagina
        titulo="Solicitudes de acompañamiento"
        detalle="Solicitudes enviadas por los estudiantes desde su portal. Tómalas, responde y ciérralas cuando estén atendidas."
      >
        <div className="flex items-center gap-2">
          <label htmlFor="solicitudes-periodo" className="text-sm font-medium text-ink-muted">Periodo</label>
          <select id="solicitudes-periodo" className={`${claseSelect} min-w-[120px]`} value={periodo} onChange={(e) => setPeriodo(e.target.value)}>
            <option value="">Todos</option>
            {bandeja?.periodos.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
      </EncabezadoPagina>

      {/* El estado es el filtro principal y muestra cuántas solicitudes hay en cada uno */}
      <div className="bg-white border border-line rounded-[14px] overflow-hidden">
        <div className="flex flex-wrap items-stretch gap-px bg-line border-b border-line" role="group" aria-label="Filtrar por estado">
          {[{ valor: '', texto: 'Todas', cuenta: bandeja?.conteos.total }, ...(bandeja?.estados.map((e) => ({ valor: e.valor as string, texto: e.texto, cuenta: bandeja.conteos[e.valor] })) ?? [])].map((e) => (
            <button
              key={e.valor || 'todas'}
              type="button"
              onClick={() => setEstado(e.valor)}
              aria-pressed={estado === e.valor}
              className={`flex-1 min-w-[8rem] text-left px-4 py-3 ${estado === e.valor ? 'bg-primary-tint' : 'bg-white hover:bg-paper'}`}
            >
              <span className="block text-sm font-medium text-ink-muted">{e.texto}</span>
              <span className="cifra block mt-1 text-xl font-semibold text-ink leading-none">{e.cuenta ?? '—'}</span>
            </button>
          ))}
        </div>

        <div className="p-4 sm:p-5 space-y-4">
          {aviso && !dialogo && (
            <p role={aviso.tipo === 'error' ? 'alert' : 'status'}
              className={`text-sm rounded-[10px] px-3 py-2 border ${aviso.tipo === 'ok'
                ? 'text-green-800 bg-green-50 border-green-200' : 'text-red-700 bg-red-50 border-red-200'}`}>
              {aviso.texto}
            </p>
          )}

          {contenido}
        </div>
      </div>

      <Dialog open={dialogo !== null} onOpenChange={(abierto) => !abierto && setDialogo(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{dialogo?.accion === 'cerrar' ? 'Cerrar solicitud como atendida' : 'Responder al estudiante'}</DialogTitle>
            <DialogDescription>
              {dialogo?.solicitud.estudiante.nombre} · {dialogo?.solicitud.motivo_texto}. El estudiante verá esta respuesta en
              su portal y la recibirá por correo.
            </DialogDescription>
          </DialogHeader>
          <textarea value={respuesta} onChange={(e) => setRespuesta(e.target.value)} rows={5}
            placeholder="Escribe la respuesta o los acuerdos para el estudiante."
            className="w-full px-3 py-2 border border-gray-300 rounded-[10px] focus:outline-none focus:ring-2 focus:ring-primary text-sm" />
          {aviso?.tipo === 'error' && <p role="alert" className="text-sm text-red-700">{aviso.texto}</p>}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setDialogo(null)}
              className="px-4 py-2 text-sm rounded-[10px] border border-gray-300 text-gray-700 hover:bg-gray-50">
              Volver
            </button>
            <button type="button" disabled={guardando} onClick={confirmarDialogo}
              className="px-4 py-2 text-sm rounded-[10px] bg-primary text-white hover:bg-primary-strong disabled:opacity-50">
              {guardando ? 'Guardando…' : dialogo?.accion === 'cerrar' ? 'Cerrar solicitud' : 'Enviar respuesta'}
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
