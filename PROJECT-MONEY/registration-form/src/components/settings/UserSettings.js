import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { getErrorMessage } from '../../services/api';
import Icon from '../common/Icons';
import { ButtonLoader } from '../common/LoadingSpinner';

export default function UserSettings() {
  const { currentUser, updateTinkoffToken } = useAuth();
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    setMessage('');
    setError('');

    const nextToken = token.trim();
    if (nextToken.length < 10 || nextToken.length > 500) {
      setError('Введите T-Invest API Token длиной от 10 до 500 символов.');
      return;
    }

    try {
      setLoading(true);
      const result = await updateTinkoffToken(nextToken);
      setToken('');
      setMessage(`Токен проверен и сохранен: ${result.tinkoff_token_masked || '***'}`);
    } catch (requestError) {
      setError(getErrorMessage(requestError, 'Не удалось проверить и сохранить токен. Проверьте токен и права доступа.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid max-w-5xl grid-cols-1 gap-6 lg:grid-cols-[1fr_1.2fr]">
        <div className="app-card rounded-3xl p-6">
          <h2 className="mb-5 text-lg font-semibold text-white">Профиль</h2>
          <div className="space-y-4">
            <div className="app-muted-card rounded-2xl p-4">
              <div className="text-sm text-zinc-500">Пользователь</div>
              <div className="mt-1 font-semibold text-white">{currentUser?.username || '—'}</div>
              <div className="text-sm text-zinc-500">{currentUser?.email || '—'}</div>
            </div>
            <div className="app-muted-card rounded-2xl p-4">
              <div className="text-sm text-zinc-500">Текущий токен</div>
              <div className="mt-1 font-mono font-semibold text-white">
                {currentUser?.has_tinkoff_token ? currentUser?.tinkoff_token_masked : 'Не задан'}
              </div>
            </div>
          </div>
        </div>

        <div className="app-card rounded-3xl p-6">
          <h2 className="mb-5 text-lg font-semibold text-white">T-Invest API Token</h2>

          {message && (
            <div className="mb-4 flex gap-3 rounded-2xl border border-green-500/30 bg-green-500/10 p-4 text-sm text-green-200">
              <Icon name="check" className="h-5 w-5 shrink-0 text-green-300" />
              <span>{message}</span>
            </div>
          )}
          {error && (
            <div className="mb-4 flex gap-3 rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
              <Icon name="alert" className="h-5 w-5 shrink-0 text-red-300" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-zinc-300">Новый токен</span>
              <input
                type="password"
                value={token}
                onChange={(event) => setToken(event.target.value.slice(0, 500))}
                minLength={10}
                maxLength={500}
                autoComplete="off"
                className="app-input w-full rounded-2xl px-4 py-3"
                placeholder="Вставьте новый токен"
                disabled={loading}
              />
            </label>

            <button type="submit" disabled={loading || token.trim().length < 10} className="app-primary-button inline-flex items-center justify-center rounded-2xl px-5 py-3 disabled:cursor-not-allowed disabled:opacity-50">
              {loading ? <ButtonLoader label="Проверяем..." dark /> : 'Проверить и сохранить'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
