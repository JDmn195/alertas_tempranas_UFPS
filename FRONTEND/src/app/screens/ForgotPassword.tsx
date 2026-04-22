import { useState } from 'react';
import { Link } from 'react-router';
import { Button } from '../components/ui/Button';

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
    <div className="min-h-screen bg-[#F5F5F5] flex flex-col">
      <div className="h-2 bg-[#C8102E]" />
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-[#C8102E] rounded-2xl mb-6">
              <span className="text-white font-bold text-4xl">U</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Recuperar contraseña</h1>
            <p className="text-sm text-gray-600">
              Ingresa tu correo institucional para recibir un enlace de recuperación.
            </p>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-8 shadow-sm">
            {message ? (
              <div className="text-center">
                <div className="p-3 bg-green-100 border border-green-200 text-green-700 text-sm rounded-lg mb-6">
                  {message}
                </div>
                <Link to="/login" className="text-[#C8102E] font-medium hover:underline">
                  Volver al inicio de sesión
                </Link>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                  <div className="p-3 bg-red-100 border border-red-200 text-red-700 text-sm rounded-lg">
                    {error}
                  </div>
                )}
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                    Correo electrónico
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={isLoading}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C8102E] focus:border-transparent disabled:opacity-50"
                    placeholder="usuario@ufps.edu.co"
                  />
                </div>

                <Button type="submit" fullWidth size="lg" disabled={isLoading}>
                  {isLoading ? 'Enviando...' : 'Enviar enlace de recuperación'}
                </Button>

                <div className="text-center">
                  <Link to="/login" className="text-sm text-gray-600 hover:text-[#C8102E] hover:underline">
                    ¿Recordaste tu contraseña? Inicia sesión
                  </Link>
                </div>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
