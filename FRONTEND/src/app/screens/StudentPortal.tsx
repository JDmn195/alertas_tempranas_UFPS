import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from 'recharts';
import {
  AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, Bell, BookOpen, CalendarCheck, CheckCircle2, ChevronRight,
  Clock,
  GraduationCap, HeartHandshake, Info, Lightbulb, LineChart as IconoLinea, Loader2, MessageSquarePlus, SearchX, Send,
  TrendingUp, X, XCircle,
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

type EstadoAsistencia = 'ASISTIO' | 'FALTA' | 'FALTA_JUSTIFICADA';

interface CursoAsistencia {
  curso_id: number;
  materia: string;
  codigo_materia: string;
  grupo: string;
  total_clases: number;
  asistencias: number;
  faltas: number;
  faltas_justificadas: number;
  porcentaje: number | null;
  umbral: number | null;
  umbral_aviso: number | null;
  cerca_del_limite: boolean;
  supera_umbral: boolean;
  detalle: { fecha: string; estado: EstadoAsistencia; estado_texto: string }[];
}

interface AsistenciaPropia {
  periodo: string | null;
  periodos: string[];
  cursos: CursoAsistencia[];
  hay_registros: boolean;
  mensaje: string | null;
}

const NOTA_APROBATORIA = 3.0;

const ESTILO_NIVEL: Record<Nivel, { tarjeta: string; texto: string; icono: string; consejo: string; fondo: string; insignia: string; paso: string | null; pasoRuta: string; pasoBoton: string }> = {
  high: {
    tarjeta: 'bg-red-50 border-red-200',
    texto: 'text-red-700',
    icono: 'text-red-500',
    consejo: 'Tu situación académica necesita atención. Te recomendamos acercarte a Bienestar Universitario o a la dirección de tu programa para recibir acompañamiento.',
    fondo: 'from-[#FEF3F4] via-white to-white border-primary-tint',
    insignia: 'bg-primary text-white',
    paso: 'Tu siguiente paso: pide acompañamiento. Es gratis, confidencial y toma un minuto.',
    pasoRuta: '/dashboard/portal/acompanamiento',
    pasoBoton: 'Solicitar acompañamiento',
  },
  medium: {
    tarjeta: 'bg-amber-50 border-amber-200',
    texto: 'text-amber-700',
    icono: 'text-amber-500',
    consejo: 'Hay aspectos de tu rendimiento que conviene revisar. Estás a tiempo de mejorar: organiza tu semestre y busca apoyo si lo necesitas.',
    fondo: 'from-amber-50 via-white to-white border-amber-200',
    insignia: 'bg-amber-500 text-white',
    paso: 'Tu siguiente paso: revisa tus alertas y decide si te conviene pedir apoyo.',
    pasoRuta: '/dashboard/portal/alertas',
    pasoBoton: 'Ver mis alertas',
  },
  low: {
    tarjeta: 'bg-green-50 border-green-200',
    texto: 'text-green-700',
    icono: 'text-green-500',
    consejo: 'Vas por buen camino. Sigue así y revisa tu situación periódicamente.',
    fondo: 'from-green-50 via-white to-white border-green-200',
    insignia: 'bg-green-500 text-white',
    paso: null,
    pasoRuta: '/dashboard/portal/alertas',
    pasoBoton: 'Ver mis alertas',
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

const ESCALA_RIESGO: { nivel: Nivel; texto: string; activo: string }[] = [
  { nivel: 'low', texto: 'Bajo', activo: 'bg-green-500' },
  { nivel: 'medium', texto: 'Medio', activo: 'bg-amber-500' },
  { nivel: 'high', texto: 'Alto', activo: 'bg-riesgo-critico' },
];

/** Esqueleto de carga: mantiene la forma de la pantalla mientras llegan los datos. */
function Esqueleto({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-[10px] bg-wash ${className}`} aria-hidden="true" />;
}

function CargandoLista({ etiqueta }: { etiqueta: string }) {
  return (
    <div role="status" aria-label={etiqueta} className="space-y-3">
      <Esqueleto className="h-16" /><Esqueleto className="h-16" /><Esqueleto className="h-16 opacity-60" />
      <span className="sr-only">{etiqueta}</span>
    </div>
  );
}

function CargandoInicio() {
  return (
    <div className="space-y-6" role="status" aria-live="polite" aria-label="Cargando tu información">
      <div className="space-y-2">
        <Esqueleto className="h-8 w-64" />
        <Esqueleto className="h-4 w-48" />
      </div>
      <Esqueleto className="h-52 w-full !rounded-[14px]" />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Esqueleto className="h-28" /><Esqueleto className="h-28" /><Esqueleto className="h-28" />
      </div>
      <span className="sr-only">Cargando tu información…</span>
    </div>
  );
}

function TarjetaRiesgo({ datos }: { datos: RiesgoPropio }) {
  const { riesgo } = datos;

  if (!riesgo.nivel) {
    return (
      <div className="bg-white rounded-[14px] border border-line shadow-sm p-6 flex items-start gap-4">
        <div className="w-12 h-12 rounded-[14px] bg-wash flex items-center justify-center shrink-0">
          <Info className="w-6 h-6 text-gray-500" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Nivel de riesgo académico</h2>
          <p className="text-sm text-gray-600 mt-1">{riesgo.mensaje}</p>
        </div>
      </div>
    );
  }

  const estilo = ESTILO_NIVEL[riesgo.nivel];
  const Icono = riesgo.nivel === 'low' ? CheckCircle2 : AlertTriangle;
  const posicion = ESCALA_RIESGO.findIndex((e) => e.nivel === riesgo.nivel);
  return (
    <section className="bg-white rounded-[20px] border border-line overflow-hidden grid md:grid-cols-[minmax(0,17rem)_minmax(0,1fr)]" aria-label="Tu nivel de riesgo académico">
      {/* Cómo estás: el nivel, dicho con palabras y con la escala */}
      <div className={`p-6 sm:p-7 border-b md:border-b-0 md:border-r ${estilo.tarjeta}`}>
        <p className="text-sm font-medium text-ink-soft">Tu nivel de riesgo académico actual</p>
        <p className={`mt-2 flex items-center gap-2.5 text-4xl font-semibold tracking-[-0.03em] leading-none ${estilo.texto}`}>
          <Icono className="w-7 h-7 shrink-0" aria-hidden="true" />
          {riesgo.nivel_texto?.toUpperCase()}
        </p>

        <div className="mt-6" role="img" aria-label={`Nivel ${riesgo.nivel_texto} en una escala de bajo, medio y alto`}>
          <div className="grid grid-cols-3 gap-1">
            {ESCALA_RIESGO.map((e, i) => (
              <div key={e.nivel} className={`h-2 rounded-full ${i <= posicion ? e.activo : 'bg-white/80'}`} />
            ))}
          </div>
          <div className="grid grid-cols-3 gap-1 mt-1.5 text-xs text-ink-muted">
            {ESCALA_RIESGO.map((e, i) => (
              <span key={e.nivel} className={i === posicion ? 'font-semibold text-ink' : ''}>{e.texto}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Qué significa y qué puedes hacer ahora */}
      <div className="p-6 sm:p-7 flex flex-col">
        <p className="text-base sm:text-lg text-ink leading-relaxed max-w-[58ch]">{estilo.consejo}</p>

        {estilo.paso && (
          <div className="mt-5 flex flex-col sm:flex-row sm:items-center gap-3">
            <Link
              to={estilo.pasoRuta}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-primary-strong shrink-0"
            >
              {estilo.pasoBoton}
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </Link>
            <p className="text-sm text-ink-muted">{estilo.paso}</p>
          </div>
        )}

        <p className="text-xs text-ink-muted mt-auto pt-5">
          {riesgo.periodo && <>Periodo {riesgo.periodo} · </>}
          {riesgo.fecha_calculo && <>Calculado el {new Date(riesgo.fecha_calculo).toLocaleString('es-CO', { dateStyle: 'long', timeStyle: 'short' })}</>}
        </p>
      </div>
    </section>
  );
}

function Causas({ causas, nivel }: { causas: Causa[]; nivel: Nivel | null }) {
  if (!nivel) return null;
  return (
    <section className="bg-white rounded-[14px] border border-line p-6">
      <h2 className="text-lg font-semibold text-gray-900">¿Por qué tengo este nivel?</h2>
      {causas.length === 0 ? (
        <p className="text-sm text-gray-600 mt-3 flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-green-500" />
          No se cumple ninguna de las condiciones de riesgo con tu información académica actual.
        </p>
      ) : (
        <ul className="mt-4 space-y-4">
          {causas.map((causa, i) => (
            <li key={`${causa.regla}-${i}`} className={`border border-line rounded-[10px] p-4 border-l-4 transition-shadow duration-150 hover:shadow-md ${causa.nivel === 'high' ? 'border-l-primary' : causa.nivel === 'medium' ? 'border-l-amber-400' : 'border-l-emerald-400'}`}>
              <div className="flex items-center justify-between gap-3">
                <p className="font-medium text-gray-900">{causa.regla}</p>
                <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${ESTILO_NIVEL[causa.nivel]?.tarjeta ?? ''} ${ESTILO_NIVEL[causa.nivel]?.texto ?? ''}`}>
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
      escala: indicadores.pps ?? null,
    },
    { titulo: 'Promedio acumulado (PPA)', valor: numero(indicadores.ppa), detalle: 'Toda tu carrera', icono: GraduationCap, escala: indicadores.ppa ?? null },
    {
      titulo: 'Materias perdidas por aprobar',
      valor: indicadores.materias_reprobadas ?? '—',
      detalle: indicadores.lista_materias_reprobadas.join(', ') || 'Ninguna',
      icono: XCircle,
      escala: null,
    },
    { titulo: 'Créditos aprobados', valor: indicadores.creditos_aprobados, detalle: 'Materias aprobadas', icono: BookOpen, escala: null },
  ];

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-900 mb-3">Mis indicadores</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {tarjetas.map(({ titulo, valor, detalle, icono: Icono, escala }) => (
          <div key={titulo} className="bg-white rounded-[14px] border border-line p-4 transition-all duration-200 hover:">
            <div className="flex items-center gap-2.5 text-gray-500">
              <span className="w-8 h-8 rounded-[10px] bg-primary-tint flex items-center justify-center shrink-0">
                <Icono className="w-4 h-4 text-primary" aria-hidden="true" />
              </span>
              <p className="text-xs font-medium leading-snug">{titulo}</p>
            </div>
            <p className="text-3xl font-semibold text-ink mt-3 tabular-nums">{valor}</p>
            {escala !== null && (
              <div className="mt-2 h-1.5 w-full rounded-full bg-wash overflow-hidden" aria-hidden="true">
                <div
                  className={`h-full rounded-full transition-[width] duration-700 ease-out ${escala >= NOTA_APROBATORIA ? 'bg-green-500' : 'bg-riesgo-critico'}`}
                  style={{ width: `${Math.min(100, (escala / 5) * 100)}%` }}
                />
              </div>
            )}
            <p className="text-xs text-gray-500 mt-2 truncate" title={detalle}>{detalle}</p>
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
    <p className={`flex items-center gap-2 text-sm border rounded-[10px] px-3 py-2 ${color}`}>
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
    contenido = <CargandoLista etiqueta="Cargando tu evolución…" />;
  } else if (evolucion.serie.length === 0) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-12 border-2 border-dashed border-line rounded-[14px] text-gray-500 bg-paper">
        <IconoLinea className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-sm">{evolucion.mensaje}</p>
      </div>
    );
  } else if (!evolucion.historia_suficiente) {
    const [unico] = evolucion.serie;
    contenido = (
      <div className="space-y-4">
        <p className="flex items-start gap-2 text-sm text-gray-600 bg-gray-50 border border-gray-200 rounded-[10px] px-3 py-2">
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
            <div key={titulo} className="border border-gray-100 rounded-[10px] p-3">
              <p className="text-xs text-gray-500">{titulo}</p>
              <p className="text-lg font-semibold text-gray-900">{valor}</p>
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
              stroke="#9C8D8A"
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
    <section className="bg-white rounded-[14px] border border-line p-6">
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

const CLASE_DIALOGO = 'bg-white sm:max-w-lg max-h-[90vh] overflow-y-auto rounded-[14px] border-line p-0 gap-0 shadow-2xl';

const TONO_SEVERIDAD: Record<Nivel, string> = {
  high: 'bg-red-50 text-red-600',
  medium: 'bg-amber-50 text-amber-700',
  low: 'bg-green-50 text-green-700',
};

/** Cabecera común de los diálogos del portal: ícono en tinte, título, explicación breve y chips. */
function CabeceraModal({ icono: Icono, tono, titulo, descripcion, children }: {
  icono: React.ElementType;
  tono: string;
  titulo: string;
  descripcion?: string;
  children?: React.ReactNode;
}) {
  return (
    <DialogHeader className="px-6 pt-6 pb-4 border-b border-wash bg-gradient-to-b from-paper to-white text-left">
      <div className="flex items-start gap-3.5 pr-7">
        <span className={`shrink-0 w-11 h-11 rounded-[10px] flex items-center justify-center ${tono}`}>
          <Icono className="w-5 h-5" aria-hidden="true" />
        </span>
        <div className="min-w-0 space-y-1.5">
          <DialogTitle className="text-xl leading-snug text-ink">{titulo}</DialogTitle>
          <DialogDescription className="text-ink-muted leading-relaxed">
            {descripcion ?? 'Aquí tienes el detalle, explicado paso a paso.'}
          </DialogDescription>
          {children && <div className="flex flex-wrap items-center gap-2 pt-1">{children}</div>}
        </div>
      </div>
    </DialogHeader>
  );
}

function CuerpoModal({ children }: { children: React.ReactNode }) {
  return <div className="px-6 py-5 space-y-5">{children}</div>;
}

function PieModal({ onCerrar, children }: { onCerrar: () => void; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end gap-2 px-6 py-4 border-t border-wash bg-paper">
      {children}
      <button type="button" onClick={onCerrar}
        className="px-4 py-2.5 rounded-[10px] text-sm font-semibold text-ink-soft bg-wash hover:bg-line transition-colors">
        Cerrar
      </button>
    </div>
  );
}

function SeccionModal({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h3 className="text-sm font-semibold text-ink">{titulo}</h3>
      {children}
    </section>
  );
}

function FilasDetalle({ filas }: { filas: [string, string][] }) {
  return (
    <dl className="rounded-[10px] border border-line divide-y divide-wash text-sm overflow-hidden">
      {filas.map(([etiqueta, valor]) => (
        <div key={etiqueta} className="flex justify-between gap-4 px-3.5 py-2.5 bg-white">
          <dt className="text-ink-muted">{etiqueta}</dt>
          <dd className="text-ink font-medium text-right tabular-nums">{valor}</dd>
        </div>
      ))}
    </dl>
  );
}

function CargandoModal({ titulo }: { titulo: string }) {
  return (
    <>
      <DialogHeader className="px-6 pt-6 pb-4 border-b border-wash text-left">
        <DialogTitle className="text-xl text-ink">{titulo}</DialogTitle>
        <DialogDescription>Estamos buscando la información…</DialogDescription>
      </DialogHeader>
      <div role="status" aria-label="Cargando" className="px-6 py-5 space-y-3">
        <Esqueleto className="h-5 w-2/3" /><Esqueleto className="h-20" /><Esqueleto className="h-14" />
        <span className="sr-only">Cargando…</span>
      </div>
    </>
  );
}

function ErrorModal({ titulo, mensaje, onCerrar }: { titulo: string; mensaje: string; onCerrar: () => void }) {
  return (
    <>
      <CabeceraModal icono={AlertTriangle} tono="bg-amber-50 text-amber-700" titulo={titulo}
        descripcion="No pudimos mostrar esta información." />
      <CuerpoModal>
        <p role="alert" className="text-sm text-red-800 bg-red-50 border border-red-200 rounded-[10px] px-3.5 py-2.5">{mensaje}</p>
        <SeccionModal titulo="Qué puedes hacer">
          <p className="text-sm text-ink-soft">
            Revisa tu conexión y vuelve a abrir el detalle. Si el problema continúa, cierra sesión y entra de nuevo.
          </p>
        </SeccionModal>
      </CuerpoModal>
      <PieModal onCerrar={onCerrar} />
    </>
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
    contenido = <ErrorModal titulo="Detalle de la alerta" mensaje={error} onCerrar={onCerrar} />;
  } else if (!detalle) {
    contenido = <CargandoModal titulo="Detalle de la alerta" />;
  } else {
    const cerrada = detalle.estado === 'cerrada';
    contenido = (
      <>
        <CabeceraModal
          icono={cerrada ? CheckCircle2 : AlertTriangle}
          tono={cerrada ? 'bg-green-50 text-green-700' : TONO_SEVERIDAD[detalle.severidad] ?? 'bg-gray-100 text-gray-600'}
          titulo={detalle.tipo}
          descripcion={detalle.resumen}
        >
          <InsigniaSeveridad alerta={detalle} />
          <InsigniaEstado alerta={detalle} />
        </CabeceraModal>

        <CuerpoModal>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-[10px] bg-paper px-3.5 py-2.5">
              <p className="text-xs text-ink-muted">Registrada el</p>
              <p className="text-ink font-medium">{fecha(detalle.fecha_generacion)}</p>
            </div>
            {cerrada && (
              <div className="rounded-[10px] bg-paper px-3.5 py-2.5">
                <p className="text-xs text-ink-muted">Cerrada el</p>
                <p className="text-ink font-medium">{detalle.fecha_cierre ? fecha(detalle.fecha_cierre) : 'Fecha no registrada'}</p>
              </div>
            )}
          </div>

          <SeccionModal titulo="¿Qué significa?">
            <p className="text-sm text-ink-soft leading-relaxed">{detalle.explicacion.mensaje}</p>
          </SeccionModal>

          {detalle.explicacion.datos.length > 0 && (
            <FilasDetalle filas={detalle.explicacion.datos.map((d) => [d.etiqueta, String(d.valor)])} />
          )}

          {detalle.intervenciones.length > 0 && (
            <p className="flex items-start gap-2 text-sm text-ink-soft">
              <HeartHandshake className="w-4 h-4 mt-0.5 shrink-0 text-primary" aria-hidden="true" />
              <span>
                {detalle.intervenciones.length === 1
                  ? 'Se ha registrado 1 acompañamiento sobre esta alerta.'
                  : `Se han registrado ${detalle.intervenciones.length} acompañamientos sobre esta alerta.`}{' '}
                Puedes verlos en{' '}
                <Link to="/dashboard/portal/acompanamiento" onClick={onCerrar} className="font-medium text-primary hover:underline">
                  Mi acompañamiento
                </Link>.
              </span>
            </p>
          )}

          {detalle.cierre ? (
            <p className="flex items-start gap-2.5 text-sm text-green-900 bg-green-50 border border-green-200 rounded-[10px] px-3.5 py-3">
              <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
              <span>{detalle.cierre.mensaje} Los datos corresponden al último registro de la alerta.</span>
            </p>
          ) : (
            <div className="rounded-[10px] bg-primary-tint/60 border border-primary/15 px-3.5 py-3">
              <p className="flex items-center gap-2 text-sm font-semibold text-ink">
                <Lightbulb className="w-4 h-4 text-primary" aria-hidden="true" />
                Qué puedes hacer
              </p>
              <p className="text-sm text-ink-soft mt-1 leading-relaxed">{detalle.explicacion.recomendacion}</p>
            </div>
          )}
        </CuerpoModal>

        <PieModal onCerrar={onCerrar}>
          {!cerrada && (
            <Link to="/dashboard/portal/acompanamiento" onClick={onCerrar}
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-[10px] text-sm font-semibold text-white bg-primary hover:bg-primary-strong transition-colors">
              <MessageSquarePlus className="w-4 h-4" aria-hidden="true" />
              Pedir acompañamiento
            </Link>
          )}
        </PieModal>
      </>
    );
  }

  return (
    <Dialog open={alertaId !== null} onOpenChange={(abierto) => !abierto && onCerrar()}>
      <DialogContent className={CLASE_DIALOGO}>{contenido}</DialogContent>
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
  const claseSelect = 'h-10 px-3.5 border border-line-strong rounded-[10px] bg-white text-sm text-ink';

  let contenido: React.ReactNode;
  if (error) {
    contenido = <p role="alert" className="text-sm text-red-700">{error}</p>;
  } else if (!listado) {
    contenido = <CargandoLista etiqueta="Cargando tus alertas…" />;
  } else if (listado.conteos.total === 0) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-12 border-2 border-dashed border-line rounded-[14px] text-gray-500 bg-paper">
        <CheckCircle2 className="w-8 h-8 mb-2 text-green-500 opacity-70" />
        <p className="text-sm">No tienes alertas registradas sobre tu situación académica.</p>
        <p className="text-xs mt-1">Si en algún momento se registra una, aquí verás qué la originó y cómo mejorar.</p>
      </div>
    );
  } else if (listado.alertas.length === 0) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-12 border-2 border-dashed border-line rounded-[14px] text-gray-500 bg-paper">
        <SearchX className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-sm">Ninguna alerta coincide con los filtros seleccionados.</p>
        <button type="button" onClick={quitarFiltros} className="mt-3 text-sm font-medium text-primary hover:underline">
          Quitar filtros
        </button>
      </div>
    );
  } else {
    contenido = (
      <ul className="divide-y divide-wash border border-line rounded-[10px] overflow-hidden">
        {listado.alertas.map((alerta) => (
          <li key={alerta.id}>
            <button
              type="button"
              onClick={() => setSeleccionada(alerta.id)}
              className="group w-full text-left px-4 py-3.5 flex items-center gap-3 transition-colors duration-150 hover:bg-paper focus:outline-none focus-visible:bg-paper focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/40"
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
              <ChevronRight className="w-4 h-4 text-gray-400 shrink-0 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-primary" />
            </button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-3xl font-semibold text-ink">Mis alertas</h1>
        <p className="mt-1 text-ink-muted max-w-[70ch]">Avisos registrados sobre tu situación académica. Cada uno explica qué lo originó y qué puedes hacer para mejorar.</p>
      </header>
    <section className="bg-white rounded-[14px] border border-line p-4 sm:p-5">

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
            <button type="button" onClick={quitarFiltros} className="text-sm font-medium text-primary hover:underline pb-2">
              Quitar filtros
            </button>
          )}
        </div>
      )}

      {contenido}
      <ModalAlerta alertaId={seleccionada} onCerrar={() => setSeleccionada(null)} />
    </section>
    </div>
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
    contenido = <ErrorModal titulo="Acompañamiento" mensaje={error} onCerrar={onCerrar} />;
  } else if (!detalle) {
    contenido = <CargandoModal titulo="Acompañamiento" />;
  } else {
    const filas: [string, string][] = [
      ['Fecha', fecha(detalle.fecha)],
      ['Responsable', detalle.responsable ?? 'Equipo de acompañamiento'],
      ['Alerta relacionada', alertaTexto(detalle.alerta)],
      ...(detalle.alerta.periodo ? [['Periodo', detalle.alerta.periodo] as [string, string]] : []),
    ];
    contenido = (
      <>
        <CabeceraModal
          icono={HeartHandshake}
          tono="bg-primary-tint text-primary"
          titulo={detalle.tipo_texto}
          descripcion={DESCRIPCION_TIPO[detalle.tipo] ?? 'Acompañamiento registrado sobre tu caso.'}
        >
          <InsigniaEstadoIntervencion intervencion={detalle} />
        </CabeceraModal>

        <CuerpoModal>
          <FilasDetalle filas={filas} />
          <SeccionModal titulo="Resultado">
            {detalle.resultado ? (
              <p className="text-sm text-green-900 bg-green-50 border border-green-200 rounded-[10px] px-3.5 py-3 leading-relaxed">
                {detalle.resultado}
              </p>
            ) : (
              <p className="flex items-start gap-2 text-sm text-ink-muted bg-paper rounded-[10px] px-3.5 py-3">
                <Clock className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
                {detalle.estado === 'concluida'
                  ? 'Este acompañamiento concluyó sin un resultado registrado.'
                  : 'Este acompañamiento sigue en curso. El resultado aparecerá cuando se registre.'}
              </p>
            )}
          </SeccionModal>
        </CuerpoModal>

        <PieModal onCerrar={onCerrar} />
      </>
    );
  }

  return (
    <Dialog open={intervencionId !== null} onOpenChange={(abierto) => !abierto && onCerrar()}>
      <DialogContent className={CLASE_DIALOGO}>{contenido}</DialogContent>
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
  const claseSelect = 'h-10 px-3.5 border border-line-strong rounded-[10px] bg-white text-sm text-ink';

  let contenido: React.ReactNode;
  if (error) {
    contenido = <p role="alert" className="text-sm text-red-700">{error}</p>;
  } else if (!listado) {
    contenido = <CargandoLista etiqueta="Cargando tu acompañamiento…" />;
  } else if (listado.conteos.total === 0) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-12 border-2 border-dashed border-line rounded-[14px] text-gray-500 bg-paper">
        <HeartHandshake className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-sm">Aún no hay acompañamientos registrados sobre tu caso.</p>
        <p className="text-xs mt-1">
          Cuando un docente o Bienestar Universitario realice una tutoría, citación o remisión, la verás aquí.
        </p>
      </div>
    );
  } else if (listado.intervenciones.length === 0) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-12 border-2 border-dashed border-line rounded-[14px] text-gray-500 bg-paper">
        <SearchX className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-sm">Ningún acompañamiento coincide con los filtros seleccionados.</p>
        <button type="button" onClick={quitarFiltros} className="mt-3 text-sm font-medium text-primary hover:underline">
          Quitar filtros
        </button>
      </div>
    );
  } else {
    contenido = (
      <ol className="relative border-l-2 border-line ml-3 space-y-4">
        {listado.intervenciones.map((intervencion) => (
          <li key={intervencion.id} className="ml-5">
            <span
              className={`absolute -left-[9px] mt-4 w-4 h-4 rounded-full border-2 border-white shadow-sm ${
                intervencion.estado === 'concluida' ? 'bg-green-500' : 'bg-indigo-500'
              }`}
            />
            <button
              type="button"
              onClick={() => setSeleccionada(intervencion.id)}
              className="group w-full text-left border border-line bg-white rounded-[10px] px-4 py-3.5 flex items-center gap-3 transition-all duration-150 hover:bg-paper hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
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
              <ChevronRight className="w-4 h-4 text-gray-400 shrink-0 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-primary" />
            </button>
          </li>
        ))}
      </ol>
    );
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-3xl font-semibold text-ink">Mi acompañamiento</h1>
        <p className="mt-1 text-ink-muted max-w-[70ch]">El seguimiento que la universidad ha dado a tu caso: tutorías, citaciones y remisiones registradas sobre tus alertas, con su responsable y su resultado.</p>
      </header>
    <section className="bg-white rounded-[14px] border border-line p-4 sm:p-5">

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
            <button type="button" onClick={quitarFiltros} className="text-sm font-medium text-primary hover:underline pb-2">
              Quitar filtros
            </button>
          )}
        </div>
      )}

      {contenido}
      <ModalIntervencion intervencionId={seleccionada} onCerrar={() => setSeleccionada(null)} />
    </section>
    </div>
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
  const [confirmandoId, setConfirmandoId] = useState<number | null>(null);

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
    if (!motivo) nuevos.motivo = 'Elige en la lista el motivo que mejor describe lo que necesitas.';
    if (descripcion.trim().length < listado.descripcion_minima) {
      nuevos.descripcion = `Cuéntanos un poco más: escribe al menos ${listado.descripcion_minima} caracteres para que Bienestar entienda tu situación.`;
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
    setConfirmandoId(null);
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

  const claseCampo = 'w-full px-3.5 py-2.5 border border-line-strong rounded-[10px] bg-white text-sm text-ink placeholder:text-ink-faint transition-shadow focus:outline-none focus:ring-4 focus:ring-primary/15 focus:border-primary aria-[invalid=true]:border-red-400 aria-[invalid=true]:bg-red-50/40 disabled:bg-paper disabled:text-gray-400';
  const minimo = listado?.descripcion_minima ?? 20;
  const escritos = descripcion.trim().length;
  const progreso = Math.min(100, Math.round((escritos / minimo) * 100));
  const bloqueado = !listado?.puede_solicitar;

  let historial: React.ReactNode;
  if (error) {
    historial = <p role="alert" className="text-sm text-red-700">{error}</p>;
  } else if (!listado) {
    historial = <CargandoLista etiqueta="Cargando tus solicitudes…" />;
  } else if (listado.solicitudes.length === 0) {
    historial = (
      <div className="flex items-center gap-3 rounded-[10px] border border-dashed border-line-strong bg-paper px-4 py-5">
        <span className="w-10 h-10 rounded-full bg-wash text-ink-muted flex items-center justify-center shrink-0">
          <MessageSquarePlus className="w-5 h-5" aria-hidden="true" />
        </span>
        <p className="text-sm text-ink-muted">
          Aún no has enviado solicitudes de acompañamiento. Cuando envíes una, la verás aquí con su estado y la respuesta.
        </p>
      </div>
    );
  } else {
    historial = (
      <ul className="space-y-3">
        {listado.solicitudes.map((s) => (
          <li key={s.id} className="border border-line rounded-[10px] p-4 bg-white transition-shadow duration-150 hover:shadow-md">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-medium text-gray-900">{s.motivo_texto}</p>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${INSIGNIA_ESTADO_SOLICITUD[s.estado]}`}>
                  {s.estado_texto}
                </span>
              </div>
              {s.puede_cancelar && confirmandoId !== s.id && (
                <button type="button" onClick={() => setConfirmandoId(s.id)} className="text-sm font-medium text-primary hover:underline">
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
            {confirmandoId === s.id && (
              <div role="alertdialog" aria-label="Confirmar cancelación"
                className="mt-3 flex flex-wrap items-center gap-2 rounded-[10px] border border-amber-200 bg-amber-50 px-3.5 py-2.5 ">
                <p className="text-sm text-amber-900 flex-1 min-w-[14rem]">¿Quieres cancelar esta solicitud de acompañamiento?</p>
                <button type="button" onClick={() => cancelar(s.id)}
                  className="px-3 py-1.5 rounded-[10px] text-sm font-semibold text-white bg-primary hover:bg-primary-strong transition-colors">
                  Sí, cancelar
                </button>
                <button type="button" onClick={() => setConfirmandoId(null)}
                  className="px-3 py-1.5 rounded-[10px] text-sm font-semibold text-ink-soft bg-white border border-line-strong hover:bg-paper transition-colors">
                  No, mantenerla
                </button>
              </div>
            )}
            <p className="text-sm text-gray-700 mt-2 whitespace-pre-line">{s.descripcion}</p>
            {s.respuesta ? (
              <div className="mt-3 text-sm bg-green-50 border border-green-200 rounded-[10px] px-3 py-2 text-green-900">
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
    <section className="bg-white rounded-[14px] border border-line p-6">
      <div className="flex items-start gap-3">
        <span className="w-10 h-10 rounded-[10px] bg-primary-tint text-primary flex items-center justify-center shrink-0">
          <MessageSquarePlus className="w-5 h-5" aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-ink">Solicitar acompañamiento</h2>
          <p className="text-sm text-ink-muted mt-0.5 mb-5 leading-relaxed">
            Si necesitas apoyo, cuéntanos qué está pasando. Bienestar Universitario recibirá tu solicitud y te responderá por
            este medio y por correo.
          </p>
        </div>
      </div>

      {mensajeEnvio && (
        <div role={mensajeEnvio.tipo === 'error' ? 'alert' : 'status'}
          className={`mb-5 flex items-start gap-2.5 text-sm rounded-[10px] px-3.5 py-3 border ${mensajeEnvio.tipo === 'ok'
            ? 'text-green-900 bg-green-50 border-green-200' : 'text-red-800 bg-red-50 border-red-200'}`}>
          {mensajeEnvio.tipo === 'ok'
            ? <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
            : <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />}
          <p className="flex-1">{mensajeEnvio.texto}</p>
          <button type="button" onClick={() => setMensajeEnvio(null)} aria-label="Cerrar aviso" className="opacity-60 hover:opacity-100">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {listado && bloqueado && listado.mensaje_bloqueo && (
        <p className="flex items-start gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-[10px] px-3.5 py-3 mb-4">
          <Info className="w-4 h-4 mt-0.5 shrink-0" />
          {listado.mensaje_bloqueo}
        </p>
      )}

      <form onSubmit={enviar} noValidate className="space-y-5">
        <fieldset disabled={bloqueado || enviando} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="text-sm text-ink-soft">
              <span className="block mb-1.5 font-semibold">Motivo <span className="text-red-600" aria-hidden="true">*</span></span>
              <select value={motivo} onChange={(e) => setMotivo(e.target.value)} className={claseCampo}
                aria-invalid={!!errores.motivo} aria-describedby="ayuda-motivo">
                <option value="">Selecciona un motivo</option>
                {listado?.motivos.map((m) => (
                  <option key={m.valor} value={m.valor}>{m.texto}</option>
                ))}
              </select>
              <span id="ayuda-motivo" className={`block text-xs mt-1.5 ${errores.motivo ? 'text-red-700 font-medium' : 'text-ink-muted'}`}>
                {errores.motivo || 'Elige el tema que más se parece a lo que necesitas.'}
              </span>
            </label>
            <label className="text-sm text-ink-soft">
              <span className="block mb-1.5 font-semibold">Alerta relacionada <span className="font-normal text-ink-muted">(opcional)</span></span>
              <select value={alerta} onChange={(e) => setAlerta(e.target.value)} className={claseCampo}
                aria-invalid={!!errores.alerta} aria-describedby="ayuda-alerta">
                <option value="">Ninguna</option>
                {alertas.map((a) => (
                  <option key={a.id} value={a.id}>{a.materia ? `${a.tipo} · ${a.materia}` : a.tipo}</option>
                ))}
              </select>
              <span id="ayuda-alerta" className={`block text-xs mt-1.5 ${errores.alerta ? 'text-red-700 font-medium' : 'text-ink-muted'}`}>
                {errores.alerta || 'Si tu solicitud se debe a una alerta, selecciónala para dar más contexto.'}
              </span>
            </label>
          </div>
          <label className="block text-sm text-ink-soft">
            <span className="block mb-1.5 font-semibold">Descripción <span className="text-red-600" aria-hidden="true">*</span></span>
            <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} rows={4} maxLength={2000}
              placeholder="Describe brevemente tu situación y el tipo de apoyo que necesitas."
              className={`${claseCampo} resize-y min-h-[7rem]`} aria-invalid={!!errores.descripcion} aria-describedby="ayuda-descripcion" />
            <span id="ayuda-descripcion" className="block mt-2">
              <span className="block h-1 rounded-full bg-wash overflow-hidden" aria-hidden="true">
                <span className={`block h-full rounded-full transition-all duration-300 ${progreso >= 100 ? 'bg-green-500' : 'bg-primary/70'}`}
                  style={{ width: `${progreso}%` }} />
              </span>
              <span className="flex justify-between gap-3 text-xs mt-1.5">
                <span className={errores.descripcion ? 'text-red-700 font-medium' : 'text-ink-muted'}>
                  {errores.descripcion || (progreso >= 100 ? 'Listo, ya puedes enviarla.' : 'Cuéntanos qué pasa y cómo podemos ayudarte.')}
                </span>
                <span className="text-ink-muted tabular-nums shrink-0">{escritos} / mínimo {minimo}</span>
              </span>
            </span>
          </label>
          <button type="submit"
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-[10px] bg-primary text-white text-sm font-semibold transition-all duration-150 hover:bg-primary-strong disabled:opacity-60 disabled:hover:translate-y-0 w-full sm:w-auto">
            {enviando ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> : <Send className="w-4 h-4" aria-hidden="true" />}
            {enviando ? 'Enviando…' : 'Enviar solicitud'}
          </button>
        </fieldset>
      </form>

      <h3 className="text-sm font-semibold text-gray-900 mt-6 mb-3">Mis solicitudes</h3>
      {historial}
    </section>
  );
}


const ESTILO_REGISTRO: Record<EstadoAsistencia, string> = {
  ASISTIO: 'bg-green-50 text-green-700',
  FALTA: 'bg-red-50 text-red-700',
  FALTA_JUSTIFICADA: 'bg-amber-50 text-amber-700',
};

function TarjetaAsistencia({ curso }: { curso: CursoAsistencia }) {
  const [abierta, setAbierta] = useState(false);
  const sinClases = curso.porcentaje === null;
  const tono = curso.supera_umbral ? 'red' : curso.cerca_del_limite ? 'amber' : 'green';
  const colorBarra = { red: 'bg-red-500', amber: 'bg-amber-500', green: 'bg-green-500' }[tono];
  const colorBorde = { red: 'border-red-200', amber: 'border-amber-200', green: 'border-gray-200' }[tono];
  // La barra llega al 100 % en el umbral (o en el 100 % de inasistencia si no hay umbral)
  const escala = curso.umbral && curso.umbral > 0 ? curso.umbral : 100;
  const ancho = Math.min(100, ((curso.porcentaje ?? 0) / escala) * 100);

  return (
    <li className={`border rounded-[10px] p-4 bg-white transition-shadow duration-150 hover:shadow-md ${colorBorde}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-gray-900 truncate">{curso.materia}</p>
          <p className="text-xs text-gray-500">{curso.codigo_materia} · Grupo {curso.grupo}</p>
        </div>
        <div className="text-right shrink-0">
          <p className={`text-2xl font-semibold tabular-nums ${curso.supera_umbral ? 'text-red-700' : curso.cerca_del_limite ? 'text-amber-700' : 'text-gray-900'}`}>
            {sinClases ? '—' : `${numero(curso.porcentaje)} %`}
          </p>
          <p className="text-xs text-gray-500">de inasistencia</p>
        </div>
      </div>

      {sinClases ? (
        <p className="text-sm text-gray-500 mt-3">Aún no hay clases registradas en esta materia.</p>
      ) : (
        <>
          <p className="text-sm text-gray-700 mt-3">
            {curso.faltas} {curso.faltas === 1 ? 'falta' : 'faltas'} sin justificar de {curso.total_clases} clases registradas
            {curso.faltas_justificadas > 0 && <> · {curso.faltas_justificadas} justificada{curso.faltas_justificadas === 1 ? '' : 's'}</>}
          </p>
          <div className="mt-2">
            <div className="h-2.5 w-full bg-gray-100 rounded-full overflow-hidden" role="progressbar"
              aria-valuemin={0} aria-valuemax={escala} aria-valuenow={curso.porcentaje ?? 0}
              aria-label={`Inasistencia de ${curso.materia}`}>
              <div className={`h-full rounded-full transition-[width] duration-700 ease-out ${colorBarra}`} style={{ width: `${ancho}%` }} />
            </div>
            <p className="flex justify-between text-xs text-gray-500 mt-1">
              <span>0 %</span>
              <span>{curso.umbral !== null ? `Límite permitido: ${numero(curso.umbral, 1)} %` : 'Sin límite configurado'}</span>
            </p>
          </div>
        </>
      )}

      {curso.supera_umbral && (
        <p role="alert" className="flex items-start gap-2 text-sm text-red-800 bg-red-50 border border-red-200 rounded-[10px] px-3 py-2 mt-3">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          Superaste el límite de inasistencia permitido en esta materia. Habla con tu docente o con Bienestar Universitario.
        </p>
      )}
      {curso.cerca_del_limite && (
        <p className="flex items-start gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-[10px] px-3 py-2 mt-3">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          Estás cerca del límite de inasistencia{curso.umbral !== null ? ` (${numero(curso.umbral, 1)} %)` : ''}. Procura no faltar a
          las próximas clases.
        </p>
      )}

      {curso.detalle.length > 0 && (
        <div className="mt-3">
          <button type="button" onClick={() => setAbierta((v) => !v)} aria-expanded={abierta}
            className="text-sm font-medium text-primary hover:underline flex items-center gap-1">
            <ChevronRight className={`w-4 h-4 transition-transform ${abierta ? 'rotate-90' : ''}`} />
            {abierta ? 'Ocultar detalle por fecha' : 'Ver detalle por fecha'}
          </button>
          {abierta && (
            <ul className="mt-2 divide-y divide-gray-100 border border-gray-100 rounded-[10px] text-sm">
              {curso.detalle.map((d) => (
                <li key={d.fecha} className="flex items-center justify-between px-3 py-1.5">
                  <span className="text-gray-700">
                    {new Date(`${d.fecha}T00:00:00`).toLocaleDateString('es-CO', { weekday: 'short', day: 'numeric', month: 'long' })}
                  </span>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${ESTILO_REGISTRO[d.estado] ?? 'bg-gray-100 text-gray-600'}`}>
                    {d.estado_texto}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

/** HU-42: porcentaje de inasistencia por materia frente al límite permitido. */
function MiAsistencia() {
  const [datos, setDatos] = useState<AsistenciaPropia | null>(null);
  const [periodo, setPeriodo] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let activo = true;
    setError(null);
    apiFetch(`${baseUrl}/api/portal/asistencia/${periodo ? `?periodo=${encodeURIComponent(periodo)}` : ''}`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || 'No fue posible consultar tu asistencia.');
        if (activo) setDatos(json);
      })
      .catch((e: Error) => activo && setError(e.message));
    return () => {
      activo = false;
    };
  }, [periodo]);

  let contenido: React.ReactNode;
  if (error) {
    contenido = <p role="alert" className="text-sm text-red-700">{error}</p>;
  } else if (!datos) {
    contenido = (
      <div role="status" aria-label="Cargando tu asistencia" className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Esqueleto className="h-40" /><Esqueleto className="h-40" />
        <span className="sr-only">Cargando tu asistencia…</span>
      </div>
    );
  } else if (!datos.hay_registros) {
    contenido = (
      <div className="flex flex-col items-center justify-center text-center py-12 border-2 border-dashed border-line rounded-[14px] text-gray-500 bg-paper">
        <span className="w-12 h-12 rounded-full bg-wash flex items-center justify-center mb-3">
          <CalendarCheck className="w-6 h-6 text-gray-400" />
        </span>
        <p className="text-sm">{datos.mensaje ?? 'Aún no hay registros de asistencia.'}</p>
        <p className="text-xs mt-1">Cuando tus docentes registren la asistencia, verás aquí tu porcentaje por materia.</p>
      </div>
    );
  } else {
    contenido = (
      <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {datos.cursos.map((curso) => (
          <TarjetaAsistencia key={curso.curso_id} curso={curso} />
        ))}
      </ul>
    );
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-semibold text-ink">Mi asistencia</h1>
          <p className="mt-1 text-ink-muted max-w-[70ch]">
            Tu porcentaje de inasistencia en cada materia frente al límite permitido. Las faltas justificadas cuentan como
            clase pero no como falta.
          </p>
        </div>
        {datos && datos.periodos.length > 1 && (
          <label className="text-xs text-gray-600">
            <span className="block mb-1">Periodo</span>
            <select value={periodo || datos.periodo || ''} onChange={(e) => setPeriodo(e.target.value)}
              className="h-10 px-3.5 border border-line-strong rounded-[10px] bg-white text-sm text-ink">
              {datos.periodos.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
        )}
      </header>
      {contenido}
    </div>
  );
}

/** Resumen de las otras secciones del portal, con enlace a cada una. */
function AccesosPortal() {
  const [alertas, setAlertas] = useState<ListadoAlertas | null>(null);
  const [asistencia, setAsistencia] = useState<AsistenciaPropia | null>(null);
  const [solicitudes, setSolicitudes] = useState<ListadoSolicitudes | null>(null);

  useEffect(() => {
    let activo = true;
    const consultar = <T,>(ruta: string, guardar: (datos: T) => void) =>
      apiFetch(`${baseUrl}/api/portal/${ruta}`)
        .then(async (res) => (res.ok ? res.json() : null))
        .then((json: T | null) => {
          if (activo && json) guardar(json);
        })
        .catch(() => undefined);
    consultar<ListadoAlertas>('alertas/', setAlertas);
    consultar<AsistenciaPropia>('asistencia/', setAsistencia);
    consultar<ListadoSolicitudes>('solicitudes/', setSolicitudes);
    return () => {
      activo = false;
    };
  }, []);

  const pendientes = alertas ? alertas.conteos.activa + alertas.conteos.en_seguimiento : null;
  const sinAsistencia = asistencia !== null && !asistencia.hay_registros;
  const enRiesgo = asistencia ? asistencia.cursos.filter((c) => c.supera_umbral || c.cerca_del_limite).length : null;
  const enCurso = solicitudes ? solicitudes.en_curso ?? 0 : null;

  const tarjetas = [
    {
      ruta: '/dashboard/portal/alertas',
      titulo: 'Mis alertas',
      icono: Bell,
      valor: pendientes,
      detalle: pendientes === 1 ? 'alerta activa o en seguimiento' : 'alertas activas o en seguimiento',
      destacar: !!pendientes,
    },
    {
      ruta: '/dashboard/portal/asistencia',
      titulo: 'Mi asistencia',
      icono: CalendarCheck,
      valor: sinAsistencia ? '—' : enRiesgo,
      detalle: sinAsistencia
        ? 'Sin registros de asistencia'
        : enRiesgo === 1 ? 'materia cerca o por encima del límite' : 'materias cerca o por encima del límite',
      destacar: !!enRiesgo,
    },
    {
      ruta: '/dashboard/portal/acompanamiento',
      titulo: 'Mi acompañamiento',
      icono: HeartHandshake,
      valor: enCurso,
      detalle: enCurso === 1 ? 'solicitud en curso' : 'solicitudes en curso',
      destacar: false,
    },
  ];

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-900 mb-3">Mi seguimiento</h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {tarjetas.map(({ ruta, titulo, icono: Icono, valor, detalle, destacar }) => (
          <Link key={ruta} to={ruta}
            className="group bg-white rounded-[14px] border border-line p-4 transition-all duration-200 hover:border-primary/60">
            <div className="flex items-center justify-between text-gray-500">
              <span className="flex items-center gap-2">
                <Icono className="w-4 h-4" />
                <span className="text-xs font-medium">{titulo}</span>
              </span>
              <ChevronRight className="w-4 h-4 text-gray-300 transition-transform duration-200 group-hover:text-primary group-hover:translate-x-0.5" />
            </div>
            <p className={`text-3xl font-semibold mt-2 tabular-nums ${destacar ? 'text-riesgo-critico' : 'text-ink'}`}>{valor ?? '…'}</p>
            <p className="text-xs text-gray-500 mt-1">{valor === null ? 'Cargando…' : detalle}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

/**
 * Portal del estudiante, dividido en secciones de la barra lateral: inicio con
 * su nivel de riesgo (HU-37), indicadores y evolución (HU-38); alertas (HU-39);
 * asistencia por materia (HU-42); y acompañamiento (HU-40) con la solicitud de
 * acompañamiento (HU-41). Todo sale de /api/portal/.
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
      <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-[10px] p-4 text-sm">
        {error}
      </div>
    );
  }

  if (!datos) {
    return <CargandoInicio />;
  }

  return (
    <div className="space-y-6 ">
      <header>
        <h1 className="text-3xl font-semibold text-ink">Hola, {datos.estudiante.nombre}</h1>
        <p className="text-sm text-gray-500 tabular-nums">Código {datos.estudiante.codigo} · Semestre {datos.estudiante.semestre}</p>
      </header>

      <TarjetaRiesgo datos={datos} />
      <AccesosPortal />
      <Indicadores indicadores={datos.indicadores} />
      <Causas causas={datos.causas} nivel={datos.riesgo.nivel} />
      <EvolucionAcademica />
    </div>
  );
}

/** Sección «Mis alertas» del portal (HU-39). */
export function PortalAlertas() {
  return <MisAlertas />;
}

/** Sección «Mi asistencia» del portal (HU-42). */
export function PortalAsistencia() {
  return <MiAsistencia />;
}

/** Sección «Mi acompañamiento» del portal: seguimiento (HU-40) y solicitudes (HU-41). */
export function PortalAcompanamiento() {
  return (
    <div className="space-y-6">
      <MiAcompanamiento />
      <SolicitarAcompanamiento />
    </div>
  );
}
