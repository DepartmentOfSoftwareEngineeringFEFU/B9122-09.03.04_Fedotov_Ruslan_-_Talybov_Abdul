import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { analyticsAPI, getErrorMessage, normalizeUserMessage, tradeAPI } from '../../services/api';
import { formatShortId } from '../../utils/formatters';
import LoadingSpinner, { ButtonLoader, TableLoader } from '../common/LoadingSpinner';

const EMPTY_OVERVIEW = {
  portfolio: {
    total_value: 0,
    cash_balance: 0,
    total_stocks_value: 0,
    total_profit: 0,
    total_profit_percent: 0,
    positions_count: 0,
    positions: [],
  },
  manual_trades: {
    total_trades: 0,
    buy_trades: 0,
    sell_trades: 0,
    buy_amount: 0,
    sell_amount: 0,
    net_cash_flow: 0,
    realized_pnl: 0,
    avg_realized_pnl_percent: 0,
    recent: [],
  },
  bot_analytics: {
    total_trades: 0,
    closed_trades: 0,
    open_trades: 0,
    scheduled_auto_sells: 0,
    failed_trades: 0,
    realized_pnl: 0,
    realized_pnl_percent: 0,
    win_rate: 0,
    avg_trade_return_percent: 0,
    best_trade_percent: 0,
    worst_trade_percent: 0,
    by_model: {},
  },
  model_quality: {
    total_forecasts: 0,
    rows: [],
    effective_distribution: {},
    recommendation_distribution: {},
    horizon_distribution: {},
    recent_forecasts: [],
  },
  backtests: {
    total_backtests: 0,
    best_return: 0,
    avg_return: 0,
    avg_sharpe: 0,
    worst_drawdown: 0,
    recent: [],
  },
  charts: {
    bot_pnl_timeline: [],
    model_pnl: [],
    trade_status_distribution: [],
    forecast_timeline: [],
    model_forecast_counts: [],
    recommendation_distribution: [],
  },
  risk_warnings: [],
  analytics_errors: [],
  bot_history: [],
  filters: {},
};

const TABS = [
  { id: 'overview', label: 'Обзор' },
  { id: 'bot', label: 'ML-бот' },
  { id: 'models', label: 'Модели' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'manual', label: 'Сделки' },
  { id: 'risks', label: 'Риски' },
];

const MODEL_LABELS = {
  svr: 'SVR',
  gpr: 'GPR',
  adaptive: 'Adaptive',
  ensemble: 'Ensemble',
  unknown: 'Unknown',
};

const HORIZON_LABELS = {
  '1h': '1 час',
  '1d': '1 день',
  unknown: '—',
};

const RECOMMENDATION_LABELS = {
  buy: 'Покупка',
  sell: 'Продажа',
  hold: 'Удержание',
  none: 'Нет действия',
  schedule_sell: 'Auto-sell',
  unknown: 'Неизвестно',
};

const CHART_COLORS = ['#facc15', '#22c55e', '#ef4444', '#f97316', '#a1a1aa', '#f4f4f5'];
const SELECTED_ACCOUNT_STORAGE_KEY = 'trade.selected_account_id';

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getStoredAccountId() {
  try {
    return window.localStorage.getItem(SELECTED_ACCOUNT_STORAGE_KEY) || '';
  } catch (_error) {
    return '';
  }
}

function storeAccountId(accountId) {
  try {
    if (accountId) {
      window.localStorage.setItem(SELECTED_ACCOUNT_STORAGE_KEY, accountId);
    } else {
      window.localStorage.removeItem(SELECTED_ACCOUNT_STORAGE_KEY);
    }
  } catch (_error) {
    // localStorage may be unavailable in private mode; analytics still works without persistence.
  }
}

function formatMoney(value) {
  return number(value).toLocaleString('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatCompact(value) {
  return number(value).toLocaleString('ru-RU', {
    maximumFractionDigits: 0,
  });
}

function formatPercent(value, signed = true) {
  const parsed = number(value);
  const prefix = signed && parsed > 0 ? '+' : '';
  return `${prefix}${parsed.toFixed(2)}%`;
}

function formatMetric(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return Number(value).toFixed(digits);
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatChartDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
  });
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function activeRiskWarnings(value) {
  return safeArray(value).filter((warning) => warning?.severity && warning.severity !== 'success');
}

function normalizeAccountStatus(status) {
  const rawStatus = String(status ?? '').toUpperCase();
  if (rawStatus.includes('ACCOUNT_STATUS_CLOSED') || rawStatus === '3' || rawStatus === 'CLOSED') {
    return 'closed';
  }
  if (rawStatus.includes('ACCOUNT_STATUS_OPEN') || rawStatus === '2' || rawStatus === 'OPEN') {
    return 'open';
  }
  return 'unknown';
}

function isOpenAccount(account) {
  return normalizeAccountStatus(account?.status) !== 'closed';
}

function latestAccountFirst(left, right) {
  const leftDate = Date.parse(left?.opened_date || '') || 0;
  const rightDate = Date.parse(right?.opened_date || '') || 0;
  return rightDate - leftDate;
}

function accountOptionLabel(account) {
  const name = account?.name ? `${account.name} · ` : '';
  return `${name}${formatShortId(account?.id)}`;
}

function modelLabel(value) {
  const key = String(value || 'unknown').toLowerCase();
  return MODEL_LABELS[key] || value || 'Unknown';
}

function toneByNumber(value) {
  return number(value) >= 0 ? 'positive' : 'negative';
}

function buildDateFrom(period) {
  if (period === 'all') return undefined;
  const days = Number(period);
  if (!Number.isFinite(days)) return undefined;
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString();
}

function normalizeOverview(data) {
  return {
    ...EMPTY_OVERVIEW,
    ...(data || {}),
    portfolio: { ...EMPTY_OVERVIEW.portfolio, ...(data?.portfolio || {}) },
    manual_trades: { ...EMPTY_OVERVIEW.manual_trades, ...(data?.manual_trades || {}) },
    bot_analytics: { ...EMPTY_OVERVIEW.bot_analytics, ...(data?.bot_analytics || {}) },
    model_quality: { ...EMPTY_OVERVIEW.model_quality, ...(data?.model_quality || {}) },
    backtests: { ...EMPTY_OVERVIEW.backtests, ...(data?.backtests || {}) },
    charts: { ...EMPTY_OVERVIEW.charts, ...(data?.charts || {}) },
    risk_warnings: safeArray(data?.risk_warnings),
    analytics_errors: safeArray(data?.analytics_errors),
    bot_history: safeArray(data?.bot_history),
    filters: { ...EMPTY_OVERVIEW.filters, ...(data?.filters || {}) },
  };
}

function Card({ title, children, right }) {
  return (
    <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-lg dark:border-zinc-800 dark:bg-[#111111]">
      <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <h3 className="text-xl font-semibold text-gray-800 dark:text-white">{title}</h3>
        {right}
      </div>
      {children}
    </div>
  );
}

function StatCard({ label, value, hint, tone = 'neutral' }) {
  const toneClass = {
    positive: 'text-green-600 dark:text-green-400',
    negative: 'text-red-600 dark:text-red-400',
    blue: 'text-blue-600 dark:text-yellow-400',
    amber: 'text-amber-600 dark:text-amber-300',
    neutral: 'text-gray-900 dark:text-white',
  }[tone];

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-[#111111]">
      <div className="text-sm text-gray-500 dark:text-zinc-500">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${toneClass}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-gray-500 dark:text-zinc-500">{hint}</div>}
    </div>
  );
}

function EmptyState({ children = 'Данных пока нет.' }) {
  return (
    <div className="rounded-2xl bg-gray-50 p-6 text-center text-sm text-gray-500 dark:bg-zinc-900/70 dark:text-zinc-300">
      {children}
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 text-xs shadow-lg dark:border-zinc-800 dark:bg-[#070707] dark:text-gray-100">
      {label && <div className="mb-1 font-semibold">{label}</div>}
      {payload.map((item) => (
        <div key={item.name} className="flex items-center justify-between gap-4">
          <span>{item.name}</span>
          <span className="font-semibold">{formatMetric(item.value)}</span>
        </div>
      ))}
    </div>
  );
}

function preparePnlChartData(data) {
  return safeArray(data).map((item, index, items) => {
    const previous = items[index - 1];
    const isFirstForDate = index === 0 || previous?.date !== item?.date;
    return {
      ...item,
      tradeNumber: index + 1,
      dateTick: isFirstForDate ? formatChartDate(item.date) : '',
    };
  });
}

function PnlTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload || {};
  const pnl = number(row.pnl);
  const cumulative = number(row.cumulative_pnl);

  return (
    <div className="min-w-[190px] border border-yellow-400/15 bg-[#080807] p-3 text-xs shadow-2xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="font-bold text-white">{row.ticker || 'Сделка'}</div>
          <div className="mt-0.5 text-zinc-500">{row.date || '—'} · #{row.tradeNumber}</div>
        </div>
        <div className="text-right text-zinc-400">{modelLabel(row.model)}</div>
      </div>
      <div className="mt-3 space-y-1.5">
        <div className="flex items-center justify-between gap-4">
          <span className="text-zinc-500">Накопленный P/L</span>
          <span className={`font-mono font-bold ${cumulative >= 0 ? 'text-yellow-300' : 'text-red-300'}`}>
            {cumulative >= 0 ? '+' : ''}{formatMoney(cumulative)} ₽
          </span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-zinc-500">P/L сделки</span>
          <span className={`font-mono font-bold ${pnl >= 0 ? 'text-green-300' : 'text-red-300'}`}>
            {pnl >= 0 ? '+' : ''}{formatMoney(pnl)} ₽
          </span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-zinc-500">Доходность</span>
          <span className="font-mono font-bold text-white">{formatPercent(row.return_percent)}</span>
        </div>
      </div>
    </div>
  );
}

function PnlLineChart({ data }) {
  if (!data.length) return <EmptyState>Нет закрытых ML-сделок для графика P/L.</EmptyState>;
  const chartData = preparePnlChartData(data);
  const latest = chartData[chartData.length - 1] || {};
  const positiveTrades = chartData.filter((item) => number(item.pnl) > 0).length;
  const winRate = chartData.length ? (positiveTrades / chartData.length) * 100 : 0;
  const avgTradePnl = chartData.length
    ? chartData.reduce((sum, item) => sum + number(item.pnl), 0) / chartData.length
    : 0;
  const yValues = chartData.flatMap((item) => [number(item.cumulative_pnl), number(item.pnl)]);
  const yMin = Math.min(0, ...yValues);
  const yMax = Math.max(0, ...yValues);
  const yPadding = Math.max((yMax - yMin) * 0.12, 50);

  return (
    <div>
      <div className="mb-4 grid grid-cols-2 gap-3 text-sm lg:grid-cols-4">
        <div>
          <div className="text-xs text-zinc-500">Итог</div>
          <div className={`mt-1 font-mono text-lg font-black ${number(latest.cumulative_pnl) >= 0 ? 'text-yellow-300' : 'text-red-300'}`}>
            {number(latest.cumulative_pnl) >= 0 ? '+' : ''}{formatMoney(latest.cumulative_pnl)} ₽
          </div>
        </div>
        <div>
          <div className="text-xs text-zinc-500">Закрыто</div>
          <div className="mt-1 font-mono text-lg font-black text-white">{formatCompact(chartData.length)}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500">Win rate</div>
          <div className="mt-1 font-mono text-lg font-black text-green-300">{formatPercent(winRate, false)}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500">Средняя сделка</div>
          <div className={`mt-1 font-mono text-lg font-black ${avgTradePnl >= 0 ? 'text-green-300' : 'text-red-300'}`}>
            {avgTradePnl >= 0 ? '+' : ''}{formatMoney(avgTradePnl)} ₽
          </div>
        </div>
      </div>

      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 12, right: 18, bottom: 8, left: 0 }}>
            <defs>
              <linearGradient id="pnlGoldLine" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#f59e0b" />
                <stop offset="100%" stopColor="#fde047" />
              </linearGradient>
              <linearGradient id="pnlGreenLine" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#16a34a" />
                <stop offset="100%" stopColor="#4ade80" />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(250,204,21,0.12)" strokeDasharray="4 8" vertical={false} />
            <XAxis
              dataKey="tradeNumber"
              tick={{ fontSize: 11, fill: '#71717a' }}
              tickLine={false}
              axisLine={{ stroke: 'rgba(250,204,21,0.16)' }}
              interval="preserveStartEnd"
              minTickGap={28}
              tickFormatter={(_value, index) => chartData[index]?.dateTick || ''}
            />
            <YAxis
              width={72}
              tick={{ fontSize: 11, fill: '#71717a' }}
              tickLine={false}
              axisLine={false}
              domain={[Math.floor(yMin - yPadding), Math.ceil(yMax + yPadding)]}
              tickFormatter={(value) => `${formatCompact(value)} ₽`}
            />
            <ReferenceLine y={0} stroke="rgba(244,244,245,0.28)" strokeDasharray="5 5" />
            <Tooltip cursor={{ stroke: 'rgba(250,204,21,0.28)', strokeWidth: 1 }} content={<PnlTooltip />} />
            <Line
              type="monotone"
              dataKey="cumulative_pnl"
              name="Накопленный P/L"
              stroke="url(#pnlGoldLine)"
              strokeWidth={4}
              dot={{ r: 3.5, strokeWidth: 2, stroke: '#0b0b09', fill: '#facc15' }}
              activeDot={{ r: 6, strokeWidth: 2, stroke: '#fef3c7', fill: '#facc15' }}
            />
            <Line
              type="monotone"
              dataKey="pnl"
              name="P/L сделки"
              stroke="url(#pnlGreenLine)"
              strokeWidth={2.5}
              dot={{ r: 3, strokeWidth: 2, stroke: '#0b0b09', fill: '#22c55e' }}
              activeDot={{ r: 5, strokeWidth: 2, stroke: '#bbf7d0', fill: '#22c55e' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-zinc-500">
        <span className="inline-flex items-center gap-2"><span className="h-2 w-5 bg-yellow-400" />Накопленный P/L</span>
        <span className="inline-flex items-center gap-2"><span className="h-2 w-5 bg-green-400" />P/L сделки</span>
      </div>
    </div>
  );
}

function SimpleBarChart({ data, xKey, bars }) {
  if (!data.length) return <EmptyState />;
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip content={<CustomTooltip />} />
          {bars.map((bar, index) => (
            <Bar key={bar.key} dataKey={bar.key} name={bar.name} fill={CHART_COLORS[index % CHART_COLORS.length]} radius={[0, 0, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function SimplePieChart({ data }) {
  if (!data.length) return <EmptyState />;
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Tooltip content={<CustomTooltip />} />
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={3}>
            {data.map((_entry, index) => (
              <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function RiskBadge({ severity }) {
  const classes = {
    success: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-200',
    info: 'bg-blue-100 text-blue-700 dark:bg-yellow-400/10 dark:text-yellow-200',
    warning: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200',
    critical: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-200',
  };
  const labels = {
    success: 'OK',
    info: 'Инфо',
    warning: 'Риск',
    critical: 'Критично',
  };
  return <span className={`rounded-none px-3 py-1 text-xs font-semibold ${classes[severity] || classes.info}`}>{labels[severity] || 'Инфо'}</span>;
}

function Filters({
  filters,
  onChange,
  onRefresh,
  loading,
  accounts,
  selectedAccountId,
  onAccountChange,
  accountsLoading,
}) {
  const update = (key, value) => onChange((current) => ({ ...current, [key]: value }));

  return (
    <div className="rounded-3xl border border-gray-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-[#111111]">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <label className="text-sm text-gray-600 dark:text-zinc-300">
          Период
          <select
            value={filters.period}
            onChange={(event) => update('period', event.target.value)}
            className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-gray-900 dark:border-zinc-800 dark:bg-[#070707] dark:text-white"
          >
            <option value="7">7 дней</option>
            <option value="30">30 дней</option>
            <option value="90">90 дней</option>
            <option value="all">Всё время</option>
          </select>
        </label>

        <label className="text-sm text-gray-600 dark:text-zinc-300">
          Счет
          <select
            value={selectedAccountId}
            onChange={(event) => onAccountChange(event.target.value)}
            disabled={accountsLoading}
            className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-gray-900 disabled:opacity-70 dark:border-zinc-800 dark:bg-[#070707] dark:text-white"
          >
            <option value="">{accountsLoading ? 'Загрузка...' : 'Все счета'}</option>
            {safeArray(accounts).map((account) => (
              <option key={account.id} value={account.id}>
                {accountOptionLabel(account)}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-gray-600 dark:text-zinc-300">
          Модель
          <select
            value={filters.model_type}
            onChange={(event) => update('model_type', event.target.value)}
            className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-gray-900 dark:border-zinc-800 dark:bg-[#070707] dark:text-white"
          >
            <option value="">Все</option>
            <option value="svr">SVR</option>
            <option value="gpr">GPR</option>
            <option value="adaptive">Adaptive</option>
            <option value="ensemble">Ensemble</option>
          </select>
        </label>

        <label className="text-sm text-gray-600 dark:text-zinc-300">
          Горизонт
          <select
            value={filters.horizon}
            onChange={(event) => update('horizon', event.target.value)}
            className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-gray-900 dark:border-zinc-800 dark:bg-[#070707] dark:text-white"
          >
            <option value="">Все</option>
            <option value="1h">1 час</option>
            <option value="1d">1 день</option>
          </select>
        </label>

        <label className="text-sm text-gray-600 dark:text-zinc-300">
          FIGI
          <input
            value={filters.figi}
            onChange={(event) => update('figi', event.target.value)}
            placeholder="Напр. BBG004730N88"
            className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-gray-900 placeholder:text-gray-400 dark:border-zinc-800 dark:bg-[#070707] dark:text-white"
          />
        </label>

        <div className="flex items-end">
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="inline-flex w-full items-center justify-center rounded-xl bg-yellow-400 px-4 py-2.5 font-semibold text-black hover:bg-yellow-300 disabled:opacity-60 dark:bg-yellow-400 dark:text-black dark:hover:bg-yellow-300"
          >
            {loading ? <ButtonLoader label="Обновляем..." dark /> : 'Обновить'}
          </button>
        </div>
      </div>
    </div>
  );
}

function MetricStrip({ overview }) {
  const bot = overview.bot_analytics;
  const modelQuality = overview.model_quality;
  const risks = activeRiskWarnings(overview.risk_warnings);

  const items = [
    { label: 'ML P/L', value: `${number(bot.realized_pnl) >= 0 ? '+' : ''}${formatMoney(bot.realized_pnl)} ₽`, tone: toneByNumber(bot.realized_pnl) },
    { label: 'Win Rate', value: formatPercent(bot.win_rate, false), tone: number(bot.win_rate) >= 50 ? 'positive' : 'neutral' },
    { label: 'Прогнозы', value: formatCompact(modelQuality.total_forecasts), tone: 'neutral' },
    { label: 'Риски', value: risks.length, tone: risks.length ? 'negative' : 'positive' },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const toneClass = {
          positive: 'text-green-400',
          negative: 'text-red-400',
          neutral: 'text-white',
        }[item.tone] || 'text-white';

        return (
          <div key={item.label} className="rounded-3xl border border-gray-200 bg-white px-5 py-4 shadow-sm dark:border-zinc-800 dark:bg-[#111111]">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-zinc-500">{item.label}</div>
            <div className={`mt-2 text-2xl font-black ${toneClass}`}>{item.value}</div>
          </div>
        );
      })}
    </div>
  );
}

function AnalyticsEssentials({ overview }) {
  const bot = overview.bot_analytics;
  const modelQuality = overview.model_quality;
  const backtests = overview.backtests;
  const risks = activeRiskWarnings(overview.risk_warnings).slice(0, 3);
  const charts = overview.charts;

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card title="ML P/L">
        <PnlLineChart data={safeArray(charts.bot_pnl_timeline)} />
      </Card>

      <Card title="Состояние">
        <div className="space-y-3">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3 text-sm dark:border-zinc-800">
            <span className="text-gray-500 dark:text-zinc-500">Сделки</span>
            <span className="font-semibold text-gray-900 dark:text-white">{formatCompact(bot.total_trades)}</span>
          </div>
          <div className="flex items-center justify-between border-b border-gray-100 pb-3 text-sm dark:border-zinc-800">
            <span className="text-gray-500 dark:text-zinc-500">Прогнозы</span>
            <span className="font-semibold text-gray-900 dark:text-white">{formatCompact(modelQuality.total_forecasts)}</span>
          </div>
          <div className="flex items-center justify-between border-b border-gray-100 pb-3 text-sm dark:border-zinc-800">
            <span className="text-gray-500 dark:text-zinc-500">Backtest</span>
            <span className="font-semibold text-gray-900 dark:text-white">{formatCompact(backtests.total_backtests)}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500 dark:text-zinc-500">Риски</span>
            <span className={risks.length ? 'font-semibold text-red-400' : 'font-semibold text-green-400'}>{risks.length || 'нет'}</span>
          </div>
        </div>

        <div className="mt-5 space-y-2">
          {risks.length === 0 ? (
            <div className="rounded-2xl border border-green-500/20 bg-green-500/10 p-3 text-sm text-green-200">Критичных предупреждений нет.</div>
          ) : risks.map((warning, index) => (
            <div key={`${warning.title}-${index}`} className="rounded-2xl border border-red-500/20 bg-red-500/10 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-white">{warning.title}</div>
                  <div className="mt-1 line-clamp-2 text-xs text-zinc-400">{warning.message}</div>
                </div>
                <RiskBadge severity={warning.severity} />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function OverviewTab({ overview }) {
  const portfolio = overview.portfolio;
  const bot = overview.bot_analytics;
  const manual = overview.manual_trades;
  const modelQuality = overview.model_quality;
  const backtests = overview.backtests;
  const charts = overview.charts;
  const risks = activeRiskWarnings(overview.risk_warnings).slice(0, 3);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
        <StatCard label="Портфель" value={`${formatMoney(portfolio.total_value)} ₽`} hint={`${portfolio.positions_count || safeArray(portfolio.positions).length} позиций`} />
        <StatCard label="Свободные деньги" value={`${formatMoney(portfolio.cash_balance)} ₽`} hint="Ликвидность" tone="blue" />
        <StatCard label="Нереализованный P/L" value={`${number(portfolio.total_profit) >= 0 ? '+' : ''}${formatMoney(portfolio.total_profit)} ₽`} hint={formatPercent(portfolio.total_profit_percent)} tone={toneByNumber(portfolio.total_profit)} />
        <StatCard label="ML-бот P/L" value={`${number(bot.realized_pnl) >= 0 ? '+' : ''}${formatMoney(bot.realized_pnl)} ₽`} hint={`Win rate ${formatPercent(bot.win_rate, false)}`} tone={toneByNumber(bot.realized_pnl)} />
        <StatCard label="Прогнозов" value={formatCompact(modelQuality.total_forecasts)} hint="Сохраненные ModelForecast" tone="amber" />
        <StatCard label="Backtest" value={formatCompact(backtests.total_backtests)} hint={`средн. доходн. ${formatPercent(number(backtests.avg_return) * 100, false)}`} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Equity curve ML-бота">
          <PnlLineChart data={safeArray(charts.bot_pnl_timeline)} />
        </Card>
        <Card title="P/L по моделям">
          <SimpleBarChart data={safeArray(charts.model_pnl).map((row) => ({ ...row, model: modelLabel(row.model) }))} xKey="model" bars={[{ key: 'pnl', name: 'P/L' }, { key: 'avg_return', name: 'Средн. доходность %' }]} />
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card title="Диагностика системы">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-2xl bg-gray-50 p-4 dark:bg-zinc-900/70">
              <div className="text-gray-500 dark:text-zinc-500">ML-сделки</div>
              <div className="text-xl font-semibold text-gray-900 dark:text-white">{bot.total_trades}</div>
            </div>
            <div className="rounded-2xl bg-gray-50 p-4 dark:bg-zinc-900/70">
              <div className="text-gray-500 dark:text-zinc-500">Закрытые</div>
              <div className="text-xl font-semibold text-gray-900 dark:text-white">{bot.closed_trades}</div>
            </div>
            <div className="rounded-2xl bg-gray-50 p-4 dark:bg-zinc-900/70">
              <div className="text-gray-500 dark:text-zinc-500">Ручные сделки</div>
              <div className="text-xl font-semibold text-gray-900 dark:text-white">{manual.total_trades}</div>
            </div>
            <div className="rounded-2xl bg-gray-50 p-4 dark:bg-zinc-900/70">
              <div className="text-gray-500 dark:text-zinc-500">Failed ML</div>
              <div className="text-xl font-semibold text-gray-900 dark:text-white">{bot.failed_trades}</div>
            </div>
          </div>
        </Card>

        <Card title="Рекомендации моделей">
          <SimplePieChart data={safeArray(charts.recommendation_distribution).map((row) => ({ ...row, name: RECOMMENDATION_LABELS[row.name] || row.name }))} />
        </Card>

        <Card title="Короткие предупреждения">
          <div className="space-y-3">
            {risks.length === 0 ? (
              <EmptyState />
            ) : risks.map((warning, index) => (
              <div key={`${warning.title}-${index}`} className="rounded-2xl bg-gray-50 p-4 dark:bg-zinc-900/70">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="font-semibold text-gray-900 dark:text-white">{warning.title}</div>
                  <RiskBadge severity={warning.severity} />
                </div>
                <div className="text-sm text-gray-500 dark:text-zinc-300">{warning.message}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function BotTab({ overview, loading }) {
  const bot = overview.bot_analytics;
  const charts = overview.charts;
  const botHistory = safeArray(overview.bot_history);
  const modelRows = Object.entries(bot.by_model || {});

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Всего ML-сделок" value={formatCompact(bot.total_trades)} hint="Все статусы" />
        <StatCard label="Закрыто" value={formatCompact(bot.closed_trades)} hint="Можно оценивать результат" tone="blue" />
        <StatCard label="Открыто" value={formatCompact(bot.open_trades)} hint="Еще без финального P/L" />
        <StatCard label="Win Rate" value={formatPercent(bot.win_rate, false)} hint="По закрытым сделкам" tone={number(bot.win_rate) >= 50 ? 'positive' : 'negative'} />
        <StatCard label="Средняя доходность" value={formatPercent(bot.avg_trade_return_percent)} hint={`луч. ${formatPercent(bot.best_trade_percent)} / худ. ${formatPercent(bot.worst_trade_percent)}`} tone={toneByNumber(bot.avg_trade_return_percent)} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Накопленный P/L ML-бота">
          <PnlLineChart data={safeArray(charts.bot_pnl_timeline)} />
        </Card>
        <Card title="Статусы ML-сделок">
          <SimplePieChart data={safeArray(charts.trade_status_distribution)} />
        </Card>
      </div>

      <Card title="Сравнение моделей по торговым результатам">
        {modelRows.length === 0 ? (
          <EmptyState>Сделок ML-бота пока нет.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase text-gray-500 dark:text-zinc-500">
                <tr className="border-b border-gray-200 dark:border-zinc-800">
                  <th className="px-3 py-3">Модель</th>
                  <th className="px-3 py-3 text-right">Всего</th>
                  <th className="px-3 py-3 text-right">Закрыто</th>
                  <th className="px-3 py-3 text-right">Открыто</th>
                  <th className="px-3 py-3 text-right">Failed</th>
                  <th className="px-3 py-3 text-right">P/L</th>
                  <th className="px-3 py-3 text-right">Win Rate</th>
                  <th className="px-3 py-3 text-right">Средн. %</th>
                </tr>
              </thead>
              <tbody>
                {modelRows.map(([model, values]) => (
                  <tr key={model} className="border-b border-gray-100 dark:border-zinc-800/70">
                    <td className="px-3 py-3 font-semibold text-gray-900 dark:text-white">{modelLabel(model)}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{values.total_trades || 0}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{values.closed_trades || 0}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{values.open_trades || 0}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{values.failed_trades || 0}</td>
                    <td className={`px-3 py-3 text-right font-semibold ${number(values.realized_pnl) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{formatMoney(values.realized_pnl)} ₽</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatPercent(values.win_rate, false)}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatPercent(values.avg_trade_return_percent)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="История ML-бота">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase text-gray-500 dark:text-zinc-500">
              <tr className="border-b border-gray-200 dark:border-zinc-800">
                <th className="px-3 py-3">Дата</th>
                <th className="px-3 py-3">Актив</th>
                <th className="px-3 py-3">Модель</th>
                <th className="px-3 py-3">Горизонт</th>
                <th className="px-3 py-3">Действие</th>
                <th className="px-3 py-3">Статус</th>
                <th className="px-3 py-3 text-right">Прогноз %</th>
                <th className="px-3 py-3 text-right">Сумма</th>
                <th className="px-3 py-3 text-right">P/L</th>
                <th className="px-3 py-3 text-right">P/L %</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <TableLoader colSpan={10} label="Загружаем сделки ML-бота..." />
              ) : botHistory.length === 0 ? (
                <tr><td colSpan="10" className="px-3 py-8 text-center text-gray-500">Сделок ML-бота пока нет</td></tr>
              ) : botHistory.map((item) => {
                const model = item.model_type_used || item.model_type_requested || 'unknown';
                const pnl = number(item.realized_pnl);
                return (
                  <tr key={item.id} className="border-b border-gray-100 dark:border-zinc-800/70">
                    <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{formatDate(item.created_at)}</td>
                    <td className="px-3 py-3 font-semibold text-gray-900 dark:text-white">{item.ticker || item.figi}</td>
                    <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{modelLabel(model)}</td>
                    <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{HORIZON_LABELS[item.horizon] || item.horizon || '—'}</td>
                    <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{item.side}</td>
                    <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{item.status}</td>
                    <td className={`px-3 py-3 text-right font-semibold ${number(item.price_delta_percent) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{formatPercent(item.price_delta_percent)}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatMoney(item.amount)} ₽</td>
                    <td className={`px-3 py-3 text-right font-semibold ${pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{formatMoney(item.realized_pnl)} ₽</td>
                    <td className={`px-3 py-3 text-right font-semibold ${number(item.realized_pnl_percent) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{item.realized_pnl_percent === null || item.realized_pnl_percent === undefined ? '—' : formatPercent(item.realized_pnl_percent)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function ModelsTab({ overview, loading }) {
  const modelQuality = overview.model_quality;
  const charts = overview.charts;
  const rows = safeArray(modelQuality.rows);
  const forecasts = safeArray(modelQuality.recent_forecasts);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Всего прогнозов" value={formatCompact(modelQuality.total_forecasts)} hint="Сохраненные прогнозы моделей" />
        <StatCard label="SVR/GPR/Ensemble" value={safeArray(charts.model_forecast_counts).map((row) => `${modelLabel(row.model)}: ${row.count}`).join(' · ') || '—'} hint="Фактически выбранные модели" tone="blue" />
        <StatCard label="Горизонт 1h" value={formatCompact(modelQuality.horizon_distribution?.['1h'] || 0)} hint="Краткосрочные прогнозы" />
        <StatCard label="Горизонт 1d" value={formatCompact(modelQuality.horizon_distribution?.['1d'] || 0)} hint="Дневные прогнозы" />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Сколько раз adaptive выбрал модель">
          <SimpleBarChart data={safeArray(charts.model_forecast_counts).map((row) => ({ ...row, model: modelLabel(row.model) }))} xKey="model" bars={[{ key: 'count', name: 'Прогнозы' }]} />
        </Card>
        <Card title="Динамика прогнозируемого изменения">
          <div className="h-72">
            {safeArray(charts.forecast_timeline).length === 0 ? (
              <EmptyState>Нет прогнозов для графика.</EmptyState>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={safeArray(charts.forecast_timeline)} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line type="monotone" dataKey="delta" name="Прогноз %" stroke="#9333ea" strokeWidth={3} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>

      <Card title="Качество моделей по сохраненным прогнозам">
        {rows.length === 0 ? (
          <EmptyState>Пока нет сохраненных прогнозов. Сделай прогноз во вкладке ML-модели.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase text-gray-500 dark:text-zinc-500">
                <tr className="border-b border-gray-200 dark:border-zinc-800">
                  <th className="px-3 py-3">Факт. модель</th>
                  <th className="px-3 py-3">Горизонт</th>
                  <th className="px-3 py-3 text-right">Прогнозов</th>
                  <th className="px-3 py-3 text-right">MAE</th>
                  <th className="px-3 py-3 text-right">RMSE</th>
                  <th className="px-3 py-3 text-right">R²</th>
                  <th className="px-3 py-3 text-right">Train</th>
                  <th className="px-3 py-3 text-right">Средн. прогноз %</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.model}-${row.horizon}`} className="border-b border-gray-100 dark:border-zinc-800/70">
                    <td className="px-3 py-3 font-semibold text-gray-900 dark:text-white">{modelLabel(row.model)}</td>
                    <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{HORIZON_LABELS[row.horizon] || row.horizon}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{row.forecast_count}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatMetric(row.avg_mae)}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatMetric(row.avg_rmse)}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatMetric(row.avg_r2, 4)}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatCompact(row.avg_train_samples)}</td>
                    <td className={`px-3 py-3 text-right font-semibold ${number(row.avg_predicted_delta_percent) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{formatPercent(row.avg_predicted_delta_percent)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Последние прогнозы">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase text-gray-500 dark:text-zinc-500">
              <tr className="border-b border-gray-200 dark:border-zinc-800">
                <th className="px-3 py-3">Дата</th>
                <th className="px-3 py-3">Актив</th>
                <th className="px-3 py-3">Модель</th>
                <th className="px-3 py-3">Факт. модель</th>
                <th className="px-3 py-3">Горизонт</th>
                <th className="px-3 py-3 text-right">Текущая</th>
                <th className="px-3 py-3 text-right">Прогноз</th>
                <th className="px-3 py-3 text-right">Δ%</th>
                <th className="px-3 py-3">Рекомендация</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <TableLoader colSpan={9} label="Загружаем прогнозы моделей..." />
              ) : forecasts.length === 0 ? (
                <tr><td colSpan="9" className="px-3 py-8 text-center text-gray-500">Прогнозов пока нет</td></tr>
              ) : forecasts.map((item) => (
                <tr key={item.id} className="border-b border-gray-100 dark:border-zinc-800/70">
                  <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{formatDate(item.created_at)}</td>
                  <td className="px-3 py-3 font-semibold text-gray-900 dark:text-white">{item.ticker || item.figi}</td>
                  <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{modelLabel(item.model_type)}</td>
                  <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{modelLabel(item.model_type_effective || item.model_type)}</td>
                  <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{HORIZON_LABELS[item.horizon] || item.horizon}</td>
                  <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatMoney(item.current_price)} ₽</td>
                  <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatMoney(item.predicted_price)} ₽</td>
                  <td className={`px-3 py-3 text-right font-semibold ${number(item.price_delta_percent) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{formatPercent(item.price_delta_percent)}</td>
                  <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{RECOMMENDATION_LABELS[item.recommendation] || item.recommendation || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function BacktestTab({ overview }) {
  const backtests = overview.backtests;
  const recent = safeArray(backtests.recent);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Backtest-запусков" value={formatCompact(backtests.total_backtests)} hint="Сохраненные результаты" />
        <StatCard label="Лучшая доходность" value={formatPercent(number(backtests.best_return) * (Math.abs(number(backtests.best_return)) <= 1 ? 100 : 1), false)} hint="Лучший historical run" tone={toneByNumber(backtests.best_return)} />
        <StatCard label="Средняя доходность" value={formatPercent(number(backtests.avg_return) * (Math.abs(number(backtests.avg_return)) <= 1 ? 100 : 1), false)} hint="По всем backtest" tone={toneByNumber(backtests.avg_return)} />
        <StatCard label="Max Drawdown" value={formatPercent(number(backtests.worst_drawdown) * (Math.abs(number(backtests.worst_drawdown)) <= 1 ? 100 : 1), false)} hint="Худшая просадка" tone="negative" />
      </div>

      <Card title="Последние backtest-результаты">
        {recent.length === 0 ? (
          <EmptyState>Сохраненных backtest-запусков нет. Сейчас раздел показывает готовую структуру для оценки стратегий, но реальные сравнения появятся после запуска backtest.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase text-gray-500 dark:text-zinc-500">
                <tr className="border-b border-gray-200 dark:border-zinc-800">
                  <th className="px-3 py-3">Дата</th>
                  <th className="px-3 py-3">Название</th>
                  <th className="px-3 py-3">Инструменты</th>
                  <th className="px-3 py-3 text-right">Начальный баланс</th>
                  <th className="px-3 py-3 text-right">Финальный баланс</th>
                  <th className="px-3 py-3 text-right">Доходность</th>
                  <th className="px-3 py-3 text-right">Сделок</th>
                  <th className="px-3 py-3 text-right">Win Rate</th>
                  <th className="px-3 py-3 text-right">Sharpe</th>
                  <th className="px-3 py-3 text-right">Max DD</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((item) => (
                  <tr key={item.id} className="border-b border-gray-100 dark:border-zinc-800/70">
                    <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{formatDate(item.created_at)}</td>
                    <td className="px-3 py-3 font-semibold text-gray-900 dark:text-white">{item.name}</td>
                    <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{safeArray(item.stock_symbols).join(', ') || '—'}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatMoney(item.initial_balance)}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatMoney(item.final_balance)}</td>
                    <td className={`px-3 py-3 text-right font-semibold ${number(item.total_return) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{formatPercent(item.total_return)}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{item.total_trades}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatPercent(item.win_rate, false)}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatMetric(item.sharpe_ratio, 4)}</td>
                    <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatPercent(item.max_drawdown, false)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function ManualTradesTab({ overview, loading }) {
  const manual = overview.manual_trades;
  const rows = safeArray(manual.recent);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Ручных сделок" value={formatCompact(manual.total_trades)} hint="По выбранному периоду" />
        <StatCard label="Покупки / продажи" value={`${manual.buy_trades || 0} / ${manual.sell_trades || 0}`} hint="Количество заявок" />
        <StatCard label="Куплено" value={`${formatMoney(manual.buy_amount)} ₽`} hint="Суммарный BUY" tone="blue" />
        <StatCard label="Продано" value={`${formatMoney(manual.sell_amount)} ₽`} hint="Суммарный SELL" tone="amber" />
        <StatCard label="Реализованный P/L" value={`${number(manual.realized_pnl) >= 0 ? '+' : ''}${formatMoney(manual.realized_pnl)} ₽`} hint={formatPercent(manual.avg_realized_pnl_percent)} tone={toneByNumber(manual.realized_pnl)} />
      </div>

      <Card title="Последние ручные сделки">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase text-gray-500 dark:text-zinc-500">
              <tr className="border-b border-gray-200 dark:border-zinc-800">
                <th className="px-3 py-3">Дата</th>
                <th className="px-3 py-3">FIGI</th>
                <th className="px-3 py-3">Сторона</th>
                <th className="px-3 py-3">Статус</th>
                <th className="px-3 py-3 text-right">Кол-во</th>
                <th className="px-3 py-3 text-right">Цена</th>
                <th className="px-3 py-3 text-right">Сумма</th>
                <th className="px-3 py-3 text-right">P/L</th>
                <th className="px-3 py-3 text-right">P/L %</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <TableLoader colSpan={9} label="Загружаем ручные сделки..." />
              ) : rows.length === 0 ? (
                <tr><td colSpan="9" className="px-3 py-8 text-center text-gray-500">Ручных сделок пока нет</td></tr>
              ) : rows.map((item) => (
                <tr key={item.id} className="border-b border-gray-100 dark:border-zinc-800/70">
                  <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{formatDate(item.created_at)}</td>
                  <td className="px-3 py-3 font-semibold text-gray-900 dark:text-white">{item.figi}</td>
                  <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{item.side}</td>
                  <td className="px-3 py-3 text-gray-700 dark:text-zinc-300">{item.status}</td>
                  <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{item.quantity}</td>
                  <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatMoney(item.price)} ₽</td>
                  <td className="px-3 py-3 text-right text-gray-700 dark:text-zinc-300">{formatMoney(item.amount)} ₽</td>
                  <td className={`px-3 py-3 text-right font-semibold ${number(item.realized_pnl) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{formatMoney(item.realized_pnl)} ₽</td>
                  <td className={`px-3 py-3 text-right font-semibold ${number(item.realized_pnl_percent) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{formatPercent(item.realized_pnl_percent)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function RisksTab({ overview }) {
  const risks = safeArray(overview.risk_warnings);
  const positions = safeArray(overview.portfolio.positions)
    .map((position) => ({
      name: position.ticker || position.figi,
      value: number(position.value),
    }))
    .filter((item) => item.value > 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Предупреждения">
          <div className="space-y-3">
            {risks.length === 0 ? (
              <EmptyState />
            ) : risks.map((warning, index) => (
              <div key={`${warning.title}-${index}`} className="rounded-2xl border border-gray-100 bg-gray-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div>
                    <div className="font-semibold text-gray-900 dark:text-white">{warning.title}</div>
                    <div className="text-sm text-gray-500 dark:text-zinc-300">{warning.message}</div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <RiskBadge severity={warning.severity} />
                    <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">{warning.metric}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Концентрация портфеля">
          <SimplePieChart data={positions} />
        </Card>
      </div>
    </div>
  );
}

export default function Analytics() {
  const [overview, setOverview] = useState(EMPTY_OVERVIEW);
  const [filters, setFilters] = useState({ period: '30', model_type: '', horizon: '', figi: '' });
  const [activeTab, setActiveTab] = useState('overview');
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [accountsLoaded, setAccountsLoaded] = useState(false);
  const [accountError, setAccountError] = useState('');

  const loadAccounts = useCallback(async () => {
    try {
      setAccountsLoading(true);
      setAccountError('');
      const response = await tradeAPI.getAccounts();
      const openAccounts = safeArray(response.data?.accounts)
        .map((account) => ({ ...account, status: normalizeAccountStatus(account?.status) }))
        .filter(isOpenAccount)
        .sort(latestAccountFirst);

      setAccounts(openAccounts);
      setSelectedAccountId((currentAccountId) => {
        const storedAccountId = getStoredAccountId();
        const preferredAccount = openAccounts.find((account) => account.id === currentAccountId)
          || openAccounts.find((account) => account.id === storedAccountId)
          || openAccounts[0];
        const nextAccountId = preferredAccount?.id || '';
        storeAccountId(nextAccountId);
        return nextAccountId;
      });
    } catch (requestError) {
      setAccounts([]);
      setSelectedAccountId('');
      storeAccountId('');
      setAccountError(getErrorMessage(requestError, 'Не удалось загрузить счета для аналитики.'));
    } finally {
      setAccountsLoading(false);
      setAccountsLoaded(true);
    }
  }, []);

  const handleAccountChange = useCallback((accountId) => {
    setSelectedAccountId(accountId);
    storeAccountId(accountId);
  }, []);

  const requestParams = useMemo(() => {
    const params = {};
    const dateFrom = buildDateFrom(filters.period);
    if (dateFrom) params.date_from = dateFrom;
    if (filters.model_type) params.model_type = filters.model_type;
    if (filters.horizon) params.horizon = filters.horizon;
    if (filters.figi.trim()) params.figi = filters.figi.trim().toUpperCase();
    if (selectedAccountId) params.account_id = selectedAccountId;
    return params;
  }, [filters, selectedAccountId]);

  const loadOverview = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const response = await analyticsAPI.getOverview(requestParams);
      setOverview(normalizeOverview(response.data));
    } catch (requestError) {
      setError(getErrorMessage(requestError, 'Не удалось загрузить аналитику ML-торговой системы. Повторите попытку позже.'));
      setOverview(EMPTY_OVERVIEW);
    } finally {
      setLoading(false);
    }
  }, [requestParams]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  useEffect(() => {
    if (accountsLoaded) {
      loadOverview();
    }
  }, [accountsLoaded, loadOverview]);

  const tabContent = {
    overview: <OverviewTab overview={overview} />,
    bot: <BotTab overview={overview} loading={loading} />,
    models: <ModelsTab overview={overview} loading={loading} />,
    backtest: <BacktestTab overview={overview} />,
    manual: <ManualTradesTab overview={overview} loading={loading} />,
    risks: <RisksTab overview={overview} />,
  };

  return (
    <div className="analytics-page space-y-5">
      <MetricStrip overview={overview} />
      <Filters
        filters={filters}
        onChange={setFilters}
        onRefresh={loadOverview}
        loading={loading}
        accounts={accounts}
        selectedAccountId={selectedAccountId}
        onAccountChange={handleAccountChange}
        accountsLoading={accountsLoading}
      />

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
          {error}
        </div>
      )}

      {accountError && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          {accountError}
        </div>
      )}

      {overview.portfolio_error && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          Портфель сейчас недоступен: {normalizeUserMessage(overview.portfolio_error, 'Не удалось загрузить портфель. Повторите попытку позже.')}
        </div>
      )}

      {safeArray(overview.analytics_errors).length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          Аналитика загружена частично: {safeArray(overview.analytics_errors).join('; ')}. Остальные блоки остаются доступными.
        </div>
      )}

      {loading && <LoadingSpinner label="Загружаем актуальные показатели..." compact />}

      <AnalyticsEssentials overview={overview} />

      <section className="rounded-3xl border border-gray-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-[#111111]">
        <button
          type="button"
          onClick={() => setDetailsOpen((value) => !value)}
          className="flex w-full items-center justify-between px-5 py-4 text-left text-sm font-semibold text-gray-800 hover:bg-gray-50 dark:text-white dark:hover:bg-zinc-900"
        >
          <span>Подробная аналитика</span>
          <span className="text-xs text-gray-500 dark:text-zinc-500">{detailsOpen ? 'Скрыть' : 'Показать'}</span>
        </button>

        {detailsOpen && (
          <div className="space-y-5 border-t border-gray-200 p-5 dark:border-zinc-800">
            <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white p-2 shadow-sm dark:border-zinc-800 dark:bg-[#111111]">
              <div className="flex min-w-max gap-2">
                {TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                      activeTab === tab.id
                        ? 'bg-yellow-400 text-black shadow dark:bg-yellow-400 dark:text-black'
                        : 'text-gray-600 hover:bg-gray-100 dark:text-zinc-300 dark:hover:bg-gray-700'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {tabContent[activeTab]}
          </div>
        )}
      </section>
    </div>
  );
}
