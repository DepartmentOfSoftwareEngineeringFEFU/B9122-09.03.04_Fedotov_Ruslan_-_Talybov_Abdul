// src/components/backtest/Backtest.js
import React, { useEffect, useState } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { backtestAPI, getErrorMessage } from '../../services/api';
import LoadingSpinner, { ButtonLoader } from '../common/LoadingSpinner';

export default function Backtest() {
  const { isDark } = useTheme();
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const loadResults = async () => {
    try {
      setLoading(true);
      setMessage('');
      const response = await backtestAPI.getBacktestResults();
      setResults(response.data || []);
    } catch (error) {
      setMessage(getErrorMessage(error, 'Не удалось загрузить backtest-результаты'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadResults();
  }, []);

  const handleRunBacktest = async () => {
    setMessage('Backtest временно отключён: сначала нужно сохранить реальные результаты обученной модели.');
  };

  return (
    <div className="space-y-6">
      <div className={`rounded-3xl p-8 text-white shadow-2xl ${
        isDark
          ? 'bg-gradient-to-r from-zinc-950 to-zinc-900 border border-yellow-500/20'
          : 'bg-gradient-to-r from-blue-500 to-purple-600'
      }`}>
        <h1 className="text-3xl font-bold mb-2">Бэктестинг</h1>
        <p className={isDark ? 'text-yellow-100' : 'text-blue-100'}>
          Раздел оставлен для истории запусков. Новые запуски отключены до подключения сохранённых ML-артефактов.
        </p>
      </div>

      {message && (
        <div className={`rounded-2xl border p-4 ${
          isDark ? 'border-yellow-400/20 bg-yellow-400/10 text-yellow-200' : 'border-yellow-200 bg-yellow-50 text-yellow-900'
        }`}>
          {message}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white dark:bg-[#111111] rounded-3xl shadow-lg border border-gray-200 dark:border-zinc-800 p-6">
            <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">Статус модуля</h3>
            <p className="text-sm text-gray-600 dark:text-zinc-400 mb-5">
              Случайная генерация результатов удалена. Кнопка ниже ничего не исполняет и нужна только как явное объяснение состояния.
            </p>
            <button
              type="button"
              onClick={handleRunBacktest}
              className="w-full py-3 rounded-2xl font-semibold bg-yellow-400 text-black hover:bg-yellow-300 transition-colors"
            >
              Почему запуск отключён?
            </button>
          </div>
        </div>

        <div className="lg:col-span-2">
          <div className="bg-white dark:bg-[#111111] rounded-3xl shadow-lg border border-gray-200 dark:border-zinc-800 p-6">
            <div className="flex items-center justify-between gap-4 mb-4">
              <h3 className="text-xl font-semibold text-gray-800 dark:text-white">Сохранённые результаты</h3>
              <button
                type="button"
                onClick={loadResults}
                disabled={loading}
                className="inline-flex items-center justify-center rounded-xl border border-yellow-400/20 px-3 py-2 text-sm font-semibold text-yellow-300 hover:bg-yellow-400/10 disabled:opacity-50"
              >
                {loading ? <ButtonLoader label="Загружаем..." /> : 'Обновить'}
              </button>
            </div>
            {loading ? (
              <LoadingSpinner label="Загружаем результаты..." compact />
            ) : results.length === 0 ? (
              <div className={`h-64 rounded-2xl flex items-center justify-center text-center px-6 ${isDark ? 'bg-gray-800 text-gray-400' : 'bg-gray-100 text-gray-500'}`}>
                Сохранённых backtest-запусков пока нет.
              </div>
            ) : (
              <div className="space-y-3">
                {results.map((item) => (
                  <div key={item.id} className="rounded-2xl border border-zinc-800 bg-black/20 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <h4 className="font-semibold text-white">{item.name}</h4>
                        <p className="text-sm text-zinc-500">{(item.stock_symbols || []).join(', ')}</p>
                      </div>
                      <span className="text-sm font-semibold text-yellow-300">
                        {Number(item.total_return || 0).toLocaleString('ru-RU', { style: 'percent', maximumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
