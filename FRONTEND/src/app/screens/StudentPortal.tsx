import { useEffect, useState } from 'react';
import { AlertTriangle, BookOpen, CheckCircle2, GraduationCap, Info, TrendingUp, XCircle } from 'lucide-react';
import { apiFetch } from '../../services/apiFetch';

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

/**
 * Portal del estudiante: inicio con su nivel de riesgo actual (HU-37).
 * Las HU-38 a HU-42 (evolución del promedio, alertas, intervenciones,
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
      <Indicadores indicadores={datos.indicadores} />
    </div>
  );
}
