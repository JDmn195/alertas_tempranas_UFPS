import { useState } from 'react';
import { Link } from 'react-router';
import { ArrowLeft, MailCheck } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { AuthLayout, campoAcceso, etiquetaAcceso } from '../components/layouts/AuthLayout';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    setMessage('');

    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/api/usuarios/recuperar-password/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      const data = await response.json();

      if (response.ok) {
        setMessage(data.mensaje || 'Se ha enviado un correo con instrucciones.');
      } else {
        setError(data.error || 'Error al procesar la solicitud.');
      }
    } catch (err) {
      console.error('Error:', err);
      setError('Error de conexión con el servidor.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout>
      <Link to="/login" className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink mb-5">
        <ArrowLeft className="w-4 h-4" aria-hidden="true" />
        Volver al inicio de sesión
      </Link>

      {message ? (
        <div role="status">
          <div className="w-11 h-11 rounded-full bg-green-50 border border-green-200 text-green-700 flex items-center justify-center mb-4">
            <MailCheck className="w-5 h-5" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-semibold text-ink">Revisa tu correo</h1>
          <p className="mt-2 p-3 bg-green-100 border border-green-200 text-green-800 text-sm rounded-[10px]">{message}</p>
          <p className="mt-4 text-sm text-ink-muted">Si no llega en unos minutos, revisa la carpeta de correo no deseado.</p>
        </div>
      ) : (
        <>
          <h1 className="text-2xl font-semibold text-ink">Recuperar contraseña</h1>
          <p className="mt-1.5 text-ink-muted">Ingresa tu correo institucional para recibir un enlace de recuperación.</p>
          <p className="mt-4 mb-6 text-sm text-ink-soft bg-paper border border-line rounded-[10px] px-3.5 py-3">
            ¿Eres estudiante y es tu primer ingreso? Usa esta misma opción con tu correo institucional para activar tu
            cuenta y definir tu contraseña.
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div role="alert" className="p-3 bg-red-100 border border-red-200 text-red-800 text-sm rounded-[10px]">
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

            <Button type="submit" fullWidth size="lg" disabled={isLoading}>
              {isLoading ? 'Enviando...' : 'Enviar enlace de recuperación'}
            </Button>

            <p className="text-center">
              <Link to="/login" className="text-sm text-ink-muted hover:text-primary hover:underline">
                ¿Recordaste tu contraseña? Inicia sesión
              </Link>
            </p>
          </form>
        </>
      )}
    </AuthLayout>
  );
}
