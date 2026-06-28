import React from 'react';

const actionLabels = {
  SELL: 'Продать',
  HOLD: 'Держать',
  HOLD_AND_OPTIONAL_BUY: 'Держать / можно докупить',
  BUY_OPTIONAL: 'Можно купить',
  WAIT: 'Ждать',
  DO_NOT_BUY: 'Не покупать',
};

const reasonLabels = {
  flat_existing_position: 'Цена почти не изменилась, позиция уже есть',
  flat_no_position: 'Сильного сигнала нет',
  forecast_growth: 'Прогноз показывает рост',
  forecast_drop: 'Прогноз показывает снижение',
  sell_drop_existing_position: 'Есть позиция, модель ждёт снижение',
  buy_growth_no_position: 'Позиции нет, модель ждёт рост',
  no_cash: 'Недостаточно денег для покупки',
  no_position: 'Нет бумаг для продажи',
};

const formatSignedPercent = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`;
};

const getTone = (action, delta) => {
  if (action === 'SELL' || action === 'DO_NOT_BUY') {
    return {
      card: 'border-red-400/22 bg-red-500/10',
      badge: 'border-red-400/25 bg-red-500/10 text-red-200',
      value: 'text-red-300',
    };
  }
  if (action === 'BUY_OPTIONAL' || action === 'HOLD_AND_OPTIONAL_BUY' || Number(delta) > 0) {
    return {
      card: 'border-emerald-400/22 bg-emerald-500/10',
      badge: 'border-emerald-400/25 bg-emerald-500/10 text-emerald-200',
      value: 'text-emerald-300',
    };
  }
  return {
    card: 'border-yellow-400/16 bg-[#17140f]',
    badge: 'border-yellow-400/20 bg-yellow-400/10 text-yellow-200',
    value: 'text-yellow-300',
  };
};

export default function ForecastResultCard({ forecastResult, formatMoney }) {
  if (!forecastResult) return null;

  const recommendation = forecastResult.recommendation || {};
  const action = recommendation.action;
  const tone = getTone(action, forecastResult.price_delta_percent);
  const actionLabel = actionLabels[action] || action || 'Нет рекомендации';
  const reason = reasonLabels[recommendation.reason_code] || 'Сигнал рассчитан по текущему прогнозу';
  const hasPosition = Boolean(recommendation.has_position);

  const metrics = [
    { label: 'Текущая цена', value: `${formatMoney(forecastResult.current_price)} ₽` },
    { label: 'Прогноз', value: `${formatMoney(forecastResult.predicted_price)} ₽` },
    { label: 'Изменение', value: formatSignedPercent(forecastResult.price_delta_percent), className: tone.value },
    { label: 'Модель', value: String(forecastResult.model_type_effective || forecastResult.model_type || '—').toUpperCase() },
  ];

  const details = [
    { label: 'Позиция', value: hasPosition ? 'есть в портфеле' : 'нет в портфеле' },
    { label: 'Количество', value: recommendation.quantity != null ? formatMoney(recommendation.quantity) : '—' },
    { label: 'Свободные деньги', value: `${formatMoney(recommendation.cash_balance)} ₽` },
    { label: 'Средняя цена', value: `${formatMoney(recommendation.average_buy_price)} ₽` },
    { label: 'От средней', value: formatSignedPercent(recommendation.expected_profit_from_avg_percent) },
    { label: 'Причина', value: reason },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {metrics.map((item) => (
          <div key={item.label} className="border border-yellow-400/12 bg-[#12110e] p-4">
            <div className="text-xs text-zinc-500">{item.label}</div>
            <div className={`mt-2 text-xl font-black text-white ${item.className || ''}`}>{item.value}</div>
          </div>
        ))}
      </div>

      <article className={`border p-5 shadow-[0_18px_45px_rgba(0,0,0,0.18)] ${tone.card}`}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className={`mb-3 inline-flex border px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] ${tone.badge}`}>
              Рекомендация
            </div>
            <div className="text-3xl font-black tracking-tight text-white">{actionLabel}</div>
            <p className="mt-3 max-w-4xl text-base leading-7 text-zinc-300">
              {recommendation.message || 'Модель рассчитала прогноз. Проверьте параметры и принимайте решение вручную.'}
            </p>
          </div>
          <div className="border border-yellow-400/12 bg-black/20 px-4 py-3 text-right">
            <div className="text-xs text-zinc-500">Сигнал</div>
            <div className={`mt-1 text-2xl font-black ${tone.value}`}>{formatSignedPercent(forecastResult.price_delta_percent)}</div>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {details.map((item) => (
            <div key={item.label} className="border border-white/10 bg-black/20 p-3">
              <div className="text-xs text-zinc-500">{item.label}</div>
              <div className="mt-1 text-sm font-bold text-zinc-100">{item.value}</div>
            </div>
          ))}
        </div>
      </article>
    </div>
  );
}
