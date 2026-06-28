import React from 'react';
import { ButtonLoader } from '../../common/LoadingSpinner';

const qualityStyles = {
  ready_all: 'border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-900/20 dark:text-green-200',
  ready_svr_only: 'border-yellow-200 bg-yellow-50 text-yellow-800 dark:border-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200',
  not_ready: 'border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200',
};

export default function DataQualityCard({ dataQuality, selectedInstrument, forecastHorizon, loading, onRefresh }) {
  const quality = dataQuality || {};
  const style = qualityStyles[quality.quality_status] || 'border-gray-200 bg-gray-50 text-gray-700 dark:border-zinc-800 dark:bg-[#070707] dark:text-zinc-300';
  const required = quality.required_samples || {};

  return (
    <div className="rounded-3xl border border-gray-200 dark:border-zinc-800 bg-white dark:bg-[#111111] p-6 shadow-lg">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">Качество данных</h3>
          <p className="text-sm text-gray-500 dark:text-zinc-500">Проверка перед обучением и прогнозом.</p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="inline-flex items-center justify-center px-3 py-2 text-sm rounded-xl bg-gray-100 hover:bg-gray-200 dark:bg-zinc-900 dark:hover:bg-gray-600 dark:text-white disabled:opacity-60"
        >
          {loading ? <ButtonLoader label="Проверяем..." /> : 'Обновить'}
        </button>
      </div>

      <div className={`rounded-2xl border p-4 mb-4 ${style}`}>
        <div className="font-bold mb-1">{quality.quality_message || 'Данные еще не проверены.'}</div>
        <div className="text-xs opacity-80">{selectedInstrument?.ticker || selectedInstrument?.figi || '—'} · горизонт {forecastHorizon}</div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div className="rounded-xl p-3 bg-gray-50 dark:bg-[#070707] border border-gray-200 dark:border-zinc-800">
          <div className="text-xs text-gray-500">Свечей</div>
          <div className="font-bold text-gray-900 dark:text-white">{quality.candle_count ?? '—'}</div>
        </div>
        <div className="rounded-xl p-3 bg-gray-50 dark:bg-[#070707] border border-gray-200 dark:border-zinc-800">
          <div className="text-xs text-gray-500">Валидных close</div>
          <div className="font-bold text-gray-900 dark:text-white">{quality.valid_close_count ?? '—'}</div>
        </div>
        <div className="rounded-xl p-3 bg-gray-50 dark:bg-[#070707] border border-gray-200 dark:border-zinc-800">
          <div className="text-xs text-gray-500">Мин. SVR</div>
          <div className="font-bold text-gray-900 dark:text-white">{required.svr ?? '—'}</div>
        </div>
        <div className="rounded-xl p-3 bg-gray-50 dark:bg-[#070707] border border-gray-200 dark:border-zinc-800">
          <div className="text-xs text-gray-500">Мин. GPR/adaptive</div>
          <div className="font-bold text-gray-900 dark:text-white">{required.gpr ?? '—'}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 text-xs text-gray-500 dark:text-zinc-500">
        <div>Период с: {quality.first_date ? new Date(quality.first_date).toLocaleString('ru-RU') : '—'}</div>
        <div>Последняя свеча: {quality.last_date ? new Date(quality.last_date).toLocaleString('ru-RU') : '—'}</div>
      </div>
    </div>
  );
}
