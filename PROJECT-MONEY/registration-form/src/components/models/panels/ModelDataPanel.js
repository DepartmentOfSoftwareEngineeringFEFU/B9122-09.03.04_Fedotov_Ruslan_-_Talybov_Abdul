import React from 'react';
import DataQualityCard from './DataQualityCard';
import { TableLoader } from '../../common/LoadingSpinner';

const formatNumber = (value, digits = 2) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number.toLocaleString('ru-RU', { maximumFractionDigits: digits });
};

export default function ModelDataPanel({
  dataQuality,
  selectedInstrument,
  forecastHorizon,
  dataQualityLoading,
  loadingCandles,
  refreshDataQuality,
  candles,
  currentDataInfo,
  loadCandles,
  userCandles,
  loadUserCandles,
  deleteUserCandles,
  selectInstrument,
}) {
  const features = dataQuality?.feature_names || [];

  return (
    <div className="space-y-6">
      <DataQualityCard
        dataQuality={dataQuality}
        selectedInstrument={selectedInstrument}
        forecastHorizon={forecastHorizon}
        loading={dataQualityLoading}
        onRefresh={refreshDataQuality}
      />

      <div className="rounded-3xl border border-gray-200 dark:border-zinc-800 bg-white dark:bg-[#111111] p-6 shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">Загрузка свечей</h3>
            <p className="text-sm text-gray-500 dark:text-zinc-500">Текущий FIGI: {currentDataInfo.figi}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => loadCandles(currentDataInfo.figi, 1)} className="px-3 py-2 rounded-lg border border-gray-300 dark:border-zinc-700 hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-zinc-300">1 день</button>
            <button type="button" onClick={() => loadCandles(currentDataInfo.figi, 7)} className="px-3 py-2 rounded-lg border border-gray-300 dark:border-zinc-700 hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-zinc-300">1 неделя</button>
            <button type="button" onClick={() => loadCandles(currentDataInfo.figi, 30)} className="px-3 py-2 rounded-lg border border-gray-300 dark:border-zinc-700 hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-zinc-300">1 месяц</button>
          </div>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-gray-200 dark:border-zinc-800 max-h-96">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-gray-50 dark:bg-[#070707] text-gray-600 dark:text-zinc-300">
              <tr>
                <th className="px-3 py-2 text-left">Время</th>
                <th className="px-3 py-2 text-right">Open</th>
                <th className="px-3 py-2 text-right">High</th>
                <th className="px-3 py-2 text-right">Low</th>
                <th className="px-3 py-2 text-right">Close</th>
                <th className="px-3 py-2 text-right">Volume</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {loadingCandles ? (
                <TableLoader colSpan={6} label="Загружаем свечи..." />
              ) : candles.slice().reverse().map((item, index) => (
                <tr key={`${item.time || item.x}-${index}`} className="text-gray-700 dark:text-zinc-300">
                  <td className="px-3 py-2 whitespace-nowrap">{item.time ? new Date(item.time).toLocaleString('ru-RU') : '—'}</td>
                  <td className="px-3 py-2 text-right font-mono">{formatNumber(item.open ?? item.o)}</td>
                  <td className="px-3 py-2 text-right font-mono">{formatNumber(item.high ?? item.h)}</td>
                  <td className="px-3 py-2 text-right font-mono">{formatNumber(item.low ?? item.l)}</td>
                  <td className="px-3 py-2 text-right font-mono">{formatNumber(item.close ?? item.c)}</td>
                  <td className="px-3 py-2 text-right font-mono">{formatNumber(item.volume ?? item.v, 0)}</td>
                </tr>
              ))}
              {!loadingCandles && candles.length === 0 && (
                <tr><td className="px-3 py-8 text-center text-gray-500" colSpan="6">Нет свечей.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-3xl border border-gray-200 dark:border-zinc-800 bg-white dark:bg-[#111111] p-6 shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">Сохраненные наборы свечей</h3>
            <button type="button" onClick={loadUserCandles} className="text-sm px-3 py-2 rounded-lg bg-gray-100 dark:bg-zinc-900 dark:text-white">Обновить</button>
          </div>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {userCandles.map((item, index) => (
              <div key={`${item.figi}-${index}`} className="rounded-xl p-4 bg-gray-50 dark:bg-[#070707] border border-gray-200 dark:border-zinc-800">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-mono font-bold text-gray-900 dark:text-white">{item.figi}</div>
                    <div className="text-xs text-gray-500">Свечей: {item.candle_count}</div>
                    <div className="text-xs text-gray-500">{item.first_date ? new Date(item.first_date).toLocaleDateString('ru-RU') : '—'} — {item.last_date ? new Date(item.last_date).toLocaleDateString('ru-RU') : '—'}</div>
                  </div>
                  <div className="flex gap-2">
                    <button type="button" onClick={() => selectInstrument({ figi: item.figi, ticker: item.figi }, 'manual')} className="text-xs px-3 py-2 rounded-lg bg-yellow-400 text-black">Выбрать</button>
                    <button type="button" onClick={() => deleteUserCandles(item.figi)} className="text-xs px-3 py-2 rounded-lg bg-red-50 text-red-600 dark:bg-red-900/20">Удалить</button>
                  </div>
                </div>
              </div>
            ))}
            {userCandles.length === 0 && <div className="py-8 text-center text-gray-500">Нет сохраненных наборов свечей.</div>}
          </div>
        </div>

        <div className="rounded-3xl border border-gray-200 dark:border-zinc-800 bg-white dark:bg-[#111111] p-6 shadow-lg">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Признаки модели</h3>
          <p className="text-sm text-gray-500 dark:text-zinc-500 mb-4">Единый обработчик данных формирует лаги цены, доходности, rolling-статистики и лаги объема.</p>
          <div className="flex flex-wrap gap-2 max-h-80 overflow-y-auto">
            {features.map(feature => (
              <span key={feature} className="px-3 py-2 rounded-lg text-xs font-mono bg-gray-100 text-gray-700 dark:bg-[#070707] dark:text-zinc-300 border border-gray-200 dark:border-zinc-800">{feature}</span>
            ))}
            {features.length === 0 && <div className="text-gray-500">Признаки появятся после проверки данных.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
