import { useState } from 'react';
import { useNavigate, Link } from 'react-router';
import { Button } from '../components/ui/Button';

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
          // Guardar temporalmente para la pantalla de cambio
          localStorage.setItem('temp_forced_change', JSON.stringify({ id: data.id }));
          navigate('/reset-password');
          return;
        }

        // Guardar sesión en localStorage
        localStorage.setItem('user', JSON.stringify(data));
        
        // Redirigir según el rol (de momento todos al mismo)
        navigate('/dashboard/admin/import');
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
    <div className="min-h-screen bg-[#F5F5F5] flex flex-col">
      {/* Red header bar */}
      <div className="h-2 bg-[#C8102E]" />

      {/* Login content */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          {/* Logo and title */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-[#C8102E] rounded-2xl mb-6">
              <span className="text-white font-bold text-4xl">U</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Universidad Francisco de Paula Santander
            </h1>
            <p className="text-sm text-gray-600">
              Plataforma de Alertas Tempranas Académicas
            </p>
          </div>

          {/* Login card */}
          <div className="bg-white rounded-lg border border-gray-200 p-8 shadow-sm">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Iniciar sesión en tu cuenta</h2>

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

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                  Contraseña
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

              <div className="flex items-center justify-between">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    className="w-4 h-4 text-[#C8102E] border-gray-300 rounded focus:ring-[#C8102E]"
                  />
                  <span className="ml-2 text-sm text-gray-600">Recordarme</span>
                </label>
                <Link to="/forgot-password" size="sm" className="text-sm text-[#C8102E] hover:underline">
                  ¿Olvidaste tu contraseña?
                </Link>
              </div>

              <Button type="submit" fullWidth size="lg" disabled={isLoading}>
                {isLoading ? 'Iniciando sesión...' : 'Iniciar sesión'}
              </Button>
            </form>
          </div>

          {/* Footer */}
          <p className="text-center text-xs text-gray-500 mt-8">
            © 2026 Universidad Francisco de Paula Santander. Todos los derechos reservados.
          </p>
        </div>
      </div>
    </div>
  );
}
