import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { modelAPI, marketAPI, tradeAPI, botTradeAPI, getErrorMessage } from '../../services/api';
import {
  FALLBACK_MOEX_SHARES,
  getInstrumentDisplayName,
  getInstrumentTicker,
  normalizeInstrumentList,
} from '../../utils/instruments';
import { sanitizeNumberInput } from '../../utils/numberInput';
import InstrumentSelector from './InstrumentSelector';
import ForecastHorizonSelector from './ForecastHorizonSelector';
import ModelTypeSelector from './ModelTypeSelector';
import ForecastResultCard from './ForecastResultCard';
import BotTradeControls from './BotTradeControls';
import TradeRecommendationDialog from './TradeRecommendationDialog';
import ForecastPriceChart from './charts/ForecastPriceChart';
import ModelComparisonPanel from './panels/ModelComparisonPanel';
import ForecastHistoryPanel from './panels/ForecastHistoryPanel';
import ModelDataPanel from './panels/ModelDataPanel';
import RiskSettingsPanel from './panels/RiskSettingsPanel';
import { ButtonLoader } from '../common/LoadingSpinner';
import { getStoredAccountId, withStoredAccountId } from './accountScope';


const isProblemMessage = (message) => {
  const normalized = String(message || '').toLowerCase();
  return ['ошибка', 'не удалось', 'нельзя', 'закрыт', 'закрыта', 'проверьте', 'недостаточно', 'отключена', 'отключен', 'сначала', 'укажите', 'выберите'].some((marker) => normalized.includes(marker));
};

const createIdempotencyKey = (prefix) => {
  if (window.crypto?.randomUUID) {
    return `${prefix}:${window.crypto.randomUUID()}`;
  }
  return `${prefix}:${Date.now()}:${Math.random().toString(16).slice(2)}`;
};

const BULK_TERMINAL_STATUSES = ['completed', 'partial_completed', 'failed'];
const BULK_ACTIVE_STATUSES = ['queued', 'running', 'scheduled_sell', 'closing'];

const bulkStatusLabels = {
  queued: 'В очереди',
  running: 'Сканируем акции',
  scheduled_sell: 'Ожидаем продажу',
  closing: 'Продаём',
  completed: 'Завершено',
  partial_completed: 'Частично завершено',
  failed: 'Ошибка',
  scanning: 'Проверяем',
  skipped: 'Пропущено',
  bought: 'Куплено',
  closed: 'Продано',
};

const bulkReasonLabels = {
  scheduled_sell: 'Куплено, ждём продажу через 1 час',
  predicted_not_positive: 'Прогноз не показал рост',
  no_successful_model: 'Не удалось выбрать рабочую модель',
  insufficient_candles: 'Недостаточно свечей для прогноза',
  candle_load_unavailable: 'Свечи недоступны у брокера',
  invalid_instrument: 'Инструмент не подходит',
  no_current_price: 'Нет текущей цены',
  invalid_lot: 'Некорректный размер лота',
  trade_rejected: 'Сделка отклонена',
  trade_error: 'Ошибка сделки',
  unexpected_error: 'Неожиданная ошибка',
};

const bulkSteps = [
  { key: 'scan', label: 'Сканирование' },
  { key: 'buy', label: 'Покупки' },
  { key: 'wait', label: 'Ожидание 1 час' },
  { key: 'sell', label: 'Продажа' },
  { key: 'csv', label: 'CSV' },
];

const DEFAULT_INSTRUMENT = {
  figi: 'BBG004730N88',
  ticker: 'SBER',
  name: 'Сбер Банк',
  source: 'popular',
};

const advancedTabs = [
  { key: 'compare', label: 'Сравнение' },
  { key: 'bulk', label: 'Покупка 30' },
  { key: 'data', label: 'Данные' },
  { key: 'history', label: 'История' },
  { key: 'risk', label: 'Риск' },
];

const modelConfigs = {
  adaptive: {
    name: 'Adaptive',
    kernel: 'SVR/RBF + GPR/Matérn + ensemble',
    description: 'Автоматический выбор между SVR, GPR и ensemble по качеству на validation-срезе.',
    parameters: [
      { name: 'volatility_threshold', type: 'number', min: 0.1, max: 5.0, step: 0.1, label: 'Порог волатильности (σ)' },
      { name: 'lags', type: 'number', min: 2, max: 30, step: 1, label: 'Размер окна (лаги)' },
      { name: 'ensemble_enabled', type: 'checkbox', label: 'Разрешить ensemble при близком MAE' },
    ],
  },
  svr: {
    name: 'SVR',
    kernel: 'RBF',
    description: 'Регрессионная модель с RBF-ядром для устойчивых участков рынка.',
    parameters: [
      { name: 'C', type: 'number', min: 0.1, max: 100, step: 0.1, label: 'Регуляризация C' },
      { name: 'epsilon', type: 'number', min: 0.01, max: 1, step: 0.01, label: 'Epsilon' },
      { name: 'gamma', type: 'select', options: ['scale', 'auto'], label: 'Gamma' },
    ],
  },
  gpr: {
    name: 'GPR',
    kernel: 'Matérn',
    description: 'Вероятностная модель с ядром Матерна и оценкой неопределенности прогноза.',
    parameters: [
      { name: 'length_scale', type: 'number', min: 0.1, max: 10, step: 0.1, label: 'Length Scale' },
      { name: 'nu', type: 'number', min: 0.5, max: 2.5, step: 0.5, label: 'Nu' },
      { name: 'alpha', type: 'number', min: 0.0000000001, max: 0.001, step: 0.0000000001, label: 'Alpha' },
    ],
  },
};

const formatMoney = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
};

const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const formatCountdown = (value, now) => {
  if (!value) return '';
  const target = new Date(value).getTime();
  if (!Number.isFinite(target)) return '';
  const diff = target - now;
  if (diff <= 0) return 'продажа уже должна начаться';
  const minutes = Math.ceil(diff / 60000);
  if (minutes < 60) return `до продажи примерно ${minutes} мин`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return `до продажи примерно ${hours} ч ${rest} мин`;
};

const getBulkStepState = (batch, stepKey) => {
  const status = batch?.status;
  if (!batch) return 'idle';
  if (status === 'failed') return stepKey === 'csv' ? 'blocked' : 'done';
  if (status === 'completed' || status === 'partial_completed') return 'done';
  if (status === 'queued') return stepKey === 'scan' ? 'active' : 'idle';
  if (status === 'running') {
    if (stepKey === 'scan' || stepKey === 'buy') return 'active';
    return 'idle';
  }
  if (status === 'scheduled_sell') {
    if (['scan', 'buy'].includes(stepKey)) return 'done';
    if (stepKey === 'wait') return 'active';
    return 'idle';
  }
  if (status === 'closing') {
    if (['scan', 'buy', 'wait'].includes(stepKey)) return 'done';
    if (stepKey === 'sell') return 'active';
    return 'idle';
  }
  return 'idle';
};

const downloadBlob = (blob, filename) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};

const normalizeCandle = (candle) => ({
  ...candle,
  time: candle.time || candle.x || candle.ts,
  open: candle.open ?? candle.o,
  high: candle.high ?? candle.h,
  low: candle.low ?? candle.l,
  close: candle.close ?? candle.c,
  c: candle.c ?? candle.close,
  volume: candle.volume ?? candle.v,
  v: candle.v ?? candle.volume,
});

function ModelParametersPanel({
  activeModel,
  hyperparamMode,
  modelParams,
  updateParam,
  statusMessage,
  forecastLoading,
  compareLoading,
  runForecast,
  runCompare,
}) {
  const config = modelConfigs[activeModel];
  const inputClass = 'mt-2 w-full border border-yellow-400/12 bg-[#11100d] px-4 py-3 text-white outline-none hover:border-yellow-400/28 focus:border-yellow-400';

  return (
    <section className="border border-yellow-400/12 bg-[#12110e] p-4 shadow-[0_18px_45px_rgba(0,0,0,0.2)]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-black text-white">Запуск</h2>
          <p className="mt-1 text-sm text-zinc-500">{config.name} · {config.kernel}</p>
        </div>
        <div className="border border-yellow-400/12 bg-black/20 px-3 py-2 text-xs font-medium text-zinc-400">
          {hyperparamMode === 'manual' ? 'ручные параметры' : 'автонастройка'}
        </div>
      </div>

      {hyperparamMode === 'manual' ? (
        <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
          {config.parameters.map((param) => (
            <label key={param.name} className="text-sm font-medium text-zinc-300">
              {param.label || param.name}
              {param.type === 'select' ? (
                <select value={modelParams[activeModel][param.name]} onChange={(event) => updateParam(activeModel, param.name, event.target.value)} className={inputClass}>
                  {param.options.map(option => <option key={option} value={option}>{option}</option>)}
                </select>
              ) : param.type === 'checkbox' ? (
                <div className="mt-2 flex items-center gap-3 border border-yellow-400/12 bg-[#11100d] px-4 py-3">
                  <input
                    type="checkbox"
                    checked={Boolean(modelParams[activeModel][param.name])}
                    onChange={(event) => updateParam(activeModel, param.name, event.target.checked)}
                  />
                  <span className="text-zinc-300">Включено</span>
                </div>
              ) : (
                <input
                  type="number"
                  value={modelParams[activeModel][param.name]}
                  min={param.min}
                  max={param.max}
                  step={param.step}
                  onChange={(event) => updateParam(activeModel, param.name, sanitizeNumberInput(event.target.value, {
                    min: param.min,
                    max: param.max,
                    integer: param.step >= 1,
                    maxLength: 12,
                  }))}
                  className={inputClass}
                />
              )}
            </label>
          ))}
        </div>
      ) : (
        <div className="mb-4 border border-yellow-400/12 bg-black/20 p-3 text-sm leading-6 text-zinc-400">
          Режим Auto сам подбирает параметры модели. Это самый безопасный сценарий для обычного пользователя.
        </div>
      )}

      {statusMessage && (
        <div className={`mb-4 border p-3 text-sm ${
          isProblemMessage(statusMessage)
            ? 'border-red-500/25 bg-red-500/10 text-red-200'
            : 'border-green-500/25 bg-green-500/10 text-green-200'
        }`}>
          {statusMessage}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
        <button
          type="button"
          onClick={runForecast}
          disabled={forecastLoading}
          className="inline-flex items-center justify-center border border-yellow-300 bg-yellow-400 py-4 text-base font-black text-black shadow-[0_16px_35px_rgba(250,204,21,0.12)] hover:border-yellow-200 hover:bg-yellow-300 disabled:border-zinc-800 disabled:bg-zinc-800 disabled:text-zinc-500"
        >
          {forecastLoading ? <ButtonLoader label="Строим прогноз..." dark /> : 'Построить прогноз'}
        </button>
        <button
          type="button"
          onClick={runCompare}
          disabled={compareLoading}
          className="inline-flex items-center justify-center border border-yellow-400/16 bg-[#17140f] py-4 text-base font-bold text-white hover:border-yellow-400/35 hover:bg-[#211b10] disabled:opacity-60"
        >
          {compareLoading ? <ButtonLoader label="Сравниваем..." /> : 'Сравнить'}
        </button>
      </div>
    </section>
  );
}

function RandomBulkPanel({
  tradingMode,
  bulkBatch,
  bulkLoading,
  bulkMessage,
  bulkDisabledReason,
  startRandomBulk,
  refreshRandomBulk,
  loadLatestRandomBulk,
  downloadRandomBulkCsv,
  csvDownloading,
  isProblemMessage,
}) {
  const [now, setNow] = useState(Date.now());
  const batchId = bulkBatch?.batch_id || bulkBatch?.id;
  const terminal = BULK_TERMINAL_STATUSES.includes(bulkBatch?.status);
  const csvReady = Boolean(batchId && bulkBatch?.csv_download_url);
  const countdownText = formatCountdown(bulkBatch?.nearest_scheduled_sell_at, now);
  const pnl = Number(bulkBatch?.realized_pnl_total || 0);
  const notableItems = (bulkBatch?.items || [])
    .filter(item => ['bought', 'closed', 'failed', 'skipped'].includes(item.status))
    .slice(-12)
    .reverse();

  useEffect(() => {
    if (!bulkBatch || terminal) return undefined;
    const timer = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(timer);
  }, [bulkBatch, terminal]);

  return (
    <section className="border border-yellow-400/12 bg-[#10100d] p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-black text-white">Рандомная покупка 30 акций</h2>
          <div className="mt-1 text-xs text-zinc-500">Sandbox · 1 лот · прогноз на 1 час · продажа через 1 час</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={loadLatestRandomBulk}
            disabled={bulkLoading}
            className="inline-flex items-center justify-center border border-yellow-400/12 bg-[#17140f] px-3 py-2 text-sm font-bold text-white hover:border-yellow-400/35 disabled:opacity-60"
          >
            Последний batch
          </button>
          {batchId && (
            <button
              type="button"
              onClick={() => refreshRandomBulk(batchId)}
              disabled={bulkLoading}
              className="inline-flex items-center justify-center border border-yellow-400/12 bg-[#17140f] px-3 py-2 text-sm font-bold text-white hover:border-yellow-400/35 disabled:opacity-60"
            >
              {bulkLoading ? <ButtonLoader label="Обновляем..." /> : 'Обновить'}
            </button>
          )}
          {csvReady && (
            <button
              type="button"
              onClick={() => downloadRandomBulkCsv(batchId)}
              disabled={csvDownloading}
              className="inline-flex items-center justify-center border border-green-500/30 bg-green-500/12 px-3 py-2 text-sm font-bold text-green-100 hover:bg-green-500/20"
            >
              {csvDownloading ? <ButtonLoader label="Скачиваем..." /> : 'Скачать CSV'}
            </button>
          )}
          <button
            type="button"
            onClick={startRandomBulk}
            disabled={bulkLoading || Boolean(bulkDisabledReason)}
            className="inline-flex items-center justify-center border border-yellow-300 bg-yellow-400 px-3 py-2 text-sm font-black text-black hover:bg-yellow-300 disabled:border-zinc-800 disabled:bg-zinc-800 disabled:text-zinc-500"
          >
            {bulkLoading ? <ButtonLoader label="Запускаем..." dark /> : 'Запустить покупку 30'}
          </button>
        </div>
      </div>

      <div className="mb-3 grid grid-cols-1 gap-2 md:grid-cols-5">
        {bulkSteps.map((step) => {
          const state = getBulkStepState(bulkBatch, step.key);
          const className = state === 'done'
            ? 'border-green-500/30 bg-green-500/10 text-green-100'
            : state === 'active'
              ? 'border-yellow-300 bg-yellow-400/15 text-yellow-100'
              : state === 'blocked'
                ? 'border-red-500/30 bg-red-500/10 text-red-100'
                : 'border-yellow-400/12 bg-black/20 text-zinc-500';
          return (
            <div key={step.key} className={`border px-3 py-2 text-sm font-bold ${className}`}>
              {step.label}
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3 xl:grid-cols-6">
        <div className="border border-yellow-400/12 bg-black/20 p-2.5">
          <div className="text-xs text-zinc-500">Режим</div>
          <div className="font-bold text-white">{tradingMode.sandbox ? 'Sandbox' : 'Real'}</div>
        </div>
        <div className="border border-yellow-400/12 bg-black/20 p-2.5">
          <div className="text-xs text-zinc-500">Статус</div>
          <div className="font-bold text-white">{bulkBatch?.status_label || bulkStatusLabels[bulkBatch?.status] || 'Нет batch'}</div>
        </div>
        <div className="border border-yellow-400/12 bg-black/20 p-2.5">
          <div className="text-xs text-zinc-500">Проверено</div>
          <div className="font-bold text-white">{bulkBatch?.scanned_count || 0}/{bulkBatch?.candidate_count || 0}</div>
        </div>
        <div className="border border-yellow-400/12 bg-black/20 p-2.5">
          <div className="text-xs text-zinc-500">Куплено</div>
          <div className="font-bold text-white">{bulkBatch?.bought_count || 0}/{bulkBatch?.target_count || 30}</div>
        </div>
        <div className="border border-yellow-400/12 bg-black/20 p-2.5">
          <div className="text-xs text-zinc-500">Продано</div>
          <div className="font-bold text-white">{bulkBatch?.closed_count || 0}</div>
        </div>
        <div className="border border-yellow-400/12 bg-black/20 p-2.5">
          <div className="text-xs text-zinc-500">Пропущено / ошибки</div>
          <div className="font-bold text-white">{bulkBatch?.skipped_count || 0} / {bulkBatch?.failed_count || 0}</div>
        </div>
      </div>

      {batchId && (
        <div className="mt-3 grid grid-cols-1 gap-2 text-sm md:grid-cols-3">
          <div className="border border-yellow-400/12 bg-black/20 p-2.5">
            <div className="text-xs text-zinc-500">Следующее действие</div>
            <div className="font-medium text-white">{bulkBatch?.next_action_label || 'Запустите batch, чтобы начать.'}</div>
          </div>
          <div className="border border-yellow-400/12 bg-black/20 p-2.5">
            <div className="text-xs text-zinc-500">Ближайшая продажа</div>
            <div className="font-medium text-white">
              {bulkBatch?.nearest_scheduled_sell_at ? formatDateTime(bulkBatch.nearest_scheduled_sell_at) : '—'}
            </div>
            {countdownText && <div className="mt-1 text-xs text-yellow-200">{countdownText}</div>}
          </div>
          <div className="border border-yellow-400/12 bg-black/20 p-2.5">
            <div className="text-xs text-zinc-500">Итог после продаж</div>
            <div className={`font-mono font-bold ${pnl >= 0 ? 'text-green-300' : 'text-red-300'}`}>
              {bulkBatch?.closed_count ? `${formatMoney(pnl)} ₽ (${formatMoney(bulkBatch?.realized_pnl_percent_total)}%)` : 'Ждём закрытия'}
            </div>
          </div>
        </div>
      )}

      {(bulkDisabledReason || bulkMessage || bulkBatch?.error_message) && (
        <div className={`mt-3 border p-3 text-sm ${
          bulkDisabledReason || isProblemMessage(bulkMessage || bulkBatch?.error_message)
            ? 'border-red-500/25 bg-red-500/10 text-red-200'
            : 'border-green-500/25 bg-green-500/10 text-green-200'
        }`}>
          {bulkDisabledReason || bulkMessage || bulkBatch?.error_message}
        </div>
      )}

      {batchId && !terminal && (
        <div className="mt-3 border border-yellow-500/25 bg-yellow-500/10 p-3 text-sm text-yellow-100">
          Batch #{batchId} выполняется на сервере. Панель обновляется каждые 5 секунд; можно обновить страницу, batch не пропадёт.
        </div>
      )}

      {terminal && batchId && (
        <div className={`mt-3 border p-3 text-sm ${csvReady ? 'border-green-500/25 bg-green-500/10 text-green-100' : 'border-yellow-500/25 bg-yellow-500/10 text-yellow-100'}`}>
          {csvReady ? 'Batch завершён, CSV готов к скачиванию.' : 'Batch завершён, CSV ещё не найден. Нажмите «Обновить» через несколько секунд.'}
        </div>
      )}

      {notableItems.length > 0 && (
        <div className="mt-3 overflow-x-auto border border-yellow-400/12">
          <table className="w-full text-sm">
            <thead className="bg-black/30 text-zinc-400">
              <tr>
                <th className="px-3 py-2 text-left">Акция</th>
                <th className="px-3 py-2 text-left">Статус</th>
                <th className="px-3 py-2 text-left">Причина</th>
                <th className="px-3 py-2 text-right">Прогноз</th>
                <th className="px-3 py-2 text-right">Сумма</th>
                <th className="px-3 py-2 text-right">PnL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-yellow-400/10">
              {notableItems.map(item => (
                <tr key={item.id} className="text-zinc-200">
                  <td className="px-3 py-2">
                    <div className="font-bold">{item.ticker || item.figi}</div>
                    <div className="font-mono text-xs text-zinc-500">{item.figi}</div>
                  </td>
                  <td className="px-3 py-2">{item.status_label || bulkStatusLabels[item.status] || item.status}</td>
                  <td className="px-3 py-2 text-zinc-400">{item.reason_label || bulkReasonLabels[item.reason] || item.error_message || '—'}</td>
                  <td className={`px-3 py-2 text-right font-mono ${Number(item.price_delta_percent || 0) >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                    {formatMoney(item.price_delta_percent)}%
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{formatMoney(item.buy_amount)} ₽</td>
                  <td className={`px-3 py-2 text-right font-mono ${Number(item.realized_pnl || 0) >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                    {item.realized_pnl == null ? '—' : `${formatMoney(item.realized_pnl)} ₽`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function CompactContextCard({
  dataQuality,
  selectedInstrument,
  forecastHorizon,
  loading,
  onRefresh,
  portfolio,
  selectedPosition,
  tradingMode,
}) {
  const quality = dataQuality || {};
  const ready = quality.quality_status === 'ready_all' || quality.quality_status === 'ready_svr_only';

  return (
    <aside className="space-y-3">
      <div className="border border-yellow-400/12 bg-[#12110e] p-4 shadow-[0_18px_45px_rgba(0,0,0,0.2)]">
        <div className="text-xs font-bold uppercase tracking-[0.22em] text-yellow-400/70">Актив</div>
        <div className="mt-3 text-3xl font-black text-white">{selectedInstrument.ticker || selectedInstrument.figi}</div>
        <div className="mt-1 break-all font-mono text-xs text-zinc-500">{selectedInstrument.figi}</div>
        <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
          <div className="border border-yellow-400/12 bg-black/20 p-3">
            <div className="text-xs text-zinc-500">Режим</div>
            <div className="font-bold text-white">{tradingMode.sandbox ? 'Sandbox' : 'Real'}</div>
          </div>
          <div className="border border-yellow-400/12 bg-black/20 p-3">
            <div className="text-xs text-zinc-500">Горизонт</div>
            <div className="font-bold text-white">{forecastHorizon === '1d' ? '1 день' : '1 час'}</div>
          </div>
        </div>
      </div>

      <div className="border border-yellow-400/12 bg-[#12110e] p-4 shadow-[0_18px_45px_rgba(0,0,0,0.2)]">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="text-sm font-black text-white">Данные</h3>
          <button type="button" onClick={onRefresh} disabled={loading} className="inline-flex items-center justify-center border border-yellow-400/12 bg-[#17140f] px-3 py-2 text-xs text-white hover:border-yellow-400/35 disabled:opacity-60">
            {loading ? <ButtonLoader label="Обновляем..." /> : 'Обновить'}
          </button>
        </div>
        <div className={`border p-3 text-sm ${ready ? 'border-green-500/25 bg-green-500/10 text-green-200' : 'border-yellow-500/25 bg-yellow-500/10 text-yellow-100'}`}>
          <div className="font-bold">{quality.quality_message || 'Проверка не выполнена'}</div>
          <div className="mt-1 text-xs opacity-75">Свечей: {quality.candle_count ?? '—'}</div>
        </div>
      </div>

      <div className="border border-yellow-400/12 bg-[#12110e] p-4 shadow-[0_18px_45px_rgba(0,0,0,0.2)]">
        <h3 className="mb-3 text-sm font-black text-white">Портфель</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="border border-yellow-400/12 bg-black/20 p-3">
            <div className="text-xs text-zinc-500">Деньги</div>
            <div className="font-bold text-white">{formatMoney(portfolio.cash_balance)} ₽</div>
          </div>
          <div className="border border-yellow-400/12 bg-black/20 p-3">
            <div className="text-xs text-zinc-500">В позиции</div>
            <div className="font-bold text-white">{selectedPosition ? formatMoney(selectedPosition.quantity) : 'нет'}</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default function Models() {
  const { isDark } = useTheme();

  const [advancedTab, setAdvancedTab] = useState('compare');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [activeModel, setActiveModel] = useState('adaptive');
  const [candles, setCandles] = useState([]);
  const [loadingCandles, setLoadingCandles] = useState(false);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [compareLoading, setCompareLoading] = useState(false);
  const [dataQualityLoading, setDataQualityLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [tradeStatusMessage, setTradeStatusMessage] = useState('');

  const [portfolio, setPortfolio] = useState({ positions: [], cash_balance: 0 });
  const [shareOptions, setShareOptions] = useState(() => FALLBACK_MOEX_SHARES);
  const [userCandles, setUserCandles] = useState([]);
  const [selectedSource, setSelectedSource] = useState('popular');
  const [manualInstrument, setManualInstrument] = useState({ figi: '', ticker: '' });
  const [selectedInstrument, setSelectedInstrument] = useState(DEFAULT_INSTRUMENT);
  const [forecastHorizon, setForecastHorizon] = useState('1h');
  const [hyperparamMode, setHyperparamMode] = useState('auto');
  const [flatThresholdPercent, setFlatThresholdPercent] = useState(1);
  const [forecastResult, setForecastResult] = useState(null);
  const [compareResult, setCompareResult] = useState(null);
  const [dataQuality, setDataQuality] = useState(null);
  const [forecastHistory, setForecastHistory] = useState([]);
  const [historyFilters, setHistoryFilters] = useState({ figi: '', model_type: '', horizon: '' });
  const [tradingMode, setTradingMode] = useState({
    mode: 'unknown',
    sandbox: true,
    auto_sell_worker_enabled: false,
    auto_sell_poll_seconds: 60,
    auto_sell_dry_run: true,
    bulk_trade_worker_enabled: false,
    bulk_trade_worker_poll_seconds: 60,
    real_trading_enabled: false,
  });
  const [bulkBatch, setBulkBatch] = useState(null);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkMessage, setBulkMessage] = useState('');
  const [csvDownloading, setCsvDownloading] = useState(false);
  const [tradeLoading, setTradeLoading] = useState(false);
  const [tradeControls, setTradeControls] = useState({ visible: false, quantity: 1, buyNow: false, autoSell: false, reminderMinutes: null });
  const [riskSettings, setRiskSettings] = useState({
    largeTradeConfirmAmount: 5000,
    maxPositionSharePercent: 30,
    allowBuy: true,
    allowSell: true,
    allowAutoSell: true,
  });
  const [currentDataInfo, setCurrentDataInfo] = useState({ figi: DEFAULT_INSTRUMENT.figi, days: 1, symbol: DEFAULT_INSTRUMENT.ticker });

  const [modelParams, setModelParams] = useState({
    svr: { C: 1.0, epsilon: 0.1, gamma: 'scale' },
    gpr: { nu: 1.5, length_scale: 1.0, alpha: 1e-10 },
    adaptive: { volatility_threshold: 0.8, lags: 10, ensemble_enabled: true },
  });

  const activeLags = Number(modelParams.adaptive.lags) || 10;

  const loadPortfolio = useCallback(async () => {
    try {
      const accountId = getStoredAccountId();
      const response = await tradeAPI.getPortfolio(accountId || null);
      setPortfolio({
        positions: response.data.positions || [],
        cash_balance: response.data.cash_balance || 0,
      });
    } catch (error) {
      console.error('Ошибка загрузки портфеля:', error);
      setPortfolio({ positions: [], cash_balance: 0 });
    }
  }, []);

  const loadShareOptions = useCallback(async () => {
    try {
      const response = await marketAPI.getShares(1000);
      const loadedShares = normalizeInstrumentList(response?.data?.items || []);
      setShareOptions(loadedShares.length > 0 ? loadedShares : FALLBACK_MOEX_SHARES);
    } catch (error) {
      console.error('Ошибка загрузки списка акций:', error);
      setShareOptions(prev => prev.length > 0 ? prev : FALLBACK_MOEX_SHARES);
    }
  }, []);

  const loadTradingMode = useCallback(async () => {
    try {
      const response = await marketAPI.getTradingMode();
      setTradingMode(response.data || { mode: 'unknown', sandbox: true });
    } catch (error) {
      console.error('Ошибка загрузки режима торговли:', error);
      setTradingMode({
        mode: 'unknown',
        sandbox: true,
        auto_sell_worker_enabled: false,
        auto_sell_poll_seconds: 60,
        auto_sell_dry_run: true,
        bulk_trade_worker_enabled: false,
        bulk_trade_worker_poll_seconds: 60,
        real_trading_enabled: false,
      });
    }
  }, []);

  const loadUserCandles = useCallback(async () => {
    try {
      const response = await marketAPI.getUserCandles();
      setUserCandles(response.data.candles_by_figi || []);
    } catch (error) {
      console.error('Ошибка загрузки списка FIGI:', error);
    }
  }, []);

  const refreshDataQuality = useCallback(async (figi = selectedInstrument.figi) => {
    if (!figi) return null;
    try {
      setDataQualityLoading(true);
      const response = await modelAPI.getDataQuality({ figi, horizon: forecastHorizon, lags: activeLags });
      setDataQuality(response.data);
      return response.data;
    } catch (error) {
      console.error('Ошибка проверки качества данных:', error);
      setDataQuality(null);
      return null;
    } finally {
      setDataQualityLoading(false);
    }
  }, [activeLags, forecastHorizon, selectedInstrument.figi]);

  const loadCandles = useCallback(async (figi = currentDataInfo.figi, days = currentDataInfo.days) => {
    if (!figi) return [];
    try {
      setLoadingCandles(true);
      setStatusMessage('Загрузка свечей...');
      const response = await marketAPI.loadCandles(figi, days);
      const loaded = (response.data.candles || []).map(normalizeCandle);
      setCandles(loaded);
      setCurrentDataInfo(prev => ({ ...prev, figi, days }));
      setStatusMessage(`Загружено свечей: ${loaded.length}`);
      await loadUserCandles();
      await refreshDataQuality(figi);
      return loaded;
    } catch (error) {
      console.error('Ошибка загрузки свечей:', error);
      setStatusMessage(getErrorMessage(error, 'Не удалось загрузить свечи. Проверьте инструмент или повторите позже.'));
      return [];
    } finally {
      setLoadingCandles(false);
    }
  }, [currentDataInfo.days, currentDataInfo.figi, loadUserCandles, refreshDataQuality]);

  const loadForecastHistory = useCallback(async (filters = historyFilters) => {
    try {
      setHistoryLoading(true);
      const params = { limit: 40 };
      if (filters.figi?.trim()) params.figi = filters.figi.trim().toUpperCase();
      if (filters.model_type) params.model_type = filters.model_type;
      if (filters.horizon) params.horizon = filters.horizon;
      const response = await modelAPI.getForecasts(params);
      setForecastHistory(response.data.items || []);
    } catch (error) {
      console.error('Ошибка загрузки истории прогнозов:', error);
      setForecastHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [historyFilters]);

  const loadLatestRandomBulk = useCallback(async (options = {}) => {
    const silent = Boolean(options.silent);
    try {
      if (!silent) setBulkLoading(true);
      const response = await botTradeAPI.getLatestRandomBulk();
      setBulkBatch(response.data);
      if (!silent) setBulkMessage('Последний batch загружен.');
      return response.data;
    } catch (error) {
      if (error?.response?.status === 404) {
        if (!silent) setBulkMessage('Пока нет batch-запусков.');
        return null;
      }
      if (error?.response?.status === 401) {
        setBulkMessage('Сессия истекла. Войдите снова, batch продолжает выполняться на сервере.');
        return null;
      }
      console.error('Random bulk latest error:', error);
      if (!silent) {
        setBulkMessage(getErrorMessage(error, 'Не удалось загрузить последний batch.'));
      }
      return null;
    } finally {
      if (!silent) setBulkLoading(false);
    }
  }, []);

  const refreshRandomBulk = useCallback(async (batchId, options = {}) => {
    if (!batchId) return null;
    const silent = Boolean(options.silent);
    try {
      if (!silent) setBulkLoading(true);
      const response = await botTradeAPI.getRandomBulk(batchId);
      const nextBatch = response.data;
      setBulkBatch(nextBatch);
      if (BULK_TERMINAL_STATUSES.includes(nextBatch?.status)) {
        setBulkMessage(nextBatch?.csv_download_url ? 'Batch завершён. CSV готов.' : 'Batch завершён. CSV ещё готовится.');
        await loadPortfolio();
      }
      return nextBatch;
    } catch (error) {
      console.error('Random bulk status error:', error);
      if (error?.response?.status === 401) {
        setBulkMessage('Сессия истекла. Войдите снова, batch продолжает выполняться на сервере.');
        return null;
      }
      if (!silent) {
        setBulkMessage(getErrorMessage(error, 'Не удалось обновить статус batch.'));
      }
      return null;
    } finally {
      if (!silent) setBulkLoading(false);
    }
  }, [loadPortfolio]);

  const startRandomBulk = useCallback(async () => {
    try {
      setBulkLoading(true);
      setBulkMessage('');
      const accountId = getStoredAccountId();
      const payload = { target_count: 30 };
      if (accountId) payload.account_id = accountId;
      const response = await botTradeAPI.startRandomBulk(payload);
      setBulkBatch(response.data);
      setBulkMessage('Batch запущен: сканируем акции и покупаем только положительные прогнозы.');
    } catch (error) {
      console.error('Random bulk start error:', error);
      setBulkMessage(getErrorMessage(error, 'Не удалось запустить рандомную покупку 30 акций.'));
    } finally {
      setBulkLoading(false);
    }
  }, []);

  const downloadRandomBulkCsv = useCallback(async (batchId) => {
    if (!batchId) return;
    try {
      setCsvDownloading(true);
      const response = await botTradeAPI.downloadRandomBulkCsv(batchId);
      downloadBlob(response.data, `random_bulk_batch_${batchId}.csv`);
      setBulkMessage('CSV скачан.');
    } catch (error) {
      console.error('Random bulk csv download error:', error);
      if (error?.response?.status === 401) {
        setBulkMessage('Сессия истекла. Войдите снова, batch продолжает выполняться на сервере.');
      } else if (error?.response?.status === 409 || error?.response?.status === 404) {
        setBulkMessage('CSV ещё не готов. Нажмите «Обновить» через несколько секунд.');
      } else {
        setBulkMessage(getErrorMessage(error, 'Не удалось скачать CSV.'));
      }
    } finally {
      setCsvDownloading(false);
    }
  }, []);

  useEffect(() => {
    loadCandles(DEFAULT_INSTRUMENT.figi, 1);
    loadPortfolio();
    loadShareOptions();
    loadTradingMode();
    loadUserCandles();
    loadForecastHistory({ figi: '', model_type: '', horizon: '' });
    loadLatestRandomBulk({ silent: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    refreshDataQuality(selectedInstrument.figi);
  }, [forecastHorizon, activeLags, selectedInstrument.figi, refreshDataQuality]);

  useEffect(() => {
    const batchId = bulkBatch?.batch_id || bulkBatch?.id;
    if (!batchId || !BULK_ACTIVE_STATUSES.includes(bulkBatch?.status)) return undefined;
    const timer = window.setInterval(() => {
      refreshRandomBulk(batchId, { silent: true });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [bulkBatch?.batch_id, bulkBatch?.id, bulkBatch?.status, refreshRandomBulk]);

  const selectInstrument = (instrument, source = selectedSource) => {
    const figi = (instrument.figi || '').trim().toUpperCase();
    if (!figi) {
      setStatusMessage('Укажите FIGI');
      return;
    }

    const nextInstrument = {
      figi,
      ticker: instrument.ticker || instrument.name || '',
      name: instrument.name || instrument.ticker || figi,
      source,
    };

    setSelectedInstrument(nextInstrument);
    setTradeStatusMessage('');
    setCurrentDataInfo(prev => ({ ...prev, figi, symbol: nextInstrument.ticker || figi }));
    setForecastResult(null);
    setCompareResult(null);
    setHistoryFilters(prev => ({ ...prev, figi }));
    loadCandles(figi, currentDataInfo.days || 1);
  };

  const deleteUserCandles = async (figi) => {
    try {
      await marketAPI.deleteUserCandles(figi);
      setStatusMessage(`Удалены свечи для ${figi}`);
      await loadUserCandles();
      if (figi === currentDataInfo.figi) setCandles([]);
      await refreshDataQuality(figi);
    } catch (error) {
      console.error('Ошибка удаления свечей:', error);
      setStatusMessage(getErrorMessage(error, 'Не удалось удалить свечи. Повторите попытку позже.'));
    }
  };

  const buildForecastPayload = (modelType = activeModel) => {
    return withStoredAccountId({
      figi: selectedInstrument.figi,
      ticker: selectedInstrument.ticker || null,
      horizon: forecastHorizon,
      model_type: modelType,
      hyperparam_mode: hyperparamMode,
      flat_threshold_percent: Number(flatThresholdPercent) || 1,
      days: forecastHorizon === '1d' ? 7 : 3,
      lags: activeLags,
      svr_params: hyperparamMode === 'manual' ? modelParams.svr : null,
      gpr_params: hyperparamMode === 'manual' ? modelParams.gpr : null,
      adaptive_params: hyperparamMode === 'manual' ? modelParams.adaptive : { ensemble_enabled: true },
      source: selectedInstrument.source || selectedSource,
    });
  };

  const initTradeControls = (forecast) => {
    const recommendation = forecast?.recommendation || {};
    const action = recommendation.action;
    const recommendedQuantity = Number(recommendation.recommended_quantity || recommendation.quantity || 1);

    if (action === 'SELL') {
      setTradeControls({ visible: true, quantity: Math.max(1, Math.floor(recommendedQuantity)), buyNow: false, autoSell: false, reminderMinutes: null, largeTradeConfirmed: false });
      return;
    }
    if (action === 'BUY_OPTIONAL') {
      setTradeControls({ visible: true, quantity: Math.max(1, Math.floor(recommendedQuantity || 1)), buyNow: true, autoSell: false, reminderMinutes: null, largeTradeConfirmed: false });
      return;
    }
    if (action === 'HOLD_AND_OPTIONAL_BUY') {
      setTradeControls({ visible: true, quantity: Math.max(1, Math.floor(recommendedQuantity || 1)), buyNow: false, autoSell: false, reminderMinutes: null, largeTradeConfirmed: false });
      return;
    }
    setTradeControls({ visible: false, quantity: 1, buyNow: false, autoSell: false, reminderMinutes: null, largeTradeConfirmed: false });
  };

  const runForecast = async () => {
    if (!selectedInstrument.figi) {
      setStatusMessage('Выберите инструмент');
      return;
    }

    try {
      setForecastLoading(true);
      setForecastResult(null);
      setTradeStatusMessage('');
      setStatusMessage('Строю ML-прогноз...');
      const response = await modelAPI.forecast(buildForecastPayload(activeModel));
      setForecastResult(response.data);
      initTradeControls(response.data);
      setStatusMessage('Прогноз построен и сохранен в истории');
      await loadForecastHistory({ ...historyFilters, figi: selectedInstrument.figi });
      await refreshDataQuality(selectedInstrument.figi);
    } catch (error) {
      console.error('Ошибка прогноза:', error);
      setStatusMessage(getErrorMessage(error, 'Не удалось построить прогноз. Проверьте данные инструмента и повторите попытку.'));
    } finally {
      setForecastLoading(false);
    }
  };

  const runCompare = async () => {
    if (!selectedInstrument.figi) {
      setStatusMessage('Выберите инструмент');
      return;
    }

    try {
      setAdvancedOpen(true);
      setAdvancedTab('compare');
      setCompareLoading(true);
      setStatusMessage('Сравниваю SVR, GPR и adaptive...');
      const response = await modelAPI.compare(buildForecastPayload(activeModel));
      setCompareResult(response.data);
      setStatusMessage('Сравнение моделей готово');
      await loadForecastHistory({ ...historyFilters, figi: selectedInstrument.figi });
    } catch (error) {
      console.error('Ошибка сравнения моделей:', error);
      setStatusMessage(getErrorMessage(error, 'Не удалось сравнить модели. Повторите попытку позже.'));
    } finally {
      setCompareLoading(false);
    }
  };

  const updateParam = (modelType, paramName, value) => {
    if (typeof value === 'boolean') {
      setModelParams(prev => ({ ...prev, [modelType]: { ...prev[modelType], [paramName]: value } }));
      return;
    }
    const paramConfig = modelConfigs[modelType]?.parameters?.find(param => param.name === paramName);
    const fallback = modelParams[modelType][paramName];
    const numericValue = value === '' ? fallback : parseFloat(value);
    setModelParams(prev => ({
      ...prev,
      [modelType]: {
        ...prev[modelType],
        [paramName]: paramName === 'gamma'
          ? value
          : Math.min(paramConfig?.max ?? Number.MAX_SAFE_INTEGER, Math.max(paramConfig?.min ?? 0, numericValue)),
      },
    }));
  };

  const setReminder = (minutes) => {
    setTradeControls(prev => ({ ...prev, reminderMinutes: minutes }));
    setTradeStatusMessage(`Локальное напоминание: повторить прогноз через ${minutes} мин.`);
  };

  const getScheduledSellAt = () => {
    const now = new Date();
    if (forecastResult?.horizon === '1d') now.setDate(now.getDate() + 1);
    else now.setHours(now.getHours() + 1);
    return now.toISOString();
  };

  const confirmBotTrade = async (side) => {
    if (!forecastResult?.forecast_id) {
      setTradeStatusMessage('Сначала постройте прогноз, потом подтверждайте сделку.');
      return;
    }

    const quantity = Math.max(1, Math.floor(Number(tradeControls.quantity) || 1));
    const effectiveSide = side || forecastResult.recommendation?.recommended_side;
    const amount = Number(forecastResult.current_price || 0) * quantity;

    if (effectiveSide === 'buy' && !riskSettings.allowBuy) {
      setTradeStatusMessage('Покупка отключена в настройках риска.');
      return;
    }
    if (effectiveSide === 'sell' && !riskSettings.allowSell) {
      setTradeStatusMessage('Продажа отключена в настройках риска.');
      return;
    }
    if (effectiveSide === 'schedule_sell' && !riskSettings.allowAutoSell) {
      setTradeStatusMessage('Автопродажа отключена в настройках риска.');
      return;
    }
    const largeTradeConfirmAmount = Number(riskSettings.largeTradeConfirmAmount || 0);
    if (effectiveSide === 'buy' && largeTradeConfirmAmount > 0 && amount > largeTradeConfirmAmount && !tradeControls.largeTradeConfirmed) {
      setTradeStatusMessage('Подтвердите покупку вручную.');
      return;
    }

    try {
      setTradeLoading(true);
      const accountId = getStoredAccountId();
      const payload = {
        forecast_id: forecastResult.forecast_id,
        side: effectiveSide,
        action: forecastResult.recommendation?.action,
        quantity: effectiveSide === 'schedule_sell'
          ? Math.max(1, Math.floor(Number(forecastResult.recommendation?.quantity) || quantity))
          : quantity,
        auto_sell_enabled: Boolean(tradeControls.autoSell),
        scheduled_sell_at: tradeControls.autoSell ? getScheduledSellAt() : null,
        sell_target_price: tradeControls.autoSell ? forecastResult.predicted_price : null,
        idempotency_key: createIdempotencyKey('bot-trade'),
      };
      if (accountId) payload.account_id = accountId;

      await botTradeAPI.confirmAction(payload);
      setTradeStatusMessage(effectiveSide === 'schedule_sell'
        ? 'Автопродажа запланирована'
        : `Сделка подтверждена (${tradingMode.sandbox ? 'песочница' : 'реальный режим'})`
      );
      setTradeControls(prev => ({ ...prev, visible: false }));
      await loadPortfolio();
      await loadForecastHistory({ ...historyFilters, figi: selectedInstrument.figi });
    } catch (error) {
      console.error('Ошибка подтверждения bot trade:', error);
      setTradeStatusMessage(getErrorMessage(error, 'Сделка не выполнена. Проверьте баланс, инструмент и режим торговли.'));
    } finally {
      setTradeLoading(false);
    }
  };

  const instrumentOptions = useMemo(() => (
    selectedSource === 'portfolio'
      ? portfolio.positions.map(item => ({
          figi: item.figi,
          ticker: getInstrumentTicker(item),
          name: getInstrumentDisplayName(item),
          quantity: item.quantity,
          price: item.price,
          average_price: item.average_price,
        }))
      : shareOptions
  ), [portfolio.positions, shareOptions, selectedSource]);

  const selectedPosition = portfolio.positions.find(item => item.figi === selectedInstrument.figi);
  const bulkDisabledReason = useMemo(() => {
    if (!tradingMode.sandbox) return 'Рандомная покупка доступна только в sandbox-режиме.';
    if (!tradingMode.bulk_trade_worker_enabled) return 'Bulk worker выключен на backend. Включите BULK_TRADE_WORKER_ENABLED=true.';
    if (tradingMode.auto_sell_dry_run) return 'AUTO_SELL_DRY_RUN включён. Для запуска нужна реальная sandbox-автопродажа: AUTO_SELL_DRY_RUN=false.';
    return '';
  }, [tradingMode]);

  return (
    <div className="ml-models-page animate-fade-in space-y-5 text-white">
      <section className="border border-yellow-400/12 bg-[#0f0e0b] p-5 shadow-[0_18px_45px_rgba(0,0,0,0.24)]">
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            <InstrumentSelector
              isDark={isDark}
              selectedSource={selectedSource}
              setSelectedSource={setSelectedSource}
              selectedInstrument={selectedInstrument}
              manualInstrument={manualInstrument}
              setManualInstrument={setManualInstrument}
              instrumentOptions={instrumentOptions}
              selectInstrument={selectInstrument}
            />
            <ForecastHorizonSelector
              isDark={isDark}
              forecastHorizon={forecastHorizon}
              setForecastHorizon={setForecastHorizon}
              hyperparamMode={hyperparamMode}
              setHyperparamMode={setHyperparamMode}
              flatThresholdPercent={flatThresholdPercent}
              setFlatThresholdPercent={setFlatThresholdPercent}
            />
            <ModelTypeSelector
              isDark={isDark}
              activeTab={activeModel}
              setActiveTab={setActiveModel}
              modelConfigs={modelConfigs}
            />
            <ModelParametersPanel
              activeModel={activeModel}
              hyperparamMode={hyperparamMode}
              modelParams={modelParams}
              updateParam={updateParam}
              statusMessage={statusMessage}
              forecastLoading={forecastLoading}
              compareLoading={compareLoading}
              runForecast={runForecast}
              runCompare={runCompare}
            />
          </div>

          <CompactContextCard
            dataQuality={dataQuality}
            selectedInstrument={selectedInstrument}
            forecastHorizon={forecastHorizon}
            loading={dataQualityLoading || loadingCandles}
            onRefresh={() => refreshDataQuality(selectedInstrument.figi)}
            portfolio={portfolio}
            selectedPosition={selectedPosition}
            tradingMode={tradingMode}
          />
        </div>
      </section>

      <section className="border border-yellow-400/12 bg-[#12110e] p-5 shadow-[0_18px_45px_rgba(0,0,0,0.24)]">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-black text-white">Результат и рекомендация</h2>
          {forecastResult && (
            <div className="text-xs font-medium text-zinc-500">готово</div>
          )}
        </div>

        <ForecastPriceChart candles={candles} forecastResult={forecastResult} isDark={isDark} />

        {forecastResult ? (
          <div className="mt-5 border border-yellow-400/12 bg-black/20 p-4">
            <ForecastResultCard forecastResult={forecastResult} isDark={isDark} formatMoney={formatMoney} />
            <BotTradeControls forecastResult={forecastResult} setReminder={setReminder} />
            {tradeStatusMessage && !tradeControls.visible && (
              <div className={`mt-5 border p-3 text-sm ${
                isProblemMessage(tradeStatusMessage)
                  ? 'border-red-500/25 bg-red-500/10 text-red-200'
                  : 'border-green-500/25 bg-green-500/10 text-green-200'
              }`}>
                {tradeStatusMessage}
              </div>
            )}
            <TradeRecommendationDialog
              forecastResult={forecastResult}
              tradeControls={tradeControls}
              setTradeControls={setTradeControls}
              tradeLoading={tradeLoading}
              confirmBotTrade={confirmBotTrade}
              formatMoney={formatMoney}
              isDark={isDark}
              riskSettings={riskSettings}
              tradeStatusMessage={tradeStatusMessage}
              isProblemMessage={isProblemMessage}
            />
          </div>
        ) : (
          <div className="mt-5 border border-dashed border-yellow-400/16 bg-black/20 p-8 text-center text-zinc-500">
            Здесь появится прогноз цены, объяснение модели и торговое решение.
          </div>
        )}
      </section>

      <section className="border border-yellow-400/12 bg-[#12110e] shadow-[0_18px_45px_rgba(0,0,0,0.2)]">
        <button
          type="button"
          onClick={() => setAdvancedOpen((value) => !value)}
          className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-sm font-bold text-white hover:bg-[#17140f]"
        >
          <span>Дополнительно</span>
          <span className="text-zinc-500">{advancedOpen ? 'Скрыть' : 'Показать'}</span>
        </button>

        {advancedOpen && (
          <div className="border-t border-yellow-400/10 p-4">
            <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-5">
              {advancedTabs.map(tab => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setAdvancedTab(tab.key)}
                  className={`border px-4 py-3 text-sm font-bold transition ${
                    advancedTab === tab.key
                      ? 'border-yellow-300 bg-yellow-400 text-black shadow'
                      : 'border-yellow-400/12 text-zinc-400 hover:border-yellow-400/35 hover:bg-[#1d190f] hover:text-white'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {advancedTab === 'compare' && (
              <ModelComparisonPanel
                compareResult={compareResult}
                compareLoading={compareLoading}
                onCompare={runCompare}
                isDark={isDark}
              />
            )}

            {advancedTab === 'bulk' && (
              <RandomBulkPanel
                tradingMode={tradingMode}
                bulkBatch={bulkBatch}
                bulkLoading={bulkLoading}
                bulkMessage={bulkMessage}
                bulkDisabledReason={bulkDisabledReason}
                startRandomBulk={startRandomBulk}
                refreshRandomBulk={refreshRandomBulk}
                loadLatestRandomBulk={loadLatestRandomBulk}
                downloadRandomBulkCsv={downloadRandomBulkCsv}
                csvDownloading={csvDownloading}
                isProblemMessage={isProblemMessage}
              />
            )}

            {advancedTab === 'data' && (
              <ModelDataPanel
                dataQuality={dataQuality}
                selectedInstrument={selectedInstrument}
                forecastHorizon={forecastHorizon}
                dataQualityLoading={dataQualityLoading}
                loadingCandles={loadingCandles}
                refreshDataQuality={() => refreshDataQuality(selectedInstrument.figi)}
                candles={candles}
                currentDataInfo={currentDataInfo}
                loadCandles={loadCandles}
                userCandles={userCandles}
                loadUserCandles={loadUserCandles}
                deleteUserCandles={deleteUserCandles}
                selectInstrument={selectInstrument}
              />
            )}

            {advancedTab === 'history' && (
              <ForecastHistoryPanel
                history={forecastHistory}
                loading={historyLoading}
                onRefresh={() => loadForecastHistory(historyFilters)}
                filters={historyFilters}
                setFilters={setHistoryFilters}
              />
            )}

            {advancedTab === 'risk' && (
              <RiskSettingsPanel
                flatThresholdPercent={flatThresholdPercent}
                setFlatThresholdPercent={setFlatThresholdPercent}
                riskSettings={riskSettings}
                setRiskSettings={setRiskSettings}
                forecastResult={forecastResult}
              />
            )}
          </div>
        )}
      </section>
    </div>
  );
}
