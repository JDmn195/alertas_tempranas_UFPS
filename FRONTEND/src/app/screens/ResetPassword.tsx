import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router';
import { Check } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { AuthLayout, campoAcceso, etiquetaAcceso } from '../components/layouts/AuthLayout';

export default function ResetPassword() {
  const navigate = useNavigate();
  const { token } = useParams(); // Del link de correo
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isForced, setIsForced] = useState(false);
  const [forcedToken, setForcedToken] = useState<string | null>(null);

  useEffect(() => {
    // Si no hay token, verificamos si es un cambio obligatorio (guardado en localStorage temporalmente)
    if (!token) {
      const forcedData = localStorage.getItem('temp_forced_change');
      if (forcedData) {
        const { token: tokenCambio } = JSON.parse(forcedData);
        setForcedToken(tokenCambio);
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

    if (password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.');
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
          // Del enlace de recuperación o, en el cambio obligatorio, del login
          token: token || forcedToken,
          password,
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
      <AuthLayout>
        <div role="status">
          <div className="w-11 h-11 rounded-full bg-green-50 border border-green-200 text-green-700 flex items-center justify-center mb-4">
            <Check className="w-5 h-5" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-semibold text-ink">¡Contraseña actualizada!</h1>
          <p className="mt-1.5 mb-6 text-ink-muted">Tu contraseña ha sido cambiada con éxito. Ya puedes iniciar sesión.</p>
          <Button onClick={() => navigate('/login')} fullWidth size="lg">
            Ir al inicio de sesión
          </Button>
        </div>
      </AuthLayout>
    );
  }

  const largoOk = password.length >= 8;
  const coinciden = confirmPassword.length > 0 && password === confirmPassword;

  return (
    <AuthLayout>
      <h1 className="text-2xl font-semibold text-ink">
        {isForced ? 'Cambio de contraseña obligatorio' : 'Establecer nueva contraseña'}
      </h1>
      <p className="mt-1.5 mb-6 text-ink-muted">
        {isForced
          ? 'Por seguridad, debes cambiar tu contraseña inicial para continuar.'
          : 'Ingresa tu nueva contraseña a continuación.'}
      </p>

      <form onSubmit={handleSubmit} className="space-y-5">
        {error && (
          <div role="alert" className="p-3 bg-red-100 border border-red-200 text-red-800 text-sm rounded-[10px]">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="password" className={etiquetaAcceso}>
            Nueva contraseña
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={isLoading}
            autoComplete="new-password"
            aria-describedby="requisitos-clave"
            className={campoAcceso}
            placeholder="••••••••"
          />
        </div>

        <div>
          <label htmlFor="confirmPassword" className={etiquetaAcceso}>
            Confirmar contraseña
          </label>
          <input
            id="confirmPassword"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            disabled={isLoading}
            autoComplete="new-password"
            aria-describedby="requisitos-clave"
            className={campoAcceso}
            placeholder="••••••••"
          />
        </div>

        {/* Los requisitos se marcan mientras se escribe; la validación al enviar no cambia */}
        <ul id="requisitos-clave" className="space-y-1.5 text-sm">
          {[
            [largoOk, 'Al menos 8 caracteres'],
            [coinciden, 'Las dos contraseñas coinciden'],
          ].map(([ok, texto]) => (
            <li key={texto as string} className={`flex items-center gap-2 ${ok ? 'text-green-700' : 'text-ink-muted'}`}>
              <span className={`w-4 h-4 rounded-full border flex items-center justify-center ${ok ? 'bg-green-600 border-green-600 text-white' : 'border-line-strong'}`} aria-hidden="true">
                {ok && <Check className="w-3 h-3" strokeWidth={3} />}
              </span>
              {texto}
            </li>
          ))}
        </ul>

        <Button type="submit" fullWidth size="lg" disabled={isLoading}>
          {isLoading ? 'Actualizando...' : 'Cambiar contraseña'}
        </Button>
      </form>
    </AuthLayout>
  );
}
