import React from 'react';
import { sanitizeNumberInput } from '../../utils/numberInput';

export default function ForecastHorizonSelector({
  forecastHorizon,
  setForecastHorizon,
  hyperparamMode,
  setHyperparamMode,
  flatThresholdPercent,
  setFlatThresholdPercent,
}) {
  const fieldClass = 'mt-2 w-full border border-yellow-400/12 bg-[#11100d] px-4 py-3 text-white outline-none hover:border-yellow-400/28 focus:border-yellow-400';

  return (
    <section className="border border-yellow-400/12 bg-[#12110e] p-4 shadow-[0_18px_45px_rgba(0,0,0,0.2)]">
      <h2 className="mb-4 text-base font-black text-white">Прогноз</h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <label className="block text-sm font-medium text-zinc-300">
          Горизонт
          <select id="forecast-horizon" value={forecastHorizon} onChange={(event) => setForecastHorizon(event.target.value)} className={fieldClass}>
            <option value="1h">Ближайший час</option>
            <option value="1d">Ближайший день</option>
          </select>
        </label>

        <label className="block text-sm font-medium text-zinc-300">
          Настройка
          <select id="hyperparam-mode" value={hyperparamMode} onChange={(event) => setHyperparamMode(event.target.value)} className={fieldClass}>
            <option value="auto">Авто</option>
            <option value="manual">Вручную</option>
          </select>
        </label>

        <label className="block text-sm font-medium text-zinc-300">
          Flat, %
          <input
            id="flat-threshold-percent"
            type="number"
            min="0.1"
            max="10"
            step="0.1"
            value={flatThresholdPercent}
            onChange={(event) => setFlatThresholdPercent(sanitizeNumberInput(event.target.value, { min: 0.1, max: 10, integer: false, maxLength: 5 }))}
            className={fieldClass}
          />
        </label>
      </div>
    </section>
  );
}
