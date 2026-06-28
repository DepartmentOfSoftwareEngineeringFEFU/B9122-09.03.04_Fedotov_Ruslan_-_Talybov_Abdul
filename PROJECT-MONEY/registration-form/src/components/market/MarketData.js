// src/components/market/MarketData.js
import React, { useEffect, useRef, useState } from 'react';
import { marketAPI, getErrorMessage } from '../../services/api';
import { FALLBACK_MOEX_SHARES, normalizeInstrumentList } from '../../utils/instruments';
import InteractiveMarketChart from './InteractiveMarketChart';
import { ButtonLoader } from '../common/LoadingSpinner';

const PERIODS = [
  { days: 1, label: '1Д' },
  { days: 7, label: '7Д' },
  { days: 30, label: '30Д' },
];

const CHART_TYPES = [
  { type: 'candlestick', label: 'Свечи' },
  { type: 'line', label: 'Линия' },
  { type: 'area', label: 'Область' },
];

const getIntervalForPeriod = (days) => {
  if (days >= 30) return 'day';
  if (days >= 7) return 'hour';
  return '5min';
};

const formatMoney = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return `${number.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;
};

const normalizeCandles = (candles) => candles
  .map((candle) => {
    const time = candle.x || candle.time;
    const open = Number(candle.o ?? candle.open);
    const rawHigh = Number(candle.h ?? candle.high);
    const rawLow = Number(candle.l ?? candle.low);
    const close = Number(candle.c ?? candle.close);
    const high = Math.max(open, rawHigh, rawLow, close);
    const low = Math.min(open, rawHigh, rawLow, close);
    const volume = Number(candle.v ?? candle.volume ?? 0);

    const timestamp = new Date(time);
    const safeTimestamp = Number.isNaN(timestamp.getTime()) ? new Date() : timestamp;
    const dateStr = safeTimestamp.toLocaleDateString('ru-RU');
    const timeStr = safeTimestamp.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    const change = open ? ((close - open) / open) * 100 : 0;

    return {
      timestamp: safeTimestamp,
      time: timeStr,
      date: dateStr,
      datetime: `${dateStr} ${timeStr}`,
      open,
      high,
      low,
      close,
      volume,
      change: Number.isFinite(change) ? change : 0,
    };
  })
  .filter((candle) => (
    Number.isFinite(candle.open) &&
    Number.isFinite(candle.high) &&
    Number.isFinite(candle.low) &&
    Number.isFinite(candle.close)
  ))
  .sort((a, b) => a.timestamp - b.timestamp);

const getCandlesFromResponse = (response) => {
  if (response?.data?.status === 'ok' && Array.isArray(response.data.candles)) {
    return response.data.candles;
  }

  if (Array.isArray(response?.data)) {
    return response.data;
  }

  return null;
};

const keepLastTradingSession = (candles) => {
  if (!candles.length) return candles;
  const lastDate = candles[candles.length - 1].date;
  return candles.filter((candle) => candle.date === lastDate);
};

const buildFallbackCandles = (symbol = 'SBER') => {
  const basePriceBySymbol = {
    SBER: 322,
    GAZP: 135,
    LKOH: 6800,
    YNDX: 4100,
    VTBR: 0.012,
    ROSN: 560,
    ALRS: 72,
    MGNT: 5200,
    TATN: 650,
    MOEX: 210,
  };
  const basePrice = basePriceBySymbol[symbol] || 300;
  const now = Date.now();

  return Array.from({ length: 80 }, (_item, index) => {
    const timestamp = new Date(now - (79 - index) * 60 * 60 * 1000);
    const wave = Math.sin(index / 5) * basePrice * 0.012;
    const trend = (index - 40) * basePrice * 0.00045;
    const close = basePrice + wave + trend;
    const open = close - Math.cos(index / 4) * basePrice * 0.004;
    const high = Math.max(open, close) + basePrice * (0.004 + (index % 5) * 0.0006);
    const low = Math.min(open, close) - basePrice * (0.004 + (index % 3) * 0.0007);
    const dateStr = timestamp.toLocaleDateString('ru-RU');
    const timeStr = timestamp.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    const change = open ? ((close - open) / open) * 100 : 0;

    return {
      timestamp,
      time: timeStr,
      date: dateStr,
      datetime: `${dateStr} ${timeStr}`,
      open,
      high,
      low,
      close,
      volume: 50000 + index * 1200,
      change: Number.isFinite(change) ? change : 0,
      fallback: true,
    };
  });
};

const getSymbolForFigi = (figi, instruments = FALLBACK_MOEX_SHARES) => (
  instruments.find((instrument) => instrument.figi === figi)?.symbol ||
  FALLBACK_MOEX_SHARES.find((instrument) => instrument.figi === figi)?.symbol ||
  'SBER'
);

export default function MarketData() {
  const [marketData, setMarketData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [instruments, setInstruments] = useState(() => FALLBACK_MOEX_SHARES);
  const [figi, setFigi] = useState('BBG004730N88');
  const [periodDays, setPeriodDays] = useState(1);
  const [error, setError] = useState(null);
  const [chartType, setChartType] = useState('candlestick');
  const [searchQuery, setSearchQuery] = useState('SBER - Сбербанк');
  const [showDropdown, setShowDropdown] = useState(false);
  const instrumentPickerRef = useRef(null);

  const selectedInstrument = instruments.find((instrument) => instrument.figi === figi) ||
    FALLBACK_MOEX_SHARES.find((instrument) => instrument.figi === figi);
  const selectedInstrumentLabel = selectedInstrument
    ? `${selectedInstrument.symbol} - ${selectedInstrument.name}`
    : '';
  const isFiltering = Boolean(searchQuery.trim()) && searchQuery !== selectedInstrumentLabel;
  const filteredInstruments = isFiltering
    ? instruments.filter((instrument) => {
      const query = searchQuery.trim().toLowerCase();
      return instrument.symbol.toLowerCase().includes(query) ||
        instrument.name.toLowerCase().includes(query) ||
        instrument.figi.toLowerCase().includes(query);
    })
    : instruments;
  const chartSymbol = selectedInstrument?.symbol || searchQuery.split(' - ')[0] || figi;

  useEffect(() => {
    let cancelled = false;

    const loadInstruments = async () => {
      try {
        const response = await marketAPI.getShares(1000);
        const loadedInstruments = normalizeInstrumentList(response?.data?.items || []);
        if (!cancelled && loadedInstruments.length > 0) {
          setInstruments(loadedInstruments);
        }
      } catch (instrumentError) {
        console.error('Ошибка загрузки списка инструментов:', instrumentError);
      }
    };

    loadInstruments();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (instrumentPickerRef.current && !instrumentPickerRef.current.contains(event.target)) {
        setShowDropdown(false);
        if (selectedInstrumentLabel) {
          setSearchQuery(selectedInstrumentLabel);
        }
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [selectedInstrumentLabel]);

  useEffect(() => {
    if (!showDropdown && selectedInstrumentLabel && searchQuery !== selectedInstrumentLabel) {
      setSearchQuery(selectedInstrumentLabel);
    }
  }, [searchQuery, selectedInstrumentLabel, showDropdown]);

  useEffect(() => {
    loadMarketData('BBG004730N88', 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadMarketData = async (selectedFigi = null, selectedDays = null) => {
    const figiToLoad = selectedFigi || figi;
    const daysToLoad = selectedDays || periodDays;
    const fallbackSymbol = getSymbolForFigi(figiToLoad, instruments);

    if (!figiToLoad.trim()) {
      setError('Введите тикер или выберите инструмент из списка.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const interval = getIntervalForPeriod(daysToLoad);
      const response = await marketAPI.loadCandles(figiToLoad.trim(), daysToLoad, interval);
      let candles = getCandlesFromResponse(response);

      if (!candles) {
        setError('Сервер вернул данные в неожиданном формате. Обновите страницу или повторите позже.');
        setMarketData(buildFallbackCandles(fallbackSymbol));
        return;
      }

      let processedData = normalizeCandles(candles);

      if (!processedData.length && daysToLoad === 1) {
        const fallbackResponse = await marketAPI.loadCandles(figiToLoad.trim(), 7, 'hour');
        candles = getCandlesFromResponse(fallbackResponse) || [];
        processedData = keepLastTradingSession(normalizeCandles(candles));
      }

      if (!processedData.length) {
        setError('По этому инструменту сейчас нет свечей. Выберите другой инструмент или более длинный период.');
        setMarketData(buildFallbackCandles(fallbackSymbol));
        return;
      }

      setMarketData(processedData);
    } catch (requestError) {
      setError(`${getErrorMessage(requestError, 'Не удалось загрузить рыночные данные. Проверьте инструмент или повторите позже.')} Пока показан локальный резервный график.`);
      setMarketData(buildFallbackCandles(fallbackSymbol));
    } finally {
      setLoading(false);
    }
  };

  const handleInstrumentSelect = (instrument) => {
    setFigi(instrument.figi);
    setSearchQuery(`${instrument.symbol} - ${instrument.name}`);
    setShowDropdown(false);
    setError(null);
    loadMarketData(instrument.figi, periodDays);
  };

  const handleSearchChange = (event) => {
    const value = event.target.value;
    setSearchQuery(value);
    setShowDropdown(true);
  };

  const handleInputFocus = () => {
    setShowDropdown(true);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      setShowDropdown(false);
      if (selectedInstrumentLabel) {
        setSearchQuery(selectedInstrumentLabel);
      }
      return;
    }

    if (event.key !== 'Enter') return;

    setShowDropdown(false);
    if (isFiltering && filteredInstruments.length > 0) {
      handleInstrumentSelect(filteredInstruments[0]);
    } else if (figi) {
      loadMarketData();
    }
  };

  const handlePeriodChange = (days) => {
    setPeriodDays(days);
    loadMarketData(figi, days);
  };

  const getStats = () => {
    if (!marketData?.length) return null;

    const closes = marketData.map((item) => item.close);
    const volumes = marketData.map((item) => item.volume);
    const first = marketData[0];
    const last = marketData[marketData.length - 1];
    const totalChange = first.close ? ((last.close - first.close) / first.close) * 100 : 0;

    return {
      count: marketData.length,
      currentPrice: last.close,
      minPrice: Math.min(...closes),
      maxPrice: Math.max(...closes),
      avgVolume: volumes.reduce((a, b) => a + b, 0) / volumes.length,
      totalChange,
    };
  };

  const stats = getStats();

  return (
    <div className="space-y-5">
      <div className="app-card border border-[rgba(250,204,21,0.13)] p-5">
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(360px,1fr)_auto_auto] xl:items-start">
          <div className="min-w-0 flex-1">
            <label htmlFor="market-instrument-input" className="mb-2 block text-sm font-medium text-zinc-300">
              Инструмент
            </label>
            <div ref={instrumentPickerRef} className="relative">
              <input
                id="market-instrument-input"
                type="text"
                value={searchQuery}
                onChange={handleSearchChange}
                onFocus={handleInputFocus}
                onKeyDown={handleKeyDown}
                placeholder="Тикер, название или FIGI"
                className="app-input h-12 w-full px-4 pr-11 outline-none"
                role="combobox"
                aria-autocomplete="list"
                aria-controls="market-instrument-listbox"
                aria-expanded={showDropdown}
              />
              <span
                aria-hidden="true"
                className={`pointer-events-none absolute right-4 top-1/2 h-2 w-2 -translate-y-1/2 border-b border-r border-zinc-500 transition-transform ${
                  showDropdown ? 'rotate-[225deg]' : 'rotate-45'
                }`}
              />

              {showDropdown && (
                <div
                  id="market-instrument-listbox"
                  role="listbox"
                  className="absolute z-50 mt-2 max-h-80 w-full overflow-auto border border-[rgba(250,204,21,0.18)] bg-[#111111] shadow-2xl"
                >
                  {filteredInstruments.length > 0 ? (
                    filteredInstruments.map((instrument) => (
                      <button
                        key={instrument.figi}
                        type="button"
                        role="option"
                        aria-selected={figi === instrument.figi}
                        className={`flex w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors ${
                          figi === instrument.figi
                            ? 'bg-yellow-400 text-black'
                            : 'text-zinc-100 hover:bg-[#211d13]'
                        }`}
                        onClick={() => handleInstrumentSelect(instrument)}
                      >
                        <span className="min-w-0">
                          <span className="block font-semibold">{instrument.symbol}</span>
                          <span className={`block truncate text-sm ${figi === instrument.figi ? 'text-black/70' : 'text-zinc-500'}`}>
                            {instrument.name}
                          </span>
                        </span>
                        <span className={`shrink-0 font-mono text-xs ${figi === instrument.figi ? 'text-black/65' : 'text-zinc-600'}`}>
                          {instrument.figi}
                        </span>
                      </button>
                    ))
                  ) : (
                    <div className="px-4 py-3 text-sm text-zinc-500">
                      Ничего не найдено
                    </div>
                  )}
                </div>
              )}
            </div>
            {figi && (
              <div className="mt-2 text-xs text-zinc-600">
                FIGI: <span className="font-mono text-zinc-500">{figi}</span>
              </div>
            )}
          </div>

          <div>
            <div className="mb-2 text-sm font-medium text-zinc-300">Период</div>
            <div className="flex flex-wrap gap-2">
              {PERIODS.map(({ days, label }) => (
                <button
                  key={days}
                  type="button"
                  onClick={() => handlePeriodChange(days)}
                  className={`h-12 min-w-14 border px-4 text-sm font-semibold ${
                    periodDays === days
                      ? 'border-yellow-400 bg-yellow-400 text-black'
                      : 'border-zinc-800 bg-[#14130f] text-zinc-300 hover:border-yellow-400 hover:text-yellow-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div aria-hidden="true" className="mb-2 hidden h-5 xl:block" />
            <button
              type="button"
              onClick={() => loadMarketData()}
              disabled={loading}
              className="app-primary-button inline-flex h-12 min-w-40 items-center justify-center px-6 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? <ButtonLoader label="Загружаем..." dark /> : 'Загрузить'}
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 border border-red-500/35 bg-red-950/55 px-4 py-3 text-sm text-red-100">
            {error}
          </div>
        )}
      </div>

      <div className="app-card border border-[rgba(250,204,21,0.13)] p-5">
        <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 className="text-xl font-semibold text-white">График {chartSymbol}</h3>
          </div>

          <div className="flex flex-wrap gap-2">
            {CHART_TYPES.map(({ type, label }) => (
              <button
                key={type}
                type="button"
                onClick={() => setChartType(type)}
                className={`h-10 border px-4 text-sm font-semibold ${
                  chartType === type
                    ? 'border-yellow-400 bg-yellow-400 text-black'
                    : 'border-zinc-800 bg-[#14130f] text-zinc-300 hover:border-yellow-400 hover:text-yellow-300'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <InteractiveMarketChart data={marketData || []} chartType={chartType} symbol={chartSymbol} />

        {stats && (
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
            <div className="app-muted-card p-3">
              <div className="text-xs text-zinc-500">Свечи</div>
              <div className="mt-1 text-lg font-semibold text-white">{stats.count}</div>
            </div>
            <div className="app-muted-card p-3">
              <div className="text-xs text-zinc-500">Текущая цена</div>
              <div className="mt-1 text-lg font-semibold text-white">{formatMoney(stats.currentPrice)}</div>
            </div>
            <div className="app-muted-card p-3">
              <div className="text-xs text-zinc-500">Изменение</div>
              <div className={`mt-1 text-lg font-semibold ${stats.totalChange >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {stats.totalChange >= 0 ? '+' : ''}{stats.totalChange.toFixed(2)}%
              </div>
            </div>
            <div className="app-muted-card p-3">
              <div className="text-xs text-zinc-500">Минимум</div>
              <div className="mt-1 text-lg font-semibold text-white">{formatMoney(stats.minPrice)}</div>
            </div>
            <div className="app-muted-card p-3">
              <div className="text-xs text-zinc-500">Максимум</div>
              <div className="mt-1 text-lg font-semibold text-white">{formatMoney(stats.maxPrice)}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
