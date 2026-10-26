import { useEffect, useState } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from 'recharts';
import {
  AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, BookOpen, CheckCircle2, GraduationCap, Info,
  LineChart as IconoLinea, TrendingUp, XCircle,
} from 'lucide-react';
import { apiFetch } from '../../services/apiFetch';
import { type ChartConfig, ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from '../components/ui/chart';
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

/**
 * Portal del estudiante: inicio con su nivel de riesgo actual (HU-37) y la
 * evolución de su promedio (HU-38). Las HU-39 a HU-42 (alertas, intervenciones,
 * solicitud de acompañamiento y asistencia) agregan aquí su sección o una
 * ruta hija de /dashboard/portal, siempre con datos de /api/portal/.
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
      <Indicadores indicadores={datos.indicadores} />
    </div>
  );
}
