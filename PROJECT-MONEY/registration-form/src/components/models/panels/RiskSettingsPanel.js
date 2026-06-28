import React from 'react';
import { sanitizeNumberInput } from '../../../utils/numberInput';

export default function RiskSettingsPanel({
  flatThresholdPercent,
  setFlatThresholdPercent,
  riskSettings,
  setRiskSettings,
  forecastResult,
}) {
  const update = (key, value) => setRiskSettings(prev => ({ ...prev, [key]: value }));
  const recommendation = forecastResult?.recommendation || {};
  const currentPrice = Number(forecastResult?.current_price || 0);
  const predictedPrice = Number(forecastResult?.predicted_price || 0);
  const riskWarnings = [];

  if (forecastResult && Math.abs(Number(forecastResult.price_delta_percent || 0)) < Number(flatThresholdPercent || 1)) {
    riskWarnings.push('Сигнал слабый: прогнозное изменение внутри flat-порога.');
  }
  if (recommendation.has_position && Number(recommendation.quantity || 0) > 0 && Number(recommendation.expected_profit_from_avg_percent || 0) < 0) {
    riskWarnings.push('Прогнозная цена ниже средней цены покупки. Продажа может зафиксировать убыток.');
  }
  if (currentPrice > 0 && predictedPrice > 0 && Math.abs(predictedPrice - currentPrice) / currentPrice * 100 > 8) {
    riskWarnings.push('Прогнозное изменение слишком резкое. Проверь данные и горизонт прогноза.');
  }
  if (!forecastResult) {
    riskWarnings.push('Построй прогноз, чтобы увидеть риск-предупреждения по конкретному сигналу.');
  }

  const inputClass = 'rounded-xl px-4 py-3 outline-none border bg-gray-50 border-gray-200 dark:bg-[#070707] dark:border-zinc-800 dark:text-white';

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-gray-200 dark:border-zinc-800 bg-white dark:bg-[#111111] p-6 shadow-lg">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Риск-контроль сигнала</h2>
        <p className="text-sm text-gray-500 dark:text-zinc-500 mb-5">Эти настройки влияют на интерпретацию сигнала в интерфейсе.</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="text-sm text-gray-700 dark:text-zinc-300">
            Flat-порог, %
            <input
              type="number"
              min="0.1"
              max="10"
              step="0.1"
              value={flatThresholdPercent}
              onChange={(event) => setFlatThresholdPercent(sanitizeNumberInput(event.target.value, { min: 0.1, max: 10, integer: false, maxLength: 5 }))}
              className={`mt-2 w-full ${inputClass}`}
            />
          </label>
          <label className="text-sm text-gray-700 dark:text-zinc-300">
            Макс. доля актива, %
            <input
              type="number"
              min="1"
              max="100"
              value={riskSettings.maxPositionSharePercent}
              onChange={(event) => update('maxPositionSharePercent', sanitizeNumberInput(event.target.value, { min: 1, max: 100, integer: true, maxLength: 3 }))}
              className={`mt-2 w-full ${inputClass}`}
            />
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
          <label className="flex items-center gap-3 rounded-xl p-4 bg-gray-50 dark:bg-[#070707] border border-gray-200 dark:border-zinc-800 text-sm text-gray-700 dark:text-zinc-300">
            <input type="checkbox" checked={riskSettings.allowBuy} onChange={(event) => update('allowBuy', event.target.checked)} /> Разрешать BUY
          </label>
          <label className="flex items-center gap-3 rounded-xl p-4 bg-gray-50 dark:bg-[#070707] border border-gray-200 dark:border-zinc-800 text-sm text-gray-700 dark:text-zinc-300">
            <input type="checkbox" checked={riskSettings.allowSell} onChange={(event) => update('allowSell', event.target.checked)} /> Разрешать SELL
          </label>
          <label className="flex items-center gap-3 rounded-xl p-4 bg-gray-50 dark:bg-[#070707] border border-gray-200 dark:border-zinc-800 text-sm text-gray-700 dark:text-zinc-300">
            <input type="checkbox" checked={riskSettings.allowAutoSell} onChange={(event) => update('allowAutoSell', event.target.checked)} /> Разрешать автопродажу
          </label>
        </div>
      </div>

      <div className="rounded-3xl border border-gray-200 dark:border-zinc-800 bg-white dark:bg-[#111111] p-6 shadow-lg">
        <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Предупреждения</h3>
        <div className="space-y-3">
          {riskWarnings.map((warning, index) => (
            <div key={index} className="rounded-xl p-4 bg-yellow-50 text-yellow-800 border border-yellow-200 dark:bg-yellow-900/20 dark:text-yellow-200 dark:border-yellow-800 text-sm">
              {warning}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
