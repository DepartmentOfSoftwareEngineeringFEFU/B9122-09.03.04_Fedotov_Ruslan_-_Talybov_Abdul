import React from 'react';
import { ButtonLoader, TableLoader } from '../../common/LoadingSpinner';

const formatMoney = (value, digits = 2) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number.toLocaleString('ru-RU', { maximumFractionDigits: digits });
};

const recommendationLabels = {
  SELL: 'SELL',
  HOLD: 'HOLD',
  HOLD_AND_OPTIONAL_BUY: 'HOLD + BUY',
  BUY_OPTIONAL: 'BUY?',
  WAIT: 'WAIT',
  DO_NOT_BUY: 'NO BUY',
};

export default function ForecastHistoryPanel({ history = [], loading, onRefresh, filters, setFilters }) {
  return (
    <div className="rounded-3xl border border-gray-200 dark:border-zinc-800 bg-white dark:bg-[#111111] p-6 shadow-lg">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">История прогнозов</h2>
          <p className="text-sm text-gray-500 dark:text-zinc-500">Сохраненные прогнозы из `model_forecasts` и связь со сделками ML-бота.</p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="inline-flex items-center justify-center px-4 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 dark:bg-zinc-900 dark:hover:bg-gray-600 dark:text-white disabled:opacity-60"
        >
          {loading ? <ButtonLoader label="Загружаем..." /> : 'Обновить'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-5">
        <input
          value={filters.figi || ''}
          onChange={(event) => setFilters(prev => ({ ...prev, figi: event.target.value }))}
          placeholder="FIGI"
          className="rounded-xl px-4 py-3 outline-none border bg-gray-50 border-gray-200 dark:bg-[#070707] dark:border-zinc-800 dark:text-white"
        />
        <select
          value={filters.model_type || ''}
          onChange={(event) => setFilters(prev => ({ ...prev, model_type: event.target.value }))}
          className="rounded-xl px-4 py-3 outline-none border bg-gray-50 border-gray-200 dark:bg-[#070707] dark:border-zinc-800 dark:text-white"
        >
          <option value="">Все модели</option>
          <option value="svr">SVR</option>
          <option value="gpr">GPR</option>
          <option value="adaptive">Adaptive</option>
        </select>
        <select
          value={filters.horizon || ''}
          onChange={(event) => setFilters(prev => ({ ...prev, horizon: event.target.value }))}
          className="rounded-xl px-4 py-3 outline-none border bg-gray-50 border-gray-200 dark:bg-[#070707] dark:border-zinc-800 dark:text-white"
        >
          <option value="">Все горизонты</option>
          <option value="1h">1 час</option>
          <option value="1d">1 день</option>
        </select>
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-xl px-4 py-3 font-bold bg-yellow-400 hover:bg-yellow-300 text-black"
        >
          Применить
        </button>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-gray-200 dark:border-zinc-800">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-[#070707] text-gray-600 dark:text-zinc-300">
            <tr>
              <th className="px-4 py-3 text-left">Дата</th>
              <th className="px-4 py-3 text-left">Инструмент</th>
              <th className="px-4 py-3 text-left">Модель</th>
              <th className="px-4 py-3 text-left">Горизонт</th>
              <th className="px-4 py-3 text-right">Текущая</th>
              <th className="px-4 py-3 text-right">Прогноз</th>
              <th className="px-4 py-3 text-right">Δ %</th>
              <th className="px-4 py-3 text-left">Рекомендация</th>
              <th className="px-4 py-3 text-left">Сделка</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {loading ? (
              <TableLoader colSpan={9} label="Загружаем историю прогнозов..." />
            ) : history.map(item => (
              <tr key={item.id} className="text-gray-800 dark:text-gray-200">
                <td className="px-4 py-3 whitespace-nowrap">{item.created_at ? new Date(item.created_at).toLocaleString('ru-RU') : '—'}</td>
                <td className="px-4 py-3">
                  <div className="font-bold">{item.ticker || item.figi}</div>
                  <div className="text-xs text-gray-500 font-mono">{item.figi}</div>
                </td>
                <td className="px-4 py-3 uppercase">{item.model_type} → {item.model_type_effective || item.model_type}</td>
                <td className="px-4 py-3">{item.horizon}</td>
                <td className="px-4 py-3 text-right font-mono">{formatMoney(item.current_price)} ₽</td>
                <td className="px-4 py-3 text-right font-mono">{formatMoney(item.predicted_price)} ₽</td>
                <td className={`px-4 py-3 text-right font-mono ${item.price_delta_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>{formatMoney(item.price_delta_percent)}%</td>
                <td className="px-4 py-3">{recommendationLabels[item.recommendation] || item.recommendation}</td>
                <td className="px-4 py-3">{item.has_trade ? `да (${item.trade_count})` : 'нет'}</td>
              </tr>
            ))}
            {!loading && history.length === 0 && (
              <tr>
                <td className="px-4 py-8 text-center text-gray-500 dark:text-zinc-500" colSpan="9">Нет сохраненных прогнозов по выбранным фильтрам.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
