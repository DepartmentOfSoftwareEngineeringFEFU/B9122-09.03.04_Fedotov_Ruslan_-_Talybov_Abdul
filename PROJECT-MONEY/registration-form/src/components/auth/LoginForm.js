import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { getErrorMessage } from '../../services/api';
import Icon from '../common/Icons';
import { ButtonLoader } from '../common/LoadingSpinner';

const heroCandles = [
  { left: '12%', top: '46%', height: '82px' },
  { left: '24%', top: '34%', height: '116px' },
  { left: '36%', top: '51%', height: '72px' },
  { left: '48%', top: '27%', height: '132px' },
  { left: '60%', top: '39%', height: '96px' },
  { left: '72%', top: '22%', height: '148px' },
  { left: '84%', top: '31%', height: '110px' },
];

export default function LoginForm() {
  const [formData, setFormData] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await login(formData.email, formData.password);
      navigate('/portfolio');
    } catch (error) {
      console.error('Ошибка входа:', error);
      setError(getErrorMessage(error, 'Не удалось войти. Проверьте email и пароль.'));
    } finally {
      setLoading(false);
    }
  };

  const useTestCredentials = () => {
    setFormData({ email: 'test@example.com', password: 'testpassword123' });
  };

  return (
    <div className="min-h-screen bg-[#070707] px-4 py-8 text-zinc-100">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-6xl items-center justify-center">
        <div className="grid w-full overflow-hidden rounded-[2rem] border border-zinc-800 bg-[#0b0b0b] shadow-2xl lg:grid-cols-[1fr_440px]">
          <div className="relative hidden min-h-[620px] overflow-hidden border-r border-zinc-800 bg-black p-10 lg:block">
            <div className="pointer-events-none absolute inset-0">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_24%_16%,rgba(250,204,21,0.18),transparent_28%),radial-gradient(circle_at_82%_78%,rgba(250,204,21,0.10),transparent_32%)]" />
              <div className="auth-hero-grid absolute inset-x-8 bottom-8 h-72 rounded-[2rem] border border-yellow-400/10 bg-[#0f0e0a]/85 shadow-[0_24px_90px_rgba(0,0,0,0.45)]" />
              <svg className="absolute bottom-20 left-16 right-16 h-56 w-[calc(100%-8rem)] text-yellow-300/80" viewBox="0 0 720 260" fill="none" aria-hidden="true">
                <path d="M8 210C72 184 112 198 168 148C226 96 286 118 342 90C404 58 452 78 510 46C582 8 642 34 712 18" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
                <path d="M8 210C72 184 112 198 168 148C226 96 286 118 342 90C404 58 452 78 510 46C582 8 642 34 712 18" stroke="currentColor" strokeWidth="18" strokeLinecap="round" opacity="0.08" />
              </svg>
              {heroCandles.map((candle) => (
                <span
                  key={`${candle.left}-${candle.height}`}
                  className="auth-candle absolute bottom-20"
                  style={{ left: candle.left, top: candle.top, height: candle.height }}
                />
              ))}
              <div className="absolute inset-x-0 bottom-0 h-48 bg-gradient-to-t from-black via-black/80 to-transparent" />
            </div>

          </div>

          <div className="p-6 sm:p-8 lg:p-10">
            <div className="mb-8 text-center lg:hidden">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-yellow-400 text-sm font-black text-black">QT</div>
              <h1 className="text-2xl font-semibold text-white">Quantum Trade</h1>
            </div>

            <div className="mb-8">
              <h2 className="text-3xl font-semibold tracking-tight text-white">Вход</h2>
              <p className="mt-2 text-sm text-zinc-500">Введите данные аккаунта, чтобы продолжить.</p>
              {process.env.NODE_ENV === 'development' && (
                <button type="button" onClick={useTestCredentials} className="mt-3 text-sm font-medium text-yellow-400 hover:text-yellow-300">
                  Использовать тестовые данные
                </button>
              )}
            </div>

            {error && (
              <div className="mb-5 rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
                <div className="flex items-start gap-3">
                  <Icon name="alert" className="mt-0.5 h-5 w-5 shrink-0 text-red-300" />
                  <div>
                    <div className="font-medium">{error}</div>
                    <div className="mt-1 text-xs text-red-300/75">Проверьте, что сервер проекта запущен.</div>
                  </div>
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-zinc-300">Email</span>
                <div className="relative">
                  <Icon name="mail" className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-500" />
                  <input
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    placeholder="Введите вашу почту"
                    required
                    className="app-input w-full rounded-2xl py-3 pl-12 pr-4"
                  />
                </div>
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-medium text-zinc-300">Пароль</span>
                <div className="relative">
                  <Icon name="lock" className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-500" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="Введите ваш пароль"
                    required
                    className="app-input w-full rounded-2xl py-3 pl-12 pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((current) => !current)}
                    className="absolute right-4 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-zinc-500 transition hover:text-yellow-300 focus:outline-none focus:ring-2 focus:ring-yellow-400/50"
                    aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                    title={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                  >
                    <Icon name={showPassword ? 'eyeOff' : 'eye'} className="h-5 w-5" />
                  </button>
                </div>
              </label>

              <button type="submit" disabled={loading} className="app-primary-button flex w-full items-center justify-center rounded-2xl px-5 py-3 disabled:cursor-not-allowed disabled:opacity-60">
                {loading ? <ButtonLoader label="Входим..." dark /> : 'Войти'}
              </button>
            </form>

            <div className="mt-6 border-t border-zinc-800 pt-5 text-center text-sm text-zinc-500">
              Нет аккаунта?{' '}
              <Link to="/register" className="font-semibold text-yellow-400 hover:text-yellow-300">
                Зарегистрироваться
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
