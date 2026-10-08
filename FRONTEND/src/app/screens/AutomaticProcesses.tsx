import { useEffect, useState } from 'react';
import { BellRing, CalendarClock, ChevronDown, ChevronUp, Play, RefreshCw, Save } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { apiFetch } from '../../services/apiFetch';

// ─── HU-29: re-evaluación periódica del riesgo ──────────────────────────────

interface Ejecucion {
  id: number;
  origen: 'PROGRAMADA' | 'MANUAL';
  estado: 'EN_CURSO' | 'EXITOSA' | 'PARCIAL' | 'FALLIDA';
  intento: number;
  reintento_de: number | null;
  usuario: string | null;
  fecha_inicio: string;
  fecha_fin: string | null;
  total_estudiantes: number;
  procesados: number;
  total_errores: number;
  cambios_riesgo: number;
  alertas_generadas: number;
  alertas_actualizadas: number;
  alertas_cerradas: number;
  estudiantes_por_nivel: Record<string, number> | null;
  mensaje_error: string | null;
}

interface EjecucionDetalle extends Ejecucion {
  alcance: Record<string, unknown> | null;
  detalle_cambios: { codigo: string; de: string; a: string }[] | null;
  errores: { codigo?: string; error?: string }[] | null;
}

// ─── HU-30: recordatorios de casos sin seguimiento ──────────────────────────

interface ConfigRecordatorios {
  activo: boolean;
  dias_inactividad_alerta: number;
  dias_inactividad_intervencion: number;
  dias_entre_recordatorios: number;
  max_intentos: number;
  roles_destinatarios: string[];
  notificar_responsable: boolean;
  fecha_actualizacion: string;
  actualizado_por: string | null;
}

interface Recordatorio {
  id: number;
  tipo_caso: 'ALERTA' | 'INTERVENCION';
  alerta_id: number;
  estudiante: { codigo: string; nombre: string };
  destinatario: { id: number; nombre: string; rol: string };
  estado: 'PENDIENTE' | 'ENVIADO' | 'PARCIAL' | 'FALLIDO' | 'CANCELADO';
  dias_inactivo: number;
  intentos: number;
  max_intentos: number;
  ultimo_error: string | null;
  fecha_creacion: string;
  motivo_cancelacion: string | null;
}

interface CasoSinSeguimiento {
  tipo_caso: 'ALERTA' | 'INTERVENCION';
  alerta_id: number;
  estudiante: { codigo: string; nombre: string };
  regla: string;
  nivel: string;
  responsable: string | null;
  dias_inactivo: number;
}

const ROLES = ['ADMINISTRADOR', 'DIRECTOR', 'DOCENTE', 'BIENESTAR'];

const ESTADO_EJECUCION: Record<Ejecucion['estado'], { label: string; className: string }> = {
  EN_CURSO: { label: 'En curso', className: 'bg-blue-100 text-blue-700' },
  EXITOSA:  { label: 'Exitosa',  className: 'bg-green-100 text-green-700' },
  PARCIAL:  { label: 'Parcial',  className: 'bg-amber-100 text-amber-700' },
  FALLIDA:  { label: 'Fallida',  className: 'bg-red-100 text-red-700' },
};

const ESTADO_RECORDATORIO: Record<Recordatorio['estado'], { label: string; className: string }> = {
  PENDIENTE: { label: 'Pendiente', className: 'bg-blue-100 text-blue-700' },
  ENVIADO:   { label: 'Enviado',   className: 'bg-green-100 text-green-700' },
  PARCIAL:   { label: 'Parcial',   className: 'bg-amber-100 text-amber-700' },
  FALLIDO:   { label: 'Fallido',   className: 'bg-red-100 text-red-700' },
  CANCELADO: { label: 'Cancelado', className: 'bg-gray-100 text-gray-600' },
};

const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const formatDate = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleString('es-CO', {
        year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
      })
    : '—';

function rolActual(): string[] {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    return user?.rol ? String(user.rol).split(',') : [];
  } catch {
    return [];
  }
}

function Aviso({ tipo, texto }: { tipo: 'ok' | 'error'; texto: string }) {
  return (
    <div
      className={`rounded-lg border px-4 py-3 text-sm ${
        tipo === 'ok' ? 'border-green-200 bg-green-50 text-green-800' : 'border-red-200 bg-red-50 text-red-800'
      }`}
    >
      {texto}
    </div>
  );
}

function ReevaluacionPeriodica({ puedeEjecutar }: { puedeEjecutar: boolean }) {
  const [ejecuciones, setEjecuciones] = useState<Ejecucion[]>([]);
  const [detalle, setDetalle] = useState<EjecucionDetalle | null>(null);
  const [loading, setLoading] = useState(true);
  const [ejecutando, setEjecutando] = useState(false);
  const [mensaje, setMensaje] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);

  const cargar = async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`${baseUrl}/api/alertas/reevaluacion/ejecuciones/?limite=20`);
      if (!res.ok) throw new Error('No se pudo cargar la bitácora de ejecuciones.');
      setEjecuciones((await res.json()).ejecuciones || []);
    } catch (err: any) {
      setMensaje({ tipo: 'error', texto: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { cargar(); }, []);

  const ejecutar = async () => {
    setEjecutando(true);
    setMensaje(null);
    try {
      const res = await apiFetch(`${baseUrl}/api/alertas/reevaluacion/ejecutar/`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'No se pudo iniciar la re-evaluación.');
      setMensaje({ tipo: 'ok', texto: data.mensaje });
      setTimeout(cargar, 1500);
    } catch (err: any) {
      setMensaje({ tipo: 'error', texto: err.message });
    } finally {
      setEjecutando(false);
    }
  };

  const verDetalle = async (id: number) => {
    if (detalle?.id === id) {
      setDetalle(null);
      return;
    }
    const res = await apiFetch(`${baseUrl}/api/alertas/reevaluacion/ejecuciones/${id}/`);
    if (res.ok) setDetalle(await res.json());
  };

  const ultima = ejecuciones[0];

  return (
    <section className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      <div className="bg-gray-700 px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
          <CalendarClock className="w-4 h-4 text-white" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-white">Re-evaluación periódica del riesgo</h2>
          <p className="text-xs text-gray-400">
            Recalcula indicadores, riesgo y alertas sin una nueva importación (HU-29)
          </p>
        </div>
        <div className="ml-auto flex gap-2">
          <Button variant="secondary" size="sm" onClick={cargar}>
            <RefreshCw className={`w-4 h-4 inline mr-1 ${loading ? 'animate-spin' : ''}`} />
            Actualizar
          </Button>
          {puedeEjecutar && (
            <Button size="sm" onClick={ejecutar} disabled={ejecutando}>
              <Play className="w-4 h-4 inline mr-1" />
              Ejecutar ahora
            </Button>
          )}
        </div>
      </div>

      <div className="p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-lg border border-gray-200 p-4">
            <p className="text-[10px] uppercase font-bold text-gray-400">Programación</p>
            <p className="text-sm font-semibold text-gray-800 mt-1">Diaria a las 02:00 (hora de Colombia)</p>
            <p className="text-xs text-gray-500 mt-1">Con reintentos automáticos ante fallos.</p>
          </div>
          <div className="rounded-lg border border-gray-200 p-4">
            <p className="text-[10px] uppercase font-bold text-gray-400">Última ejecución</p>
            <p className="text-sm font-semibold text-gray-800 mt-1">{ultima ? formatDate(ultima.fecha_inicio) : 'Sin ejecuciones'}</p>
            {ultima && (
              <span className={`inline-flex mt-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${ESTADO_EJECUCION[ultima.estado].className}`}>
                {ESTADO_EJECUCION[ultima.estado].label}
              </span>
            )}
          </div>
          <div className="rounded-lg border border-gray-200 p-4">
            <p className="text-[10px] uppercase font-bold text-gray-400">Resultado de la última</p>
            <p className="text-sm text-gray-800 mt-1">
              {ultima
                ? `${ultima.procesados}/${ultima.total_estudiantes} estudiantes, ${ultima.cambios_riesgo} cambios de riesgo`
                : '—'}
            </p>
            {ultima && (
              <p className="text-xs text-gray-500 mt-1">
                Alertas: {ultima.alertas_generadas} nuevas, {ultima.alertas_actualizadas} actualizadas, {ultima.alertas_cerradas} cerradas
              </p>
            )}
          </div>
        </div>

        {mensaje && <Aviso tipo={mensaje.tipo} texto={mensaje.texto} />}

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {['', 'Inicio', 'Origen', 'Estado', 'Intento', 'Procesados', 'Cambios de riesgo', 'Alertas (nuevas / cerradas)', 'Errores'].map(col => (
                  <th key={col} className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">{col}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                <tr><td colSpan={9} className="px-4 py-6 text-center text-sm text-gray-400 animate-pulse">Cargando ejecuciones...</td></tr>
              ) : ejecuciones.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-6 text-center text-sm text-gray-400">Aún no hay ejecuciones registradas.</td></tr>
              ) : (
                ejecuciones.map(ej => [
                  <tr key={ej.id} onClick={() => verDetalle(ej.id)} className="cursor-pointer hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-400">
                      {detalle?.id === ej.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">{formatDate(ej.fecha_inicio)}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {ej.origen === 'PROGRAMADA' ? 'Programada' : `Manual${ej.usuario ? ` (${ej.usuario})` : ''}`}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${ESTADO_EJECUCION[ej.estado].className}`}>
                        {ESTADO_EJECUCION[ej.estado].label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">{ej.intento}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{ej.procesados}/{ej.total_estudiantes}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{ej.cambios_riesgo}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{ej.alertas_generadas} / {ej.alertas_cerradas}</td>
                    <td className={`px-4 py-3 text-sm ${ej.total_errores > 0 ? 'text-red-600 font-semibold' : 'text-gray-500'}`}>{ej.total_errores}</td>
                  </tr>,
                  detalle?.id === ej.id && (
                    <tr key={`${ej.id}-detalle`} className="bg-gray-50/60">
                      <td colSpan={9} className="px-8 py-4 text-sm text-gray-600 space-y-2">
                        {detalle.mensaje_error && <p className="text-red-600">{detalle.mensaje_error}</p>}
                        <p>
                          <strong>Estudiantes por nivel:</strong>{' '}
                          {Object.entries(detalle.estudiantes_por_nivel || {}).map(([k, v]) => `${k}: ${v}`).join(', ') || '—'}
                        </p>
                        <p><strong>Cambios de riesgo:</strong>{' '}
                          {(detalle.detalle_cambios || []).length === 0
                            ? 'ninguno'
                            : (detalle.detalle_cambios || []).slice(0, 20)
                                .map(c => `${c.codigo} (${c.de} a ${c.a})`).join(', ')}
                        </p>
                        {(detalle.errores || []).length > 0 && (
                          <p className="text-red-600"><strong>Errores:</strong>{' '}
                            {(detalle.errores || []).slice(0, 10).map(e => `${e.codigo ?? ''} ${e.error ?? ''}`.trim()).join('; ')}
                          </p>
                        )}
                      </td>
                    </tr>
                  ),
                ])
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function RecordatoriosSeguimiento() {
  const [config, setConfig] = useState<ConfigRecordatorios | null>(null);
  const [form, setForm] = useState<ConfigRecordatorios | null>(null);
  const [recordatorios, setRecordatorios] = useState<Recordatorio[]>([]);
  const [casos, setCasos] = useState<CasoSinSeguimiento[]>([]);
  const [estadoFiltro, setEstadoFiltro] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);

  const cargar = async () => {
    try {
      const q = estadoFiltro ? `&estado=${estadoFiltro}` : '';
      const [cRes, rRes, sRes] = await Promise.all([
        apiFetch(`${baseUrl}/api/alertas/recordatorios/configuracion/`),
        apiFetch(`${baseUrl}/api/alertas/recordatorios/?limite=50${q}`),
        apiFetch(`${baseUrl}/api/alertas/recordatorios/casos-sin-seguimiento/`),
      ]);
      if (!cRes.ok || !rRes.ok || !sRes.ok) throw new Error('No se pudieron cargar los recordatorios.');
      const c = await cRes.json();
      setConfig(c);
      setForm(c);
      setRecordatorios((await rRes.json()).recordatorios || []);
      setCasos((await sRes.json()).casos || []);
    } catch (err: any) {
      setMensaje({ tipo: 'error', texto: err.message });
    }
  };

  useEffect(() => { cargar(); }, [estadoFiltro]);

  const guardar = async () => {
    if (!form) return;
    setGuardando(true);
    setMensaje(null);
    try {
      const res = await apiFetch(`${baseUrl}/api/alertas/recordatorios/configuracion/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          activo: form.activo,
          dias_inactividad_alerta: Number(form.dias_inactividad_alerta),
          dias_inactividad_intervencion: Number(form.dias_inactividad_intervencion),
          dias_entre_recordatorios: Number(form.dias_entre_recordatorios),
          max_intentos: Number(form.max_intentos),
          roles_destinatarios: form.roles_destinatarios,
          notificar_responsable: form.notificar_responsable,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'No se pudo guardar la configuración.');
      setConfig(data);
      setForm(data);
      setMensaje({ tipo: 'ok', texto: 'Configuración guardada.' });
      cargar();
    } catch (err: any) {
      setMensaje({ tipo: 'error', texto: err.message });
    } finally {
      setGuardando(false);
    }
  };

  const enviarAhora = async () => {
    setMensaje(null);
    const res = await apiFetch(`${baseUrl}/api/alertas/recordatorios/ejecutar/`, { method: 'POST' });
    const data = await res.json();
    setMensaje(res.ok ? { tipo: 'ok', texto: data.mensaje } : { tipo: 'error', texto: data.error || 'No se pudo iniciar el envío.' });
    if (res.ok) setTimeout(cargar, 1500);
  };

  const campoNumero = (campo: keyof ConfigRecordatorios, label: string, max = 365) => (
    <label className="flex flex-col gap-1 text-xs font-medium text-gray-500">
      {label}
      <input
        type="number"
        min={1}
        max={max}
        value={form ? String(form[campo]) : ''}
        onChange={e => form && setForm({ ...form, [campo]: e.target.value === '' ? '' : Number(e.target.value) } as ConfigRecordatorios)}
        className="px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white text-gray-800 w-full"
      />
    </label>
  );

  return (
    <section className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      <div className="bg-gray-700 px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
          <BellRing className="w-4 h-4 text-white" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-white">Recordatorios de casos sin seguimiento</h2>
          <p className="text-xs text-gray-400">
            Avisa sobre alertas e intervenciones inactivas; se cancelan al registrar seguimiento (HU-30)
          </p>
        </div>
        <div className="ml-auto">
          <Button size="sm" onClick={enviarAhora}>
            <Play className="w-4 h-4 inline mr-1" />
            Enviar ahora
          </Button>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {mensaje && <Aviso tipo={mensaje.tipo} texto={mensaje.texto} />}

        {form && (
          <div className="rounded-lg border border-gray-200 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-gray-800">Configuración</p>
              <p className="text-xs text-gray-400">
                Última actualización: {formatDate(config?.fecha_actualizacion ?? null)}
                {config?.actualizado_por ? ` por ${config.actualizado_por}` : ''}
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {campoNumero('dias_inactividad_alerta', 'Días sin intervención (alerta)')}
              {campoNumero('dias_inactividad_intervencion', 'Días sin seguimiento (intervención)')}
              {campoNumero('dias_entre_recordatorios', 'Días entre recordatorios')}
              {campoNumero('max_intentos', 'Máximo de reintentos', 10)}
            </div>
            <div className="flex flex-wrap items-center gap-6 text-sm text-gray-700">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={form.activo} onChange={e => setForm({ ...form, activo: e.target.checked })} />
                Recordatorios activos
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.notificar_responsable}
                  onChange={e => setForm({ ...form, notificar_responsable: e.target.checked })}
                />
                Notificar al responsable de la intervención
              </label>
              <span className="text-xs text-gray-500">Roles destinatarios:</span>
              {ROLES.map(rol => (
                <label key={rol} className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={form.roles_destinatarios.includes(rol)}
                    onChange={e => setForm({
                      ...form,
                      roles_destinatarios: e.target.checked
                        ? [...form.roles_destinatarios, rol]
                        : form.roles_destinatarios.filter(r => r !== rol),
                    })}
                  />
                  {rol}
                </label>
              ))}
            </div>
            <div className="flex justify-end">
              <Button size="sm" onClick={guardar} disabled={guardando}>
                <Save className="w-4 h-4 inline mr-1" />
                Guardar configuración
              </Button>
            </div>
          </div>
        )}

        <div>
          <p className="text-sm font-semibold text-gray-800 mb-2">Casos sin seguimiento ({casos.length})</p>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {['Tipo', 'Estudiante', 'Regla', 'Responsable', 'Días inactivo'].map(col => (
                    <th key={col} className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {casos.length === 0 ? (
                  <tr><td colSpan={5} className="px-4 py-4 text-center text-sm text-gray-400">No hay casos sin seguimiento.</td></tr>
                ) : casos.slice(0, 20).map(c => (
                  <tr key={`${c.tipo_caso}-${c.alerta_id}`}>
                    <td className="px-4 py-2 text-sm text-gray-500">{c.tipo_caso === 'ALERTA' ? 'Alerta' : 'Intervención'}</td>
                    <td className="px-4 py-2 text-sm text-gray-800">{c.estudiante.nombre} <span className="text-xs text-gray-400">{c.estudiante.codigo}</span></td>
                    <td className="px-4 py-2 text-sm text-gray-500">{c.regla}</td>
                    <td className="px-4 py-2 text-sm text-gray-500">{c.responsable ?? '—'}</td>
                    <td className="px-4 py-2 text-sm font-semibold text-gray-800">{c.dias_inactivo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold text-gray-800">Recordatorios enviados</p>
            <select
              value={estadoFiltro}
              onChange={e => setEstadoFiltro(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white text-gray-800"
            >
              <option value="">Todos los estados</option>
              {Object.entries(ESTADO_RECORDATORIO).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {['Fecha', 'Tipo', 'Estudiante', 'Destinatario', 'Estado', 'Intentos', 'Detalle'].map(col => (
                    <th key={col} className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {recordatorios.length === 0 ? (
                  <tr><td colSpan={7} className="px-4 py-4 text-center text-sm text-gray-400">No hay recordatorios registrados.</td></tr>
                ) : recordatorios.map(r => (
                  <tr key={r.id}>
                    <td className="px-4 py-2 text-sm text-gray-600">{formatDate(r.fecha_creacion)}</td>
                    <td className="px-4 py-2 text-sm text-gray-500">{r.tipo_caso === 'ALERTA' ? 'Alerta' : 'Intervención'}</td>
                    <td className="px-4 py-2 text-sm text-gray-800">{r.estudiante.nombre}</td>
                    <td className="px-4 py-2 text-sm text-gray-500">{r.destinatario.nombre} ({r.destinatario.rol})</td>
                    <td className="px-4 py-2">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${ESTADO_RECORDATORIO[r.estado].className}`}>
                        {ESTADO_RECORDATORIO[r.estado].label}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-500">{r.intentos}/{r.max_intentos}</td>
                    <td className="px-4 py-2 text-xs text-gray-500">{r.motivo_cancelacion || r.ultimo_error || `${r.dias_inactivo} días sin seguimiento`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function AutomaticProcesses() {
  const puedeEjecutarReevaluacion = rolActual().includes('ADMINISTRADOR');

  return (
    <div className="space-y-6">
      <div className="border-l-4 border-[#C8102E] pl-4">
        <h1 className="text-2xl font-bold text-gray-900">Procesos automáticos</h1>
        <p className="text-sm text-gray-600 mt-1">
          Re-evaluación periódica del riesgo y recordatorios de casos sin seguimiento
        </p>
      </div>
      <ReevaluacionPeriodica puedeEjecutar={puedeEjecutarReevaluacion} />
      <RecordatoriosSeguimiento />
    </div>
  );
}
