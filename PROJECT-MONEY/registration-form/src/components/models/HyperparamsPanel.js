import React from 'react';
import { sanitizeNumberInput } from '../../utils/numberInput';
import { ButtonLoader } from '../common/LoadingSpinner';

export default function HyperparamsPanel({
  isDark,
  activeTab,
  modelConfigs,
  hyperparamMode,
  modelParams,
  updateParam,
  statusMessage,
  runForecast,
  trainModel,
  forecastLoading,
  loading,
}) {
  const config = modelConfigs[activeTab];

  return (
    <div className="bg-white dark:bg-[#111111] rounded-3xl shadow-lg border border-gray-200 dark:border-zinc-800 p-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-800 dark:text-white mb-2">
          2. {config.name}
        </h2>
        <p className="text-sm text-gray-500 dark:text-zinc-500">{config.description}</p>
        <div className="mt-3 inline-block px-3 py-1 rounded-lg text-xs font-mono bg-gray-100 dark:bg-[#070707] text-gray-600 dark:text-zinc-300">
          Kernel: {config.kernel}
        </div>
      </div>

      {hyperparamMode === 'manual' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {config.parameters.map((param) => (
            <div key={param.name} className="group">
              <label className="block text-sm font-medium text-gray-700 dark:text-zinc-300 mb-2 group-hover:text-yellow-400 transition-colors">
                {param.label || param.name}
              </label>
              {param.type === 'select' ? (
                <select
                  value={modelParams[activeTab][param.name]}
                  onChange={(event) => updateParam(activeTab, param.name, event.target.value)}
                  className={`w-full rounded-xl px-4 py-3 outline-none transition-all duration-300 border ${
                    isDark ? 'bg-gray-900 border-gray-700 text-white focus:border-yellow-400' : 'bg-gray-50 border-gray-200 focus:border-blue-500'
                  }`}
                >
                  {param.options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                </select>
              ) : (
                <div className="relative">
                  <input
                    type="number"
                    value={modelParams[activeTab][param.name]}
                    min={param.min}
                    max={param.max}
                    step={param.step}
                    onChange={(event) => updateParam(
                      activeTab,
                      param.name,
                      sanitizeNumberInput(event.target.value, {
                        min: param.min,
                        max: param.max,
                        integer: param.step >= 1,
                        maxLength: 12,
                      })
                    )}
                    className={`w-full rounded-xl px-4 py-3 outline-none transition-all duration-300 border ${
                      isDark ? 'bg-gray-900 border-gray-700 text-white focus:border-yellow-400' : 'bg-gray-50 border-gray-200 focus:border-blue-500'
                    }`}
                  />
                  <div className="absolute right-3 top-3 text-xs text-gray-400 pointer-events-none">
                    {param.step < 1 ? 'float' : 'int'}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className={`p-4 rounded-xl text-sm border ${
          isDark ? 'bg-yellow-400/10 border-yellow-500/20 text-yellow-200' : 'bg-blue-50 border-blue-100 text-blue-700'
        }`}>
          Система сама подберёт базовые гиперпараметры на проверочном участке. Для adaptive-модели она сравнит SVR/GPR и при близком качестве возьмёт ансамбль.
        </div>
      )}

      {activeTab === 'adaptive' && hyperparamMode === 'manual' && (
        <div className={`mt-6 p-4 rounded-xl text-sm border ${
          isDark ? 'bg-yellow-400/10 border-yellow-500/20 text-yellow-200' : 'bg-blue-50 border-blue-100 text-blue-700'
        }`}>
          Адаптивная модель использует параметры SVR и GPR как под-настройки. Если нужен полный ручной контроль, настрой эти вкладки перед прогнозом.
        </div>
      )}

      {statusMessage && (
        <div className={`mt-6 p-4 rounded-xl flex items-center gap-3 animate-pulse-once ${
          statusMessage.toLowerCase().includes('ошибка') || statusMessage.toLowerCase().includes('не удалось')
            ? 'bg-red-50 text-red-700 border border-red-200 dark:bg-red-900/30 dark:border-red-800 dark:text-red-200'
            : 'bg-green-50 text-green-700 border border-green-200 dark:bg-green-900/30 dark:border-green-800 dark:text-green-200'
        }`}>
          {statusMessage}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
        <button
          type="button"
          onClick={runForecast}
          disabled={forecastLoading}
          className={`py-4 rounded-xl font-bold text-lg shadow-lg transform active:scale-95 transition-all duration-200 ${
            forecastLoading
              ? 'bg-gray-400 cursor-not-allowed text-white'
              : isDark
                ? 'bg-gradient-to-r from-yellow-400 to-yellow-500 hover:from-yellow-300 hover:to-yellow-400 text-black'
                : 'bg-gradient-to-r from-yellow-400 to-yellow-500 hover:from-yellow-300 hover:to-yellow-400 text-black'
          }`}
        >
          {forecastLoading ? <ButtonLoader label="Строим прогноз..." dark /> : 'Построить прогноз'}
        </button>
        <button
          type="button"
          onClick={trainModel}
          disabled={loading}
          className={`py-4 rounded-xl font-bold text-lg shadow-lg transform active:scale-95 transition-all duration-200 ${
            loading
              ? 'bg-gray-400 cursor-not-allowed text-white'
              : isDark
                ? 'bg-gray-700 hover:bg-gray-600 text-white'
                : 'bg-white hover:bg-gray-50 text-gray-800 border border-gray-200'
          }`}
        >
          {loading ? <ButtonLoader label="Обучаем..." /> : 'Только обучение'}
        </button>
      </div>
    </div>
  );
}
