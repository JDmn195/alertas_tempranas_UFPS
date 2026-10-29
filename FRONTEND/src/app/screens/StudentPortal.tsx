import { useEffect, useState } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from 'recharts';
import {
  AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, Bell, BookOpen, CheckCircle2, ChevronRight, Clock,
  GraduationCap, HeartHandshake, Info, Lightbulb, LineChart as IconoLinea, MessageSquarePlus, SearchX, Send,
  TrendingUp, XCircle,
} from 'lucide-react';
import { apiFetch } from '../../services/apiFetch';
import { type ChartConfig, ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from '../components/ui/chart';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';

const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

type Nivel = 'high' | 'medium' | 'low';

interface Causa {
  regla: string;
  tipo: 'PROMEDIO' | 'REPROBACION' | 'ATRASO' | 'INASISTENCIA' | null;
  nivel: Nivel;
  valor: number | null;
  operador: string | null;
  umbral: number | null;
  materias?: { materia: string; porcentaje: number | null; umbral: number | null }[];
}

interface RiesgoPropio {
  estudiante: { codigo: string; nombre: string; semestre: number };
  riesgo: {
    nivel: Nivel | null;
    nivel_texto: string | null;
    periodo: string | null;
    fecha_calculo: string | null;
    mensaje: string | null;
  };
  causas: Causa[];
  indicadores: {
    pps: number | null;
    periodo_pps: string | null;
    ppa: number | null;
    materias_reprobadas: number | null;
    lista_materias_reprobadas: string[];
    creditos_aprobados: number;
  };
}

interface PuntoEvolucion {
  periodo: string;
  pps: number;
  ppa: number;
  creditos_cursados: number;
  creditos_aprobados: number;
}

interface Evolucion {
  serie: PuntoEvolucion[];
  promedio_actual: number | null;
  variacion: { valor: number; porcentaje: number } | null;
  tendencia: 'sube' | 'baja' | 'estable' | null;
  historia_suficiente: boolean;
  mensaje: string | null;
}

type EstadoAlerta = 'activa' | 'en_seguimiento' | 'atendida' | 'cerrada';

interface AlertaPortal {
  id: number;
  tipo: string;
  categoria: 'PROMEDIO' | 'REPROBACION' | 'ATRASO' | 'CORTE' | 'INASISTENCIA';
  origen: 'general' | 'corte' | 'inasistencia';
  severidad: Nivel;
  severidad_texto: string;
  estado: EstadoAlerta;
  estado_texto: string;
  fecha_generacion: string;
  fecha_cierre: string | null;
  cierre_automatico: boolean;
  periodo: string | null;
  materia: string | null;
  resumen: string;
}

interface DetalleAlerta extends AlertaPortal {
  explicacion: {
    mensaje: string;
    recomendacion: string;
    datos: { etiqueta: string; valor: string }[];
  };
  cierre: { automatico: boolean; motivo: string | null; fecha: string | null; mensaje: string } | null;
  intervenciones: IntervencionPortal[];
}

type EstadoIntervencion = 'en_curso' | 'concluida';

interface IntervencionPortal {
  id: number;
  tipo: 'TUTORIA' | 'CITACION' | 'REMISION';
  tipo_texto: string;
  fecha: string;
  estado: EstadoIntervencion;
  estado_texto: string;
  resultado: string | null;
  responsable: string | null;
  alerta: { id: number; tipo: string; materia: string | null; periodo: string | null };
}

interface ListadoIntervenciones {
  intervenciones: IntervencionPortal[];
  conteos: Record<EstadoIntervencion | 'total', number>;
  periodos: string[];
  mensaje: string | null;
}

interface ListadoAlertas {
  alertas: AlertaPortal[];
  conteos: Record<EstadoAlerta | 'total', number>;
  periodos: string[];
  mensaje: string | null;
}

type EstadoSolicitud = 'PENDIENTE' | 'EN_ATENCION' | 'ATENDIDA' | 'CANCELADA';

interface SolicitudPortal {
  id: number;
  motivo: string;
  motivo_texto: string;
  descripcion: string;
  alerta: IntervencionPortal['alerta'] | null;
  estado: EstadoSolicitud;
  estado_texto: string;
  respuesta: string | null;
  responsable: string | null;
  fecha_solicitud: string;
  fecha_atencion: string | null;
  fecha_actualizacion: string;
  puede_cancelar: boolean;
}

interface ListadoSolicitudes {
  solicitudes: SolicitudPortal[];
  en_curso: number | null;
  puede_solicitar: boolean;
  mensaje_bloqueo: string | null;
  motivos: { valor: string; texto: string }[];
  descripcion_minima: number;
}

const NOTA_APROBATORIA = 3.0;

const ESTILO_NIVEL: Record<Nivel, { tarjeta: string; texto: string; icono: string; consejo: string }> = {
  high: {
    tarjeta: 'bg-red-50 border-red-200',
    texto: 'text-red-700',
    icono: 'text-red-500',
    consejo: 'Tu situación académica necesita atención. Te recomendamos acercarte a Bienestar Universitario o a la dirección de tu programa para recibir acompañamiento.',
  },
  medium: {
    tarjeta: 'bg-yellow-50 border-yellow-200',
    texto: 'text-yellow-700',
    icono: 'text-yellow-500',
    consejo: 'Hay aspectos de tu rendimiento que conviene revisar. Estás a tiempo de mejorar: organiza tu semestre y busca apoyo si lo necesitas.',
  },
  low: {
    tarjeta: 'bg-green-50 border-green-200',
    texto: 'text-green-700',
    icono: 'text-green-500',
    consejo: 'Vas por buen camino. Sigue así y revisa tu situación periódicamente.',
  },
};

const OPERADOR_TEXTO: Record<string, string> = {
  '<': 'menor que',
  '<=': 'menor o igual a',
  '>': 'mayor que',
  '>=': 'mayor o igual a',
  '==': 'igual a',
};

const numero = (valor: number | null | undefined, decimales = 2) =>
  valor === null || valor === undefined ? '—' : Number(valor).toFixed(decimales);

/** Explicación en lenguaje claro de por qué se activó la regla. */
function explicarCausa(causa: Causa): string {
  const condicion = causa.operador && causa.umbral !== null
    ? `${OPERADOR_TEXTO[causa.operador] ?? causa.operador} ${causa.tipo === 'PROMEDIO' ? numero(causa.umbral) : numero(causa.umbral, 0)}`
    : null;
  const valorEntero = numero(causa.valor, 0);

  switch (causa.tipo) {
    case 'PROMEDIO':
      return `Tu promedio acumulado (PPA) es ${numero(causa.valor)}. Esta situación se considera de riesgo cuando el promedio es ${condicion ?? 'inferior al mínimo esperado'}.`;
    case 'REPROBACION':
      return `Tienes ${valorEntero} ${causa.valor === 1 ? 'materia perdida que aún no has aprobado' : 'materias perdidas que aún no has aprobado'}. Se considera riesgo cuando la cantidad es ${condicion ?? 'alta'}.`;
    case 'ATRASO':
      return `Tienes ${valorEntero} ${causa.valor === 1 ? 'materia' : 'materias'} de semestres anteriores pendientes por aprobar. Se considera riesgo cuando la cantidad es ${condicion ?? 'alta'}.`;
    case 'INASISTENCIA':
      return `Tus faltas sin justificar llegan al ${numero(causa.valor, 1)}% de las clases en al menos una materia, por encima del máximo permitido${causa.umbral !== null ? ` (${numero(causa.umbral, 1)}%)` : ''}.`;
    default:
      return 'Esta regla se cumplió con tu información académica actual.';
  }
}

function TarjetaRiesgo({ datos }: { datos: RiesgoPropio }) {
  const { riesgo } = datos;

  if (!riesgo.nivel) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 flex items-start gap-4">
        <Info className="w-8 h-8 text-gray-400 shrink-0" />
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Nivel de riesgo académico</h2>
          <p className="text-sm text-gray-600 mt-1">{riesgo.mensaje}</p>
        </div>
      </div>
    );
  }

  const estilo = ESTILO_NIVEL[riesgo.nivel];
  return (
    <div className={`rounded-xl border shadow-sm p-6 ${estilo.tarjeta}`}>
      <div className="flex items-start gap-4">
        <AlertTriangle className={`w-10 h-10 shrink-0 ${estilo.icono}`} />
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600">Tu nivel de riesgo académico actual</p>
          <p className={`text-3xl font-bold mt-1 ${estilo.texto}`}>{riesgo.nivel_texto?.toUpperCase()}</p>
          <p className="text-xs text-gray-500 mt-2">
            {riesgo.periodo && <>Periodo {riesgo.periodo} · </>}
            {riesgo.fecha_calculo && <>Calculado el {new Date(riesgo.fecha_calculo).toLocaleString('es-CO', { dateStyle: 'long', timeStyle: 'short' })}</>}
          </p>
          <p className="text-sm text-gray-700 mt-4">{estilo.consejo}</p>
        </div>
      </div>
    </div>
  );
}

function Causas({ causas, nivel }: { causas: Causa[]; nivel: Nivel | null }) {
  if (!nivel) return null;
  return (
    <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-900">¿Por qué tengo este nivel?</h2>
      {causas.length === 0 ? (
        <p className="text-sm text-gray-600 mt-3 flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-green-500" />
          No se cumple ninguna de las condiciones de riesgo con tu información académica actual.
        </p>
      ) : (
        <ul className="mt-4 space-y-4">
          {causas.map((causa, i) => (
            <li key={`${causa.regla}-${i}`} className="border border-gray-100 rounded-lg p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="font-medium text-gray-900">{causa.regla}</p>
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${ESTILO_NIVEL[causa.nivel]?.tarjeta ?? ''} ${ESTILO_NIVEL[causa.nivel]?.texto ?? ''}`}>
                  Riesgo {causa.nivel === 'high' ? 'alto' : causa.nivel === 'medium' ? 'medio' : 'bajo'}
                </span>
              </div>
              <p className="text-sm text-gray-600 mt-2">{explicarCausa(causa)}</p>
              {causa.materias && causa.materias.length > 0 && (
                <ul className="mt-2 text-sm text-gray-600 list-disc list-inside">
                  {causa.materias.map((m) => (
                    <li key={m.materia}>
                      {m.materia}: {numero(m.porcentaje, 1)}% de inasistencia (máximo {numero(m.umbral, 1)}%)
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Indicadores({ indicadores }: { indicadores: RiesgoPropio['indicadores'] }) {
  const tarjetas = [
    {
      titulo: 'Promedio del semestre (PPS)',
      valor: numero(indicadores.pps),
      detalle: indicadores.periodo_pps ? `Periodo ${indicadores.periodo_pps}` : 'Sin notas definitivas',
      icono: TrendingUp,
    },
    { titulo: 'Promedio acumulado (PPA)', valor: numero(indicadores.ppa), detalle: 'Toda tu carrera', icono: GraduationCap },
    {
      titulo: 'Materias perdidas por aprobar',
      valor: indicadores.materias_reprobadas ?? '—',
      detalle: indicadores.lista_materias_reprobadas.join(', ') || 'Ninguna',
      icono: XCircle,
    },
    { titulo: 'Créditos aprobados', valor: indicadores.creditos_aprobados, detalle: 'Materias aprobadas', icono: BookOpen },
  ];

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-900 mb-3">Mis indicadores</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {tarjetas.map(({ titulo, valor, detalle, icono: Icono }) => (
          <div key={titulo} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
            <div className="flex items-center gap-2 text-gray-500">
              <Icono className="w-4 h-4" />
              <p className="text-xs font-medium">{titulo}</p>
            </div>
            <p className="text-2xl font-bold text-gray-900 mt-2">{valor}</p>
            <p className="text-xs text-gray-500 mt-1 truncate" title={detalle}>{detalle}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

const configGrafica = {
  pps: { label: 'Promedio del semestre (PPS)', color: '#2563eb' },
  ppa: { label: 'Promedio acumulado (PPA)', color: '#C8102E' },
} satisfies ChartConfig;

const TENDENCIA: Record<NonNullable<Evolucion['tendencia']>, { icono: React.ElementType; color: string; verbo: string }> = {
  sube: { icono: ArrowUpRight, color: 'text-green-700 bg-green-50 border-green-200', verbo: 'subió' },
  baja: { icono: ArrowDownRight, color: 'text-red-700 bg-red-50 border-red-200', verbo: 'bajó' },
  estable: { icono: ArrowRight, color: 'text-gray-700 bg-gray-50 border-gray-200', verbo: 'se mantuvo estable' },
};

function FraseTendencia({ evolucion }: { evolucion: Evolucion }) {
  if (!evolucion.tendencia || !evolucion.variacion) return null;
  const { icono: Icono, color, verbo } = TENDENCIA[evolucion.tendencia];
  const { valor, porcentaje } = evolucion.variacion;
  const cambio = evolucion.tendencia === 'estable'
    ? ''
    : ` ${Math.abs(valor).toFixed(2)} puntos (${porcentaje.toFixed(1)} %)`;
  return (
    <p className={`flex items-center gap-2 text-sm border rounded-lg px-3 py-2 ${color}`}>
      <Icono className="w-4 h-4 shrink-0" />
      Tu promedio acumulado {verbo}{cambio} respecto al periodo anterior y hoy es {numero(evolucion.promedio_actual)}.
    </p>
  );
}

function TablaEvolucion({ serie }: { serie: PuntoEvolucion[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Periodo</TableHead>
          <TableHead className="text-right">PPS</TableHead>
          <TableHead className="text-right">PPA</TableHead>
          <TableHead className="text-right">Créditos cursados</TableHead>
          <TableHead className="text-right">Créditos aprobados</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {serie.map((p) => (
          <TableRow key={p.periodo}>
            <TableCell className="font-medium">{p.periodo}</TableCell>
            <TableCell className={`text-right ${p.pps < NOTA_APROBATORIA ? 'text-red-600 font-semibold' : ''}`}>{numero(p.pps)}</TableCell>
            <TableCell className={`text-right ${p.ppa < NOTA_APROBATORIA ? 'text-red-600 font-semibold' : ''}`}>{numero(p.ppa)}</TableCell>
            <TableCell className="text-right">{p.creditos_cursados}</TableCell>
            <TableCell className="text-right">{p.creditos_aprobados}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** HU-38: evolución del PPS y el PPA por periodo. */
function EvolucionAcademica() {
  const [evolucion, setEvolucion] = useState<Evolucion | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let activo = true;
    apiFetch(`${baseUrl}/api/portal/evolucion/`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || 'No fue posible consultar tu evolución académica.');
        if (activo) setEvolucion(json);
      })
      .catch((e: Error) => activo && setError(e.message));
    return () => {
      activo = false;
    };
  }, []);

  let contenido: React.ReactNode;
  if (error) {
    contenido = <p role="alert" className="text-sm text-red-700">{error}</p>;
  } else if (!evolucion) {
    contenido = <p className="text-sm text-gray-500">Cargando tu evolución…</p>;
  } else if (evolucion.serie.length === 0) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-10 border-2 border-dashed border-gray-100 rounded-xl text-gray-500">
        <IconoLinea className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-sm">{evolucion.mensaje}</p>
      </div>
    );
  } else if (!evolucion.historia_suficiente) {
    const [unico] = evolucion.serie;
    contenido = (
      <div className="space-y-4">
        <p className="flex items-start gap-2 text-sm text-gray-600 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
          <Info className="w-4 h-4 mt-0.5 shrink-0 text-gray-400" />
          {evolucion.mensaje}
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            ['Periodo', unico.periodo],
            ['PPS', numero(unico.pps)],
            ['PPA', numero(unico.ppa)],
            ['Créditos aprobados', `${unico.creditos_aprobados} de ${unico.creditos_cursados}`],
          ].map(([titulo, valor]) => (
            <div key={titulo} className="border border-gray-100 rounded-lg p-3">
              <p className="text-xs text-gray-500">{titulo}</p>
              <p className="text-lg font-bold text-gray-900">{valor}</p>
            </div>
          ))}
        </div>
      </div>
    );
  } else {
    contenido = (
      <div className="space-y-5">
        <ChartContainer config={configGrafica} className="aspect-auto h-72 w-full">
          <LineChart data={evolucion.serie} margin={{ top: 10, right: 16, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="periodo" tickLine={false} axisLine={false} dy={8} />
            <YAxis domain={[0, 5]} ticks={[0, 1, 2, 3, 4, 5]} tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            <ReferenceLine
              y={NOTA_APROBATORIA}
              stroke="#9ca3af"
              strokeDasharray="4 4"
              label={{ value: 'Nota aprobatoria (3.0)', position: 'insideBottomRight', fontSize: 11, fill: '#6b7280' }}
            />
            <Line type="monotone" dataKey="pps" stroke="var(--color-pps)" strokeWidth={2} dot={{ r: 4 }} />
            <Line type="monotone" dataKey="ppa" stroke="var(--color-ppa)" strokeWidth={3} dot={{ r: 4 }} />
          </LineChart>
        </ChartContainer>
        <FraseTendencia evolucion={evolucion} />
        <TablaEvolucion serie={evolucion.serie} />
      </div>
    );
  }

  return (
    <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-900">Mi evolución académica</h2>
      <p className="text-sm text-gray-500 mb-4">
        Tu promedio de cada semestre (PPS) y tu promedio acumulado (PPA). Los semestres con materias aún en curso
        aparecen cuando tienen notas definitivas.
      </p>
      {contenido}
    </section>
  );
}

const INSIGNIA_SEVERIDAD: Record<Nivel, string> = {
  high: 'bg-red-50 text-red-700 border-red-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-blue-50 text-blue-700 border-blue-200',
};

const INSIGNIA_ESTADO: Record<EstadoAlerta, string> = {
  activa: 'bg-orange-50 text-orange-700',
  en_seguimiento: 'bg-indigo-50 text-indigo-700',
  atendida: 'bg-green-50 text-green-700',
  cerrada: 'bg-gray-100 text-gray-600',
};

const OPCIONES_ESTADO: { valor: EstadoAlerta; texto: string }[] = [
  { valor: 'activa', texto: 'Activas' },
  { valor: 'en_seguimiento', texto: 'En seguimiento' },
  { valor: 'atendida', texto: 'Atendidas' },
  { valor: 'cerrada', texto: 'Cerradas' },
];

const fecha = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString('es-CO', { dateStyle: 'long' }) : '—';

function InsigniaSeveridad({ alerta }: { alerta: AlertaPortal }) {
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${INSIGNIA_SEVERIDAD[alerta.severidad] ?? ''}`}>
      Severidad {alerta.severidad_texto.toLowerCase()}
    </span>
  );
}

function InsigniaEstado({ alerta }: { alerta: AlertaPortal }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${INSIGNIA_ESTADO[alerta.estado] ?? 'bg-gray-100 text-gray-600'}`}>
      {alerta.estado_texto}
    </span>
  );
}

function ModalAlerta({ alertaId, onCerrar }: { alertaId: number | null; onCerrar: () => void }) {
  const [detalle, setDetalle] = useState<DetalleAlerta | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (alertaId === null) return;
    let activo = true;
    setDetalle(null);
    setError(null);
    apiFetch(`${baseUrl}/api/portal/alertas/${alertaId}/`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || 'No fue posible consultar la alerta.');
        if (activo) setDetalle(json);
      })
      .catch((e: Error) => activo && setError(e.message));
    return () => {
      activo = false;
    };
  }, [alertaId]);

  let contenido: React.ReactNode;
  if (error) {
    contenido = (
      <>
        <DialogHeader>
          <DialogTitle>Detalle de la alerta</DialogTitle>
        </DialogHeader>
        <p role="alert" className="text-sm text-red-700">{error}</p>
      </>
    );
  } else if (!detalle) {
    contenido = (
      <DialogHeader>
        <DialogTitle>Detalle de la alerta</DialogTitle>
        <DialogDescription>Cargando…</DialogDescription>
      </DialogHeader>
    );
  } else {
    contenido = (
      <>
        <DialogHeader>
          <DialogTitle className="pr-6">{detalle.tipo}</DialogTitle>
          <DialogDescription>{detalle.resumen}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center gap-2">
          <InsigniaSeveridad alerta={detalle} />
          <InsigniaEstado alerta={detalle} />
        </div>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs text-gray-500">Registrada el</dt>
            <dd className="text-gray-900">{fecha(detalle.fecha_generacion)}</dd>
          </div>
          {detalle.estado === 'cerrada' && (
            <div>
              <dt className="text-xs text-gray-500">Cerrada el</dt>
              <dd className="text-gray-900">{detalle.fecha_cierre ? fecha(detalle.fecha_cierre) : 'Fecha no registrada'}</dd>
            </div>
          )}
        </dl>

        <section>
          <h3 className="text-sm font-semibold text-gray-900 mb-1">¿Qué significa?</h3>
          <p className="text-sm text-gray-700">{detalle.explicacion.mensaje}</p>
        </section>

        {detalle.explicacion.datos.length > 0 && (
          <dl className="border border-gray-100 rounded-lg divide-y divide-gray-100 text-sm">
            {detalle.explicacion.datos.map((d) => (
              <div key={d.etiqueta} className="flex justify-between gap-4 px-3 py-2">
                <dt className="text-gray-500">{d.etiqueta}</dt>
                <dd className="text-gray-900 font-medium text-right">{d.valor}</dd>
              </div>
            ))}
          </dl>
        )}

        {detalle.intervenciones.length > 0 && (
          <p className="flex items-start gap-2 text-sm text-gray-700">
            <HeartHandshake className="w-4 h-4 mt-0.5 shrink-0 text-[#C8102E]" />
            <span>
              {detalle.intervenciones.length === 1
                ? 'Se ha registrado 1 acompañamiento sobre esta alerta.'
                : `Se han registrado ${detalle.intervenciones.length} acompañamientos sobre esta alerta.`}{' '}
              Puedes verlos en «Mi acompañamiento».
            </span>
          </p>
        )}

        {detalle.cierre ? (
          <p className="flex items-start gap-2 text-sm text-green-800 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
            <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{detalle.cierre.mensaje} Los datos corresponden al último registro de la alerta.</span>
          </p>
        ) : (
          <p className="flex items-start gap-2 text-sm text-blue-800 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
            <Lightbulb className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{detalle.explicacion.recomendacion}</span>
          </p>
        )}
      </>
    );
  }

  return (
    <Dialog open={alertaId !== null} onOpenChange={(abierto) => !abierto && onCerrar()}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">{contenido}</DialogContent>
    </Dialog>
  );
}

/** HU-39: alertas registradas sobre la situación académica del estudiante. */
function MisAlertas() {
  const [listado, setListado] = useState<ListadoAlertas | null>(null);
  const [estado, setEstado] = useState('');
  const [periodo, setPeriodo] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [seleccionada, setSeleccionada] = useState<number | null>(null);

  useEffect(() => {
    let activo = true;
    const params = new URLSearchParams();
    if (estado) params.set('estado', estado);
    if (periodo) params.set('periodo', periodo);
    const query = params.toString();
    setError(null);
    apiFetch(`${baseUrl}/api/portal/alertas/${query ? `?${query}` : ''}`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || 'No fue posible consultar tus alertas.');
        if (activo) setListado(json);
      })
      .catch((e: Error) => activo && setError(e.message));
    return () => {
      activo = false;
    };
  }, [estado, periodo]);

  const quitarFiltros = () => {
    setEstado('');
    setPeriodo('');
  };
  const claseSelect = 'px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] bg-white text-sm';

  let contenido: React.ReactNode;
  if (error) {
    contenido = <p role="alert" className="text-sm text-red-700">{error}</p>;
  } else if (!listado) {
    contenido = <p className="text-sm text-gray-500">Cargando tus alertas…</p>;
  } else if (listado.conteos.total === 0) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-10 border-2 border-dashed border-gray-100 rounded-xl text-gray-500">
        <CheckCircle2 className="w-8 h-8 mb-2 text-green-500 opacity-70" />
        <p className="text-sm">No tienes alertas registradas sobre tu situación académica.</p>
        <p className="text-xs mt-1">Si en algún momento se registra una, aquí verás qué la originó y cómo mejorar.</p>
      </div>
    );
  } else if (listado.alertas.length === 0) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-10 border-2 border-dashed border-gray-100 rounded-xl text-gray-500">
        <SearchX className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-sm">Ninguna alerta coincide con los filtros seleccionados.</p>
        <button type="button" onClick={quitarFiltros} className="mt-3 text-sm font-medium text-[#C8102E] hover:underline">
          Quitar filtros
        </button>
      </div>
    );
  } else {
    contenido = (
      <ul className="divide-y divide-gray-100 border border-gray-100 rounded-lg">
        {listado.alertas.map((alerta) => (
          <li key={alerta.id}>
            <button
              type="button"
              onClick={() => setSeleccionada(alerta.id)}
              className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50 focus:outline-none focus:bg-gray-50"
            >
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 truncate">{alerta.tipo}</p>
                <p className="text-xs text-gray-500 truncate">
                  {alerta.resumen} · {fecha(alerta.fecha_generacion)}
                </p>
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  <InsigniaSeveridad alerta={alerta} />
                  <InsigniaEstado alerta={alerta} />
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />
            </button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <div className="flex items-center gap-2">
        <Bell className="w-5 h-5 text-gray-500" />
        <h2 className="text-lg font-semibold text-gray-900">Mis alertas</h2>
      </div>
      <p className="text-sm text-gray-500 mb-4">
        Avisos registrados sobre tu situación académica. Cada uno explica qué lo originó y qué puedes hacer para mejorar.
      </p>

      {listado && listado.conteos.total > 0 && (
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <label className="text-xs text-gray-600">
            <span className="block mb-1">Estado</span>
            <select value={estado} onChange={(e) => setEstado(e.target.value)} className={claseSelect}>
              <option value="">Todos ({listado.conteos.total})</option>
              {OPCIONES_ESTADO.map((o) => (
                <option key={o.valor} value={o.valor}>
                  {o.texto} ({listado.conteos[o.valor]})
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-gray-600">
            <span className="block mb-1">Periodo</span>
            <select value={periodo} onChange={(e) => setPeriodo(e.target.value)} className={claseSelect}>
              <option value="">Todos</option>
              {listado.periodos.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
          {periodo && (
            <p className="text-xs text-gray-500 pb-2">El periodo aplica a las alertas de una materia (cortes e inasistencia).</p>
          )}
          {(estado || periodo) && listado.alertas.length > 0 && (
            <button type="button" onClick={quitarFiltros} className="text-sm font-medium text-[#C8102E] hover:underline pb-2">
              Quitar filtros
            </button>
          )}
        </div>
      )}

      {contenido}
      <ModalAlerta alertaId={seleccionada} onCerrar={() => setSeleccionada(null)} />
    </section>
  );
}

const DESCRIPCION_TIPO: Record<IntervencionPortal['tipo'], string> = {
  TUTORIA: 'Un espacio de apoyo académico para reforzar los temas en los que tienes dificultad.',
  CITACION: 'Un encuentro para conversar sobre tu situación académica y acordar los siguientes pasos.',
  REMISION: 'Tu caso se dirigió a un área de la universidad que puede apoyarte de forma especializada.',
};

const INSIGNIA_ESTADO_INTERVENCION: Record<EstadoIntervencion, string> = {
  en_curso: 'bg-indigo-50 text-indigo-700',
  concluida: 'bg-green-50 text-green-700',
};

const alertaTexto = (alerta: IntervencionPortal['alerta']) =>
  alerta.materia ? `${alerta.tipo} · ${alerta.materia}` : alerta.tipo;

function InsigniaEstadoIntervencion({ intervencion }: { intervencion: IntervencionPortal }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${INSIGNIA_ESTADO_INTERVENCION[intervencion.estado]}`}>
      {intervencion.estado_texto}
    </span>
  );
}

function ModalIntervencion({ intervencionId, onCerrar }: { intervencionId: number | null; onCerrar: () => void }) {
  const [detalle, setDetalle] = useState<IntervencionPortal | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (intervencionId === null) return;
    let activo = true;
    setDetalle(null);
    setError(null);
    apiFetch(`${baseUrl}/api/portal/intervenciones/${intervencionId}/`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || 'No fue posible consultar el acompañamiento.');
        if (activo) setDetalle(json);
      })
      .catch((e: Error) => activo && setError(e.message));
    return () => {
      activo = false;
    };
  }, [intervencionId]);

  let contenido: React.ReactNode;
  if (error) {
    contenido = (
      <>
        <DialogHeader>
          <DialogTitle>Acompañamiento</DialogTitle>
        </DialogHeader>
        <p role="alert" className="text-sm text-red-700">{error}</p>
      </>
    );
  } else if (!detalle) {
    contenido = (
      <DialogHeader>
        <DialogTitle>Acompañamiento</DialogTitle>
        <DialogDescription>Cargando…</DialogDescription>
      </DialogHeader>
    );
  } else {
    contenido = (
      <>
        <DialogHeader>
          <DialogTitle className="pr-6">{detalle.tipo_texto}</DialogTitle>
          <DialogDescription>{DESCRIPCION_TIPO[detalle.tipo] ?? 'Acompañamiento registrado sobre tu caso.'}</DialogDescription>
        </DialogHeader>
        <div>
          <InsigniaEstadoIntervencion intervencion={detalle} />
        </div>
        <dl className="border border-gray-100 rounded-lg divide-y divide-gray-100 text-sm">
          {[
            ['Fecha', fecha(detalle.fecha)],
            ['Responsable', detalle.responsable ?? 'Equipo de acompañamiento'],
            ['Alerta relacionada', alertaTexto(detalle.alerta)],
            ...(detalle.alerta.periodo ? [['Periodo', detalle.alerta.periodo]] : []),
          ].map(([etiqueta, valor]) => (
            <div key={etiqueta} className="flex justify-between gap-4 px-3 py-2">
              <dt className="text-gray-500">{etiqueta}</dt>
              <dd className="text-gray-900 font-medium text-right">{valor}</dd>
            </div>
          ))}
        </dl>
        <section>
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Resultado</h3>
          {detalle.resultado ? (
            <p className="text-sm text-gray-700">{detalle.resultado}</p>
          ) : (
            <p className="text-sm text-gray-500">
              {detalle.estado === 'concluida'
                ? 'Este acompañamiento concluyó sin un resultado registrado.'
                : 'Este acompañamiento sigue en curso. El resultado aparecerá cuando se registre.'}
            </p>
          )}
        </section>
      </>
    );
  }

  return (
    <Dialog open={intervencionId !== null} onOpenChange={(abierto) => !abierto && onCerrar()}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">{contenido}</DialogContent>
    </Dialog>
  );
}

/** HU-40: intervenciones (acompañamiento) registradas sobre las alertas del estudiante. */
function MiAcompanamiento() {
  const [listado, setListado] = useState<ListadoIntervenciones | null>(null);
  const [estado, setEstado] = useState('');
  const [periodo, setPeriodo] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [seleccionada, setSeleccionada] = useState<number | null>(null);

  useEffect(() => {
    let activo = true;
    const params = new URLSearchParams();
    if (estado) params.set('estado', estado);
    if (periodo) params.set('periodo', periodo);
    const query = params.toString();
    setError(null);
    apiFetch(`${baseUrl}/api/portal/intervenciones/${query ? `?${query}` : ''}`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || 'No fue posible consultar tu acompañamiento.');
        if (activo) setListado(json);
      })
      .catch((e: Error) => activo && setError(e.message));
    return () => {
      activo = false;
    };
  }, [estado, periodo]);

  const quitarFiltros = () => {
    setEstado('');
    setPeriodo('');
  };
  const claseSelect = 'px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] bg-white text-sm';

  let contenido: React.ReactNode;
  if (error) {
    contenido = <p role="alert" className="text-sm text-red-700">{error}</p>;
  } else if (!listado) {
    contenido = <p className="text-sm text-gray-500">Cargando tu acompañamiento…</p>;
  } else if (listado.conteos.total === 0) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-10 border-2 border-dashed border-gray-100 rounded-xl text-gray-500">
        <HeartHandshake className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-sm">Aún no hay acompañamientos registrados sobre tu caso.</p>
        <p className="text-xs mt-1">
          Cuando un docente o Bienestar Universitario realice una tutoría, citación o remisión, la verás aquí.
        </p>
      </div>
    );
  } else if (listado.intervenciones.length === 0) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-10 border-2 border-dashed border-gray-100 rounded-xl text-gray-500">
        <SearchX className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-sm">Ningún acompañamiento coincide con los filtros seleccionados.</p>
        <button type="button" onClick={quitarFiltros} className="mt-3 text-sm font-medium text-[#C8102E] hover:underline">
          Quitar filtros
        </button>
      </div>
    );
  } else {
    contenido = (
      <ol className="relative border-l-2 border-gray-100 ml-3 space-y-4">
        {listado.intervenciones.map((intervencion) => (
          <li key={intervencion.id} className="ml-5">
            <span
              className={`absolute -left-[9px] mt-4 w-4 h-4 rounded-full border-2 border-white ${
                intervencion.estado === 'concluida' ? 'bg-green-500' : 'bg-indigo-500'
              }`}
            />
            <button
              type="button"
              onClick={() => setSeleccionada(intervencion.id)}
              className="w-full text-left border border-gray-100 rounded-lg px-4 py-3 flex items-center gap-3 hover:bg-gray-50 focus:outline-none focus:bg-gray-50"
            >
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium text-gray-900">{intervencion.tipo_texto}</p>
                  <InsigniaEstadoIntervencion intervencion={intervencion} />
                </div>
                <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {fecha(intervencion.fecha)}
                  {intervencion.responsable && <> · {intervencion.responsable}</>}
                </p>
                <p className="text-xs text-gray-500 truncate mt-0.5">Alerta: {alertaTexto(intervencion.alerta)}</p>
              </div>
              <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />
            </button>
          </li>
        ))}
      </ol>
    );
  }

  return (
    <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <div className="flex items-center gap-2">
        <HeartHandshake className="w-5 h-5 text-gray-500" />
        <h2 className="text-lg font-semibold text-gray-900">Mi acompañamiento</h2>
      </div>
      <p className="text-sm text-gray-500 mb-4">
        El seguimiento que la universidad ha dado a tu caso: tutorías, citaciones y remisiones registradas sobre tus
        alertas, con su responsable y su resultado.
      </p>

      {listado && listado.conteos.total > 0 && (
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <label className="text-xs text-gray-600">
            <span className="block mb-1">Estado</span>
            <select value={estado} onChange={(e) => setEstado(e.target.value)} className={claseSelect}>
              <option value="">Todos ({listado.conteos.total})</option>
              <option value="en_curso">En curso ({listado.conteos.en_curso})</option>
              <option value="concluida">Concluidos ({listado.conteos.concluida})</option>
            </select>
          </label>
          <label className="text-xs text-gray-600">
            <span className="block mb-1">Periodo</span>
            <select value={periodo} onChange={(e) => setPeriodo(e.target.value)} className={claseSelect}>
              <option value="">Todos</option>
              {listado.periodos.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
          {periodo && (
            <p className="text-xs text-gray-500 pb-2">El periodo aplica a los acompañamientos de alertas de una materia.</p>
          )}
          {(estado || periodo) && listado.intervenciones.length > 0 && (
            <button type="button" onClick={quitarFiltros} className="text-sm font-medium text-[#C8102E] hover:underline pb-2">
              Quitar filtros
            </button>
          )}
        </div>
      )}

      {contenido}
      <ModalIntervencion intervencionId={seleccionada} onCerrar={() => setSeleccionada(null)} />
    </section>
  );
}

const INSIGNIA_ESTADO_SOLICITUD: Record<EstadoSolicitud, string> = {
  PENDIENTE: 'bg-orange-50 text-orange-700',
  EN_ATENCION: 'bg-indigo-50 text-indigo-700',
  ATENDIDA: 'bg-green-50 text-green-700',
  CANCELADA: 'bg-gray-100 text-gray-600',
};

/** HU-41: formulario para pedir acompañamiento e historial de solicitudes. */
function SolicitarAcompanamiento() {
  const [listado, setListado] = useState<ListadoSolicitudes | null>(null);
  const [alertas, setAlertas] = useState<AlertaPortal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [motivo, setMotivo] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [alerta, setAlerta] = useState('');
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [mensajeEnvio, setMensajeEnvio] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [recarga, setRecarga] = useState(0);

  useEffect(() => {
    let activo = true;
    apiFetch(`${baseUrl}/api/portal/solicitudes/`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || 'No fue posible consultar tus solicitudes.');
        if (activo) setListado(json);
      })
      .catch((e: Error) => activo && setError(e.message));
    return () => {
      activo = false;
    };
  }, [recarga]);

  useEffect(() => {
    // Alertas propias para relacionarlas con la solicitud (opcional); las cerradas no se ofrecen
    apiFetch(`${baseUrl}/api/portal/alertas/`)
      .then(async (res) => (res.ok ? res.json() : { alertas: [] }))
      .then((json: { alertas: AlertaPortal[] }) => setAlertas(json.alertas.filter((a) => a.estado !== 'cerrada')))
      .catch(() => setAlertas([]));
  }, []);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!listado) return;
    const nuevos: Record<string, string> = {};
    if (!motivo) nuevos.motivo = 'Selecciona el motivo de tu solicitud.';
    if (descripcion.trim().length < listado.descripcion_minima) {
      nuevos.descripcion = `Cuéntanos un poco más: escribe al menos ${listado.descripcion_minima} caracteres.`;
    }
    setErrores(nuevos);
    setMensajeEnvio(null);
    if (Object.keys(nuevos).length) return;

    setEnviando(true);
    try {
      const res = await apiFetch(`${baseUrl}/api/portal/solicitudes/`, {
        method: 'POST',
        body: JSON.stringify({ motivo, descripcion: descripcion.trim(), alerta: alerta ? Number(alerta) : null }),
      });
      const json = await res.json();
      if (!res.ok) {
        setErrores(json.detalle || {});
        setMensajeEnvio({ tipo: 'error', texto: json.error || 'No fue posible enviar tu solicitud.' });
        return;
      }
      setMotivo('');
      setDescripcion('');
      setAlerta('');
      setMensajeEnvio({ tipo: 'ok', texto: 'Tu solicitud fue enviada. Bienestar Universitario te responderá pronto.' });
      setRecarga((n) => n + 1);
    } catch {
      setMensajeEnvio({ tipo: 'error', texto: 'No fue posible enviar tu solicitud.' });
    } finally {
      setEnviando(false);
    }
  };

  const cancelar = async (id: number) => {
    if (!window.confirm('¿Quieres cancelar esta solicitud de acompañamiento?')) return;
    try {
      const res = await apiFetch(`${baseUrl}/api/portal/solicitudes/${id}/cancelar/`, { method: 'PATCH' });
      const json = await res.json();
      setMensajeEnvio(res.ok
        ? { tipo: 'ok', texto: 'Cancelaste la solicitud. Puedes enviar una nueva cuando lo necesites.' }
        : { tipo: 'error', texto: json.error || 'No fue posible cancelar la solicitud.' });
    } catch {
      setMensajeEnvio({ tipo: 'error', texto: 'No fue posible cancelar la solicitud.' });
    }
    setRecarga((n) => n + 1);
  };

  const claseCampo = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] bg-white text-sm disabled:bg-gray-50 disabled:text-gray-400';
  const bloqueado = !listado?.puede_solicitar;

  let historial: React.ReactNode;
  if (error) {
    historial = <p role="alert" className="text-sm text-red-700">{error}</p>;
  } else if (!listado) {
    historial = <p className="text-sm text-gray-500">Cargando tus solicitudes…</p>;
  } else if (listado.solicitudes.length === 0) {
    historial = <p className="text-sm text-gray-500">Aún no has enviado solicitudes de acompañamiento.</p>;
  } else {
    historial = (
      <ul className="space-y-3">
        {listado.solicitudes.map((s) => (
          <li key={s.id} className="border border-gray-100 rounded-lg p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-medium text-gray-900">{s.motivo_texto}</p>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${INSIGNIA_ESTADO_SOLICITUD[s.estado]}`}>
                  {s.estado_texto}
                </span>
              </div>
              {s.puede_cancelar && (
                <button type="button" onClick={() => cancelar(s.id)} className="text-sm font-medium text-[#C8102E] hover:underline">
                  Cancelar solicitud
                </button>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Enviada el {fecha(s.fecha_solicitud)}
              {s.responsable && <> · Responsable: {s.responsable}</>}
            </p>
            {s.alerta && <p className="text-xs text-gray-500 mt-0.5">Alerta relacionada: {alertaTexto(s.alerta)}</p>}
            <p className="text-sm text-gray-700 mt-2 whitespace-pre-line">{s.descripcion}</p>
            {s.respuesta ? (
              <div className="mt-3 text-sm bg-green-50 border border-green-200 rounded-lg px-3 py-2 text-green-900">
                <p className="text-xs font-semibold mb-0.5">
                  Respuesta{s.fecha_atencion ? ` · ${fecha(s.fecha_atencion)}` : ''}
                </p>
                <p className="whitespace-pre-line">{s.respuesta}</p>
              </div>
            ) : (
              s.estado !== 'CANCELADA' && (
                <p className="text-xs text-gray-500 mt-2">
                  {s.estado === 'PENDIENTE'
                    ? 'Tu solicitud está a la espera de que Bienestar la tome.'
                    : 'Tu solicitud está siendo atendida. La respuesta aparecerá aquí.'}
                </p>
              )
            )}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <div className="flex items-center gap-2">
        <MessageSquarePlus className="w-5 h-5 text-gray-500" />
        <h2 className="text-lg font-semibold text-gray-900">Solicitar acompañamiento</h2>
      </div>
      <p className="text-sm text-gray-500 mb-4">
        Si necesitas apoyo, cuéntanos qué está pasando. Bienestar Universitario recibirá tu solicitud y te responderá por
        este medio y por correo.
      </p>

      {listado && bloqueado && listado.mensaje_bloqueo && (
        <p className="flex items-start gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4">
          <Info className="w-4 h-4 mt-0.5 shrink-0" />
          {listado.mensaje_bloqueo}
        </p>
      )}

      <form onSubmit={enviar} noValidate className="space-y-4">
        <fieldset disabled={bloqueado || enviando} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="text-sm text-gray-700">
              <span className="block mb-1 font-medium">Motivo *</span>
              <select value={motivo} onChange={(e) => setMotivo(e.target.value)} className={claseCampo}
                aria-invalid={!!errores.motivo}>
                <option value="">Selecciona un motivo</option>
                {listado?.motivos.map((m) => (
                  <option key={m.valor} value={m.valor}>{m.texto}</option>
                ))}
              </select>
              {errores.motivo && <span className="block text-xs text-red-600 mt-1">{errores.motivo}</span>}
            </label>
            <label className="text-sm text-gray-700">
              <span className="block mb-1 font-medium">Alerta relacionada (opcional)</span>
              <select value={alerta} onChange={(e) => setAlerta(e.target.value)} className={claseCampo}>
                <option value="">Ninguna</option>
                {alertas.map((a) => (
                  <option key={a.id} value={a.id}>{a.materia ? `${a.tipo} · ${a.materia}` : a.tipo}</option>
                ))}
              </select>
              {errores.alerta && <span className="block text-xs text-red-600 mt-1">{errores.alerta}</span>}
            </label>
          </div>
          <label className="block text-sm text-gray-700">
            <span className="block mb-1 font-medium">Descripción *</span>
            <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} rows={4} maxLength={2000}
              placeholder="Describe brevemente tu situación y el tipo de apoyo que necesitas."
              className={claseCampo} aria-invalid={!!errores.descripcion} />
            <span className="flex justify-between text-xs mt-1">
              <span className="text-red-600">{errores.descripcion}</span>
              <span className="text-gray-400">{descripcion.trim().length} / mínimo {listado?.descripcion_minima ?? 20}</span>
            </span>
          </label>
          <button type="submit"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#C8102E] text-white text-sm font-medium hover:bg-[#a50d26] disabled:opacity-50">
            <Send className="w-4 h-4" />
            {enviando ? 'Enviando…' : 'Enviar solicitud'}
          </button>
        </fieldset>
      </form>

      {mensajeEnvio && (
        <p role={mensajeEnvio.tipo === 'error' ? 'alert' : 'status'}
          className={`mt-4 text-sm rounded-lg px-3 py-2 border ${mensajeEnvio.tipo === 'ok'
            ? 'text-green-800 bg-green-50 border-green-200' : 'text-red-700 bg-red-50 border-red-200'}`}>
          {mensajeEnvio.texto}
        </p>
      )}

      <h3 className="text-sm font-semibold text-gray-900 mt-6 mb-3">Mis solicitudes</h3>
      {historial}
    </section>
  );
}


/**
 * Portal del estudiante: inicio con su nivel de riesgo actual (HU-37), la
 * evolución de su promedio (HU-38), sus alertas (HU-39), su acompañamiento
 * (HU-40) y la solicitud de acompañamiento (HU-41), siempre con datos de /api/portal/.
 */
export default function StudentPortal() {
  const [datos, setDatos] = useState<RiesgoPropio | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let activo = true;
    apiFetch(`${baseUrl}/api/portal/riesgo/`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || 'No fue posible consultar tu información.');
        if (activo) setDatos(json);
      })
      .catch((e: Error) => activo && setError(e.message));
    return () => {
      activo = false;
    };
  }, []);

  if (error) {
    return (
      <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 text-sm">
        {error}
      </div>
    );
  }

  if (!datos) {
    return <div className="text-sm text-gray-500">Cargando tu información…</div>;
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">Hola, {datos.estudiante.nombre}</h1>
        <p className="text-sm text-gray-500">Código {datos.estudiante.codigo} · Semestre {datos.estudiante.semestre}</p>
      </header>

      <TarjetaRiesgo datos={datos} />
      <Causas causas={datos.causas} nivel={datos.riesgo.nivel} />
      <EvolucionAcademica />
      <MisAlertas />
      <MiAcompanamiento />
      <SolicitarAcompanamiento />
      <Indicadores indicadores={datos.indicadores} />
    </div>
  );
}
