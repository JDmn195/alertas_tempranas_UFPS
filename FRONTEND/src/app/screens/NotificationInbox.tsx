import { useState, useEffect } from 'react';
import { Badge } from '../components/ui/Badge';
import { Mail, Check, Bell, Calendar, Filter } from 'lucide-react';
import { apiFetch } from '../../services/apiFetch';

import { CargandoBloque, EstadoVacio } from '../components/Estados';
import { EncabezadoPagina } from '../components/Panel';
import { MedidorRiesgo } from '../components/Riesgo';
export default function NotificationInbox() {
  const [notifications, setNotifications] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filterPriority, setFilterPriority] = useState<string>('all');

  const fetchNotifications = async () => {
    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      // El backend devuelve las notificaciones del usuario del token
      const response = await apiFetch(`${baseUrl}/api/alertas/notificaciones/internas/`);
      const data = await response.json();
      setNotifications(data.notificaciones || []);
    } catch (error) {
      console.error("Error fetching notifications:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const markAsRead = async (id: number) => {
    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      await apiFetch(`${baseUrl}/api/alertas/notificaciones/internas/${id}/leer/`, {
        method: 'POST'
      });
      setNotifications(notifications.map(n => n.id === id ? {...n, leida: true} : n));
    } catch (error) {
      console.error("Error marking as read:", error);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, []);

  const filteredNotifications = filterPriority === 'all' 
    ? notifications 
    : notifications.filter(n => n.alerta?.nivel === filterPriority);

  const sinLeer = notifications.filter((n) => !n.leida).length;
  const prioridades: [string, string][] = [
    ['all', 'Todas'],
    ['high', 'Prioridad alta'],
    ['medium', 'Prioridad media'],
    ['low', 'Prioridad baja'],
  ];
  const cuenta = (clave: string) =>
    clave === 'all' ? notifications.length : notifications.filter((n) => n.alerta?.nivel === clave).length;

  return (
    <div className="max-w-4xl space-y-5">
      <EncabezadoPagina
        titulo="Bandeja de Notificaciones"
        detalle="Avisos internos sobre el estado académico de tus estudiantes"
      >
        {!isLoading && (
          <p className="text-sm text-ink-muted">
            <span className="font-semibold text-ink">{sinLeer}</span> sin leer de {notifications.length}
          </p>
        )}
      </EncabezadoPagina>

      {/* Prioridad: filtro visible con la cantidad de avisos de cada nivel */}
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por prioridad">
        {prioridades.map(([clave, texto]) => (
          <button
            key={clave}
            type="button"
            onClick={() => setFilterPriority(clave)}
            aria-pressed={filterPriority === clave}
            className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-sm font-medium ${
              filterPriority === clave
                ? 'border-primary bg-primary text-white'
                : 'border-line bg-white text-ink-soft hover:border-line-strong hover:text-ink'
            }`}
          >
            {clave !== 'all' && <MedidorRiesgo nivel={clave} />}
            {texto}
            <span className={filterPriority === clave ? 'text-white/80' : 'text-ink-muted'}>{isLoading ? '—' : cuenta(clave)}</span>
          </button>
        ))}
      </div>

      <div className="bg-white rounded-[14px] border border-line overflow-hidden">
        {isLoading ? (
          <CargandoBloque texto="Cargando notificaciones..." filas={5} />
        ) : notifications.length === 0 ? (
          <EstadoVacio icono={Bell} titulo="No tienes notificaciones pendientes" detalle="Te avisaremos cuando haya novedades" />
        ) : filteredNotifications.length === 0 ? (
          <EstadoVacio titulo="No hay notificaciones para este filtro" detalle="Prueba con otro filtro o vuelve más tarde." />
        ) : (
          <ul className="divide-y divide-wash">
            {filteredNotifications.map((notif) => (
              <li
                key={notif.id}
                className={`px-4 sm:px-5 py-4 flex items-start gap-3 ${notif.leida ? '' : 'bg-primary-tint/40'}`}
              >
                {/* Punto de lectura: lleno si está sin leer */}
                <span
                  className={`mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ${notif.leida ? 'border border-line-strong' : 'bg-primary'}`}
                  role="img"
                  aria-label={notif.leida ? 'Leída' : 'Sin leer'}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-1">
                    {/* HU-41: las de una solicitud de acompañamiento no tienen alerta */}
                    {notif.alerta ? (
                      <Badge variant={notif.alerta.nivel as any} size="sm">
                        Prioridad {notif.alerta.nivel === 'high' ? 'Alta' : notif.alerta.nivel === 'medium' ? 'Media' : 'Baja'}
                      </Badge>
                    ) : (
                      <Badge variant="gray" size="sm">Solicitud de acompañamiento</Badge>
                    )}
                    <span className="text-xs text-ink-muted flex items-center gap-1">
                      <Calendar className="w-3 h-3" aria-hidden="true" />
                      {new Date(notif.fecha).toLocaleString()}
                    </span>
                  </div>
                  <p className={`text-sm ${notif.leida ? 'text-ink-muted' : 'text-ink font-medium'}`}>
                    {notif.mensaje}
                  </p>
                </div>

                {!notif.leida && (
                  <button
                    onClick={() => markAsRead(notif.id)}
                    className="shrink-0 inline-flex items-center gap-1.5 rounded-[10px] border border-line bg-white px-2.5 py-1.5 text-xs font-medium text-ink-soft hover:border-primary hover:text-primary"
                    title="Marcar como leída"
                  >
                    <Check className="w-4 h-4" aria-hidden="true" />
                    <span className="hidden sm:inline">Marcar como leída</span>
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
