import React from 'react';
import { normalizeUserMessage } from '../../../services/api';
import { ButtonLoader, TableLoader } from '../../common/LoadingSpinner';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  LabelList,
  Tooltip,
} from 'recharts';

const formatNumber = (value, digits = 2) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number.toLocaleString('ru-RU', { maximumFractionDigits: digits });
};

const actionLabels = {
  SELL: 'Продать',
  HOLD: 'Держать',
  HOLD_AND_OPTIONAL_BUY: 'Держать / докупить',
  BUY_OPTIONAL: 'Можно купить',
  WAIT: 'Ждать',
  DO_NOT_BUY: 'Не покупать',
};

const modelColors = {
  svr: '#facc15',
  gpr: '#38bdf8',
  adaptive: '#22c55e',
};

const modelLabels = {
  svr: 'SVR',
  gpr: 'GPR',
  adaptive: 'Adaptive',
};

function MetricTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  const value = payload[0]?.value;

  return (
    <div className="border border-yellow-400/20 bg-[#0c0b08] px-3 py-2 text-sm shadow-xl">
      <div className="font-semibold text-white">{modelLabels[String(label).toLowerCase()] || label}</div>
      <div className="mt-1 text-yellow-200">MAE: {formatNumber(value, 4)}</div>
    </div>
  );
}

export default function ModelComparisonPanel({ compareResult, compareLoading, onCompare }) {
  const rows = (compareResult?.results || []).map(item => ({
    ...item,
    chartName: modelLabels[String(item.model_type || '').toLowerCase()] || item.model_type || 'model',
    mae: Number.isFinite(Number(item.metrics?.MAE)) ? Number(item.metrics?.MAE) : 0,
    delta: Number(item.price_delta_percent),
  }));
  const successfulRows = rows.filter(item => item.compare_status === 'success');

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-gray-200 dark:border-zinc-800 bg-white dark:bg-[#111111] p-6 shadow-lg">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">Сравнение моделей</h2>
            <p className="text-sm text-gray-500 dark:text-zinc-500">SVR, GPR и adaptive запускаются на одном инструменте и горизонте.</p>
          </div>
          <button
            type="button"
            onClick={onCompare}
            disabled={compareLoading}
            className="inline-flex items-center justify-center px-5 py-3 rounded-xl font-bold bg-yellow-400 hover:bg-yellow-300 disabled:bg-gray-700 text-black shadow-lg"
          >
            {compareLoading ? <ButtonLoader label="Сравниваем..." dark /> : 'Сравнить все модели'}
          </button>
        </div>

        {compareResult?.summary && (
          <div className="grid grid-cols-1 gap-3 mb-5 md:grid-cols-3">
            <div className="border border-yellow-400/15 bg-[#15130e] p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-zinc-500">Лучшая по MAE</div>
              <div className="mt-2 text-xl font-black text-yellow-200">{modelLabels[String(compareResult.summary.best_by_mae || '').toLowerCase()] || compareResult.summary.best_by_mae || '—'}</div>
            </div>
            <div className="border border-emerald-400/15 bg-[#10150f] p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-zinc-500">Успешно построено</div>
              <div className="mt-2 text-xl font-black text-emerald-300">{compareResult.summary.successful_models || 0}</div>
            </div>
            <div className="border border-red-400/15 bg-[#15100f] p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-zinc-500">Ошибок</div>
              <div className="mt-2 text-xl font-black text-red-300">{compareResult.summary.failed_models || 0}</div>
            </div>
          </div>
        )}

        <div className="overflow-x-auto border border-yellow-400/12 bg-[#0d0c09]">
          <table className="w-full text-sm">
            <thead className="border-b border-yellow-400/12 bg-[#16130d] text-xs uppercase tracking-[0.08em] text-zinc-400">
              <tr>
                <th className="px-4 py-3 text-left">Модель</th>
                <th className="px-4 py-3 text-left">Эффективная</th>
                <th className="px-4 py-3 text-right">Прогноз</th>
                <th className="px-4 py-3 text-right">Δ %</th>
                <th className="px-4 py-3 text-right">MAE</th>
                <th className="px-4 py-3 text-right">RMSE</th>
                <th className="px-4 py-3 text-right">R²</th>
                <th className="px-4 py-3 text-left">Решение</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-yellow-400/10">
              {compareLoading ? (
                <TableLoader colSpan={8} label="Сравниваем модели..." />
              ) : rows.map((item, index) => (
                <tr key={`${item.model_type}-${index}`} className="bg-[#11100d] text-zinc-200 transition-colors hover:bg-[#17140f]">
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-2 font-black uppercase text-white">
                      <span className="h-2.5 w-2.5" style={{ background: modelColors[String(item.model_type).toLowerCase()] || '#facc15' }} />
                      {modelLabels[String(item.model_type || '').toLowerCase()] || item.model_type || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-300">{modelLabels[String(item.model_type_effective || '').toLowerCase()] || item.model_type_effective || (item.compare_status === 'error' ? 'ошибка' : '—')}</td>
                  {item.compare_status === 'error' ? (
                    <td className="px-4 py-3 text-red-600" colSpan="6">{normalizeUserMessage(item.detail, 'Не удалось построить эту модель.')}</td>
                  ) : (
                    <>
                      <td className="px-4 py-3 text-right font-mono text-white">{formatNumber(item.predicted_price)} ₽</td>
                      <td className={`px-4 py-3 text-right font-mono ${item.price_delta_percent >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{formatNumber(item.price_delta_percent)}%</td>
                      <td className="px-4 py-3 text-right font-mono text-yellow-100">{formatNumber(item.metrics?.MAE, 4)}</td>
                      <td className="px-4 py-3 text-right font-mono text-zinc-300">{formatNumber(item.metrics?.RMSE, 4)}</td>
                      <td className="px-4 py-3 text-right font-mono text-zinc-300">{formatNumber(item.metrics?.R2, 4)}</td>
                      <td className="px-4 py-3 text-zinc-200">{actionLabels[item.recommendation?.action] || item.recommendation?.action || '—'}</td>
                    </>
                  )}
                </tr>
              ))}
              {!compareLoading && rows.length === 0 && (
                <tr>
                  <td className="px-4 py-8 text-center text-gray-500 dark:text-zinc-500" colSpan="8">Сравнение еще не запускалось.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {successfulRows.length > 0 && (
        <div className="border border-yellow-400/12 bg-[#11100d] p-6 shadow-lg">
          <div className="mb-5 flex flex-col gap-1">
            <h3 className="text-lg font-bold text-white">MAE по моделям</h3>
            <p className="text-sm text-zinc-500">Чем ниже столбец, тем точнее модель на проверочном участке.</p>
          </div>
          <div className="h-80 border border-yellow-400/10 bg-[#0b0a08] p-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={successfulRows} margin={{ top: 24, right: 24, bottom: 8, left: 0 }}>
                <CartesianGrid stroke="rgba(250,204,21,0.12)" strokeDasharray="4 6" vertical={false} />
                <XAxis
                  dataKey="chartName"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#a1a1aa', fontSize: 13, fontWeight: 700 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  width={54}
                  tick={{ fill: '#71717a', fontSize: 12 }}
                  domain={[0, (dataMax) => Math.max(0.1, dataMax * 1.18)]}
                />
                <Tooltip cursor={{ fill: 'rgba(250,204,21,0.06)' }} content={<MetricTooltip />} />
                <Bar dataKey="mae" name="MAE" maxBarSize={90} minPointSize={6} radius={[6, 6, 0, 0]}>
                  {successfulRows.map((item) => (
                    <Cell key={item.model_type} fill={modelColors[String(item.model_type).toLowerCase()] || '#facc15'} />
                  ))}
                  <LabelList
                    dataKey="mae"
                    position="top"
                    formatter={(value) => formatNumber(value, 4)}
                    fill="#f4f4f5"
                    fontSize={12}
                    fontWeight={700}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
