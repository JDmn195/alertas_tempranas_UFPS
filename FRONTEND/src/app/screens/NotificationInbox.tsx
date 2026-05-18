import { useState, useEffect } from 'react';
import { Badge } from '../components/ui/Badge';
import { Mail, Check, Bell, Calendar, Filter } from 'lucide-react';

export default function NotificationInbox() {
  const [notifications, setNotifications] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filterPriority, setFilterPriority] = useState<string>('all');

  const fetchNotifications = async () => {
    const userStr = localStorage.getItem('user');
    if (!userStr) return;
    
    try {
      const user = JSON.parse(userStr);
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/api/alertas/notificaciones/internas/?usuario_id=${user.id}`);
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
      await fetch(`${baseUrl}/api/alertas/notificaciones/internas/${id}/leer/`, {
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

  return (
    <div className="max-w-4xl mx-auto space-y-6 pt-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="border-l-4 border-[#C8102E] pl-4">
          <h1 className="text-2xl font-bold text-gray-900">Bandeja de Notificaciones</h1>
          <p className="text-sm text-gray-600 mt-1">
            Avisos internos sobre el estado académico de tus estudiantes
          </p>
        </div>
        
        <div className="flex items-center gap-2 bg-white p-2 rounded-xl border border-gray-200 shadow-sm">
          <Filter className="w-4 h-4 text-gray-400 ml-2" />
          <select 
            value={filterPriority} 
            onChange={(e) => setFilterPriority(e.target.value)}
            className="text-xs font-bold text-gray-700 border-none focus:ring-0 bg-transparent cursor-pointer uppercase outline-none pr-8"
          >
            <option value="all">TODAS LAS PRIORIDADES</option>
            <option value="high">PRIORIDAD ALTA</option>
            <option value="medium">PRIORIDAD MEDIA</option>
            <option value="low">PRIORIDAD BAJA</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-10 text-center text-gray-500">Cargando notificaciones...</div>
        ) : notifications.length === 0 ? (
          <div className="p-20 text-center flex flex-col items-center">
            <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mb-4">
              <Bell className="w-8 h-8 text-gray-300" />
            </div>
            <p className="text-gray-500 font-medium">No tienes notificaciones pendientes</p>
            <p className="text-sm text-gray-400 mt-1">Te avisaremos cuando haya novedades</p>
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div className="p-20 text-center flex flex-col items-center">
            <p className="text-gray-500 font-medium">No hay notificaciones para este filtro</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredNotifications.map((notif) => (
              <div 
                key={notif.id} 
                className={`p-6 transition-colors ${notif.leida ? 'bg-white' : 'bg-red-50/30'}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className={`mt-1 w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                      notif.alerta.nivel === 'high' ? 'bg-red-100' : 
                      notif.alerta.nivel === 'medium' ? 'bg-yellow-100' : 'bg-gray-100'
                    }`}>
                      <Bell className={`w-5 h-5 ${
                        notif.alerta.nivel === 'high' ? 'text-red-600' : 
                        notif.alerta.nivel === 'medium' ? 'text-yellow-600' : 'text-gray-600'
                      }`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant={notif.alerta.nivel as any} size="sm">
                          Prioridad {notif.alerta.nivel === 'high' ? 'Alta' : notif.alerta.nivel === 'medium' ? 'Media' : 'Baja'}
                        </Badge>
                        <span className="text-xs text-gray-400 flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {new Date(notif.fecha).toLocaleString()}
                        </span>
                      </div>
                      <p className={`text-sm ${notif.leida ? 'text-gray-600' : 'text-gray-900 font-medium'}`}>
                        {notif.mensaje}
                      </p>
                    </div>
                  </div>
                  
                  {!notif.leida && (
                    <button 
                      onClick={() => markAsRead(notif.id)}
                      className="p-2 text-gray-400 hover:text-[#C8102E] hover:bg-red-50 rounded-lg transition-all"
                      title="Marcar como leída"
                    >
                      <Check className="w-5 h-5" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
