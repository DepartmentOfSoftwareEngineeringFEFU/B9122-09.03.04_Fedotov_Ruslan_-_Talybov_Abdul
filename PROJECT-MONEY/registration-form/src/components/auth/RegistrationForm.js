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

export default function RegistrationForm() {
  const [formData, setFormData] = useState({ username: '', email: '', password: '', tinkoff_token: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const { register } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError('');
    setSuccess('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await register(formData);
      setSuccess('Регистрация успешна. Сейчас откроется страница входа.');
      setTimeout(() => navigate('/login'), 600);
    } catch (error) {
      console.error('Ошибка регистрации:', error);
      setError(getErrorMessage(error, 'Не удалось создать аккаунт. Проверьте данные и повторите попытку.'));
    } finally {
      setLoading(false);
    }
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
              <h2 className="text-3xl font-semibold tracking-tight text-white">Регистрация</h2>
              <p className="mt-2 text-sm text-zinc-500">Создайте аккаунт для работы с торговой системой.</p>
            </div>

            {error && (
              <div className="mb-5 rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
                <div className="flex items-start gap-3">
                  <Icon name="alert" className="mt-0.5 h-5 w-5 shrink-0 text-red-300" />
                  <div className="font-medium">{error}</div>
                </div>
              </div>
            )}

            {success && (
              <div className="mb-5 rounded-2xl border border-green-500/30 bg-green-500/10 p-4 text-sm text-green-200">
                <div className="font-medium">{success}</div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-zinc-300">Имя пользователя</span>
                <div className="relative">
                  <Icon name="user" className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-500" />
                  <input
                    type="text"
                    name="username"
                    value={formData.username}
                    onChange={handleChange}
                    placeholder="Введите имя пользователя"
                    required
                    minLength={3}
                    maxLength={100}
                    className="app-input w-full rounded-2xl py-3 pl-12 pr-4"
                  />
                </div>
              </label>

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
                    maxLength={255}
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
                    minLength={6}
                    maxLength={128}
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

              <label className="block">
                <span className="mb-2 block text-sm font-medium text-zinc-300">T-Invest API Token</span>
                <div className="relative">
                  <Icon name="key" className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-500" />
                  <input
                    type="text"
                    name="tinkoff_token"
                    value={formData.tinkoff_token}
                    onChange={handleChange}
                    placeholder="Опционально"
                    maxLength={500}
                    className="app-input w-full rounded-2xl py-3 pl-12 pr-4"
                  />
                </div>
              </label>

              <button type="submit" disabled={loading} className="app-primary-button flex w-full items-center justify-center rounded-2xl px-5 py-3 disabled:cursor-not-allowed disabled:opacity-60">
                {loading ? <ButtonLoader label="Создаем..." dark /> : 'Создать аккаунт'}
              </button>
            </form>

            <div className="mt-6 border-t border-zinc-800 pt-5 text-center text-sm text-zinc-500">
              Уже есть аккаунт?{' '}
              <Link to="/login" className="font-semibold text-yellow-400 hover:text-yellow-300">
                Войти
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
