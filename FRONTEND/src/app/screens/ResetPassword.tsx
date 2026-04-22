import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router';
import { Button } from '../components/ui/Button';

export default function ResetPassword() {
  const navigate = useNavigate();
  const { token } = useParams(); // Del link de correo
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isForced, setIsForced] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    // Si no hay token, verificamos si es un cambio obligatorio (guardado en localStorage temporalmente)
    if (!token) {
      const forcedData = localStorage.getItem('temp_forced_change');
      if (forcedData) {
        const { id } = JSON.parse(forcedData);
        setUserId(id);
        setIsForced(true);
      } else {
        // Si no hay nada, redirigir a login
        navigate('/login');
      }
    }
  }, [token, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (password !== confirmPassword) {
      setError('Las contraseñas no coinciden.');
      return;
    }

    if (password.length < 6) {
      setError('La contraseña debe tener al menos 6 caracteres.');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/api/usuarios/cambiar-password/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          token, 
          password,
          user_id: userId // Solo para cambio obligatorio
        }),
      });

      const data = await response.json();

      if (response.ok) {
        setSuccess(true);
        if (isForced) {
          localStorage.removeItem('temp_forced_change');
        }
      } else {
        setError(data.error || 'Error al actualizar la contraseña.');
      }
    } catch (err) {
      console.error('Error:', err);
      setError('Error de conexión con el servidor.');
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-[#F5F5F5] flex flex-col">
        <div className="h-2 bg-[#C8102E]" />
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-md bg-white rounded-lg border border-gray-200 p-8 shadow-sm text-center">
            <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">¡Contraseña actualizada!</h2>
            <p className="text-gray-600 mb-6">Tu contraseña ha sido cambiada con éxito. Ya puedes iniciar sesión.</p>
            <Button onClick={() => navigate('/login')} fullWidth size="lg">
              Ir al inicio de sesión
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F5F5F5] flex flex-col">
      <div className="h-2 bg-[#C8102E]" />
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-[#C8102E] rounded-2xl mb-6">
              <span className="text-white font-bold text-4xl">U</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              {isForced ? 'Cambio de contraseña obligatorio' : 'Establecer nueva contraseña'}
            </h1>
            <p className="text-sm text-gray-600">
              {isForced 
                ? 'Por seguridad, debes cambiar tu contraseña inicial para continuar.'
                : 'Ingresa tu nueva contraseña a continuación.'}
            </p>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-8 shadow-sm">
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="p-3 bg-red-100 border border-red-200 text-red-700 text-sm rounded-lg">
                  {error}
                </div>
              )}
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                  Nueva contraseña
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={isLoading}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent disabled:opacity-50"
                  placeholder="••••••••"
                />
              </div>

              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-2">
                  Confirmar contraseña
                </label>
                <input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  disabled={isLoading}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent disabled:opacity-50"
                  placeholder="••••••••"
                />
              </div>

              <Button type="submit" fullWidth size="lg" disabled={isLoading}>
                {isLoading ? 'Actualizando...' : 'Cambiar contraseña'}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
