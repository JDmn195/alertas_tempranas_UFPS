import { useState } from 'react';
import { useNavigate, Link } from 'react-router';
import { Button } from '../components/ui/Button';
import { rutaInicio } from '../../services/session';
import { AuthLayout, campoAcceso, etiquetaAcceso } from '../components/layouts/AuthLayout';

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/api/usuarios/login/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (response.ok) {
        if (data.cambio_obligatorio) {
          // Guardar temporalmente el token de cambio para la pantalla de cambio
          localStorage.setItem('temp_forced_change', JSON.stringify({ token: data.token_cambio }));
          navigate('/reset-password');
          return;
        }

        // Guardar sesión en localStorage
        localStorage.setItem('user', JSON.stringify(data));
        
        // Redirigir según el rol (el estudiante entra directo a su portal)
        navigate(rutaInicio(data.rol));
      } else {
        setError(data.error || 'Error al iniciar sesión.');
      }
    } catch (err) {
      console.error('Error de login:', err);
      setError('Error de conexión con el servidor.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout>
      <h1 className="text-2xl font-semibold text-ink">Iniciar sesión en tu cuenta</h1>
      <p className="mt-1.5 mb-6 text-ink-muted">Usa tu correo institucional para entrar.</p>

  <form onSubmit={handleSubmit} className="space-y-5">
    {error && (
      <div role="alert" className="flex items-start gap-2.5 p-3 bg-red-100 border border-red-200 text-red-800 text-sm rounded-[10px]">
        {error}
      </div>
    )}
    <div>
      <label htmlFor="email" className={etiquetaAcceso}>
        Correo electrónico
      </label>
      <input
        id="email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        disabled={isLoading}
        autoComplete="username"
        className={campoAcceso}
        placeholder="usuario@ufps.edu.co"
      />
    </div>

    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor="password" className={etiquetaAcceso}>
          Contraseña
        </label>
        <Link to="/forgot-password" className="text-sm font-medium text-primary hover:underline">
          ¿Olvidaste tu contraseña?
        </Link>
      </div>
      <input
        id="password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        disabled={isLoading}
        autoComplete="current-password"
        className={campoAcceso}
        placeholder="••••••••"
      />
    </div>

    <Button type="submit" fullWidth size="lg" disabled={isLoading}>
      {isLoading ? 'Iniciando sesión...' : 'Iniciar sesión'}
    </Button>

  </form>

      <p className="mt-6 pt-5 border-t border-line text-sm text-ink-muted">
        ¿Eres estudiante y aún no tienes clave?{' '}
        <Link to="/forgot-password" className="font-medium text-primary hover:underline">
          ¿Estudiante? Activa tu cuenta
        </Link>
      </p>
    </AuthLayout>
  );
}
