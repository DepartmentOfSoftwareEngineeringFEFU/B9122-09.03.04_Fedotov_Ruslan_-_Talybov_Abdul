import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';

const toNumber = (value, fallback = null) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

const formatMoney = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
};

export default function ForecastPriceChart({ candles = [], forecastResult = null, isDark = false }) {
  const sliced = candles.slice(-90).map((item, index) => {
    const time = item.time || item.x || item.ts;
    const close = toNumber(item.close ?? item.c ?? item.y);
    return {
      idx: index + 1,
      label: time ? new Date(time).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : `${index + 1}`,
      close,
      prediction: null,
      current: null,
    };
  }).filter(item => Number.isFinite(item.close));

  const currentPrice = toNumber(forecastResult?.current_price);
  const predictedPrice = toNumber(forecastResult?.predicted_price);
  const chartData = [...sliced];

  if (forecastResult && Number.isFinite(predictedPrice)) {
    chartData.push({
      idx: chartData.length + 1,
      label: forecastResult.horizon === '1d' ? '+1 день' : '+1 час',
      close: null,
      prediction: predictedPrice,
      current: Number.isFinite(currentPrice) ? currentPrice : null,
    });
  }

  return (
    <div className="rounded-3xl border border-gray-200 dark:border-zinc-800 bg-white dark:bg-[#111111] p-6 shadow-lg">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
        <div>
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">График цены и прогнозной точки</h3>
          <p className="text-sm text-gray-500 dark:text-zinc-500">История close + точка прогноза выбранной модели.</p>
        </div>
        {forecastResult && (
          <div className="text-right text-sm">
            <div className="text-gray-500 dark:text-zinc-500">Прогноз</div>
            <div className={`text-xl font-bold ${forecastResult.price_delta_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatMoney(predictedPrice)} ₽ / {Number(forecastResult.price_delta_percent || 0).toFixed(2)}%
            </div>
          </div>
        )}
      </div>

      <div className="h-80">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis dataKey="label" minTickGap={28} tick={{ fontSize: 11 }} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} tickFormatter={value => formatMoney(value)} />
              <Tooltip
                contentStyle={{
                  borderRadius: 0,
                  border: 'none',
                  background: isDark ? '#111827' : '#ffffff',
                  color: isDark ? '#ffffff' : '#111827',
                }}
                formatter={(value, name) => [formatMoney(value), name === 'close' ? 'Close' : name === 'current' ? 'Текущая' : 'Прогноз']}
              />
              {Number.isFinite(currentPrice) && <ReferenceLine y={currentPrice} strokeDasharray="4 4" label="текущая" />}
              <Line type="monotone" dataKey="close" name="Close" strokeWidth={2} dot={false} connectNulls />
              <Line type="monotone" dataKey="current" name="Текущая" strokeWidth={2} dot={{ r: 4 }} connectNulls />
              <Line type="monotone" dataKey="prediction" name="Прогноз" strokeWidth={3} dot={{ r: 6 }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-gray-500 dark:text-zinc-500 text-sm">
            Загрузите свечи или постройте прогноз, чтобы увидеть график.
          </div>
        )}
      </div>
    </div>
  );
}
