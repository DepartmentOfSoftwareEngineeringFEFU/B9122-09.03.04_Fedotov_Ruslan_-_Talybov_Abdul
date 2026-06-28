// src/components/trading/Trading.js
import React, { useState, useEffect, useRef } from 'react';
import { tradeAPI, marketAPI, getErrorMessage } from '../../services/api';
import { FALLBACK_MOEX_SHARES, normalizeInstrumentList } from '../../utils/instruments';
import { clampNumber, sanitizeNumberInput } from '../../utils/numberInput';
import { ButtonLoader } from '../common/LoadingSpinner';

const SELECTED_ACCOUNT_STORAGE_KEY = 'trade.selected_account_id';

const createIdempotencyKey = (prefix) => {
  if (window.crypto?.randomUUID) {
    return `${prefix}:${window.crypto.randomUUID()}`;
  }
  return `${prefix}:${Date.now()}:${Math.random().toString(16).slice(2)}`;
};

const getStoredAccountId = () => {
  try {
    return window.localStorage.getItem(SELECTED_ACCOUNT_STORAGE_KEY) || '';
  } catch (_error) {
    return '';
  }
};


const isProblemMessage = (message) => {
  const normalized = String(message || '').toLowerCase();
  return ['ошибка', 'не удалось', 'пожалуйста', 'нельзя', 'закрыт', 'закрыта', 'проверьте', 'недостаточно', 'недоступен', 'укажите', 'выберите'].some((marker) => normalized.includes(marker));
};

export default function Trading() {
  const [orderType, setOrderType] = useState('buy');
  const [figi, setFigi] = useState('');
  const [quantity, setQuantity] = useState('');
  const [currentPrice, setCurrentPrice] = useState(null);
  const [currentLot, setCurrentLot] = useState(1);
  const [currentLotPrice, setCurrentLotPrice] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [shareOptions, setShareOptions] = useState(() => FALLBACK_MOEX_SHARES);
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);

  // Фильтрация инструментов по поисковому запросу
  const filteredInstruments = shareOptions.filter(instrument =>
    instrument.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
    instrument.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    instrument.figi.toLowerCase().includes(searchQuery.toLowerCase())
  );

  useEffect(() => {
    let cancelled = false;

    const loadShareOptions = async () => {
      try {
        const response = await marketAPI.getShares(1000);
        const loadedShares = normalizeInstrumentList(response?.data?.items || []);
        if (!cancelled && loadedShares.length > 0) {
          setShareOptions(loadedShares);
        }
      } catch (error) {
        console.error('Ошибка загрузки списка акций:', error);
      }
    };

    loadShareOptions();
    return () => {
      cancelled = true;
    };
  }, []);

  // Автозакрытие dropdown при клике вне его
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target) &&
          inputRef.current && !inputRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleInstrumentSelect = (instrument) => {
    setFigi(instrument.figi);
    setSearchQuery(`${instrument.symbol} - ${instrument.name}`);
    setShowDropdown(false);
    setCurrentPrice(null);
    setCurrentLot(1);
    setCurrentLotPrice(null);
    setMessage('');
  };

  const handleSearchChange = (e) => {
    const value = e.target.value;
    setSearchQuery(value);
    setFigi(value); // Позволяет вводить FIGI вручную
    
    if (value.length > 0) {
      setShowDropdown(true);
    } else {
      setShowDropdown(false);
    }
  };

  const handleInputFocus = () => {
    if (searchQuery.length > 0 || filteredInstruments.length > 0) {
      setShowDropdown(true);
    }
  };

  const handleSubmitOrder = async (e) => {
    e.preventDefault();

    if (!figi) {
      setMessage('Пожалуйста, выберите или введите FIGI');
      return;
    }

    const safeQuantity = clampNumber(quantity, { min: 1, max: 1000000, integer: true });
    if (!quantity || safeQuantity <= 0) {
      setMessage('Пожалуйста, укажите корректное количество');
      return;
    }

    setLoading(true);
    setMessage('');

    try {
      const orderData = {
        figi,
        side: orderType.toLowerCase(),
        qty: safeQuantity,
        idempotency_key: createIdempotencyKey('manual-order'),
      };
      const accountId = getStoredAccountId();
      if (accountId) {
        orderData.account_id = accountId;
      }


      await tradeAPI.executeOrder(orderData);

      setMessage(`Ордер успешно исполнен! ${orderType === 'buy' ? 'Покупка' : 'Продажа'} ${quantity} лотов`);

      setQuantity('');
      setFigi('');
      setSearchQuery('');
      setCurrentPrice(null);
      setCurrentLot(1);
      setCurrentLotPrice(null);

    } catch (error) {
      console.error('Ошибка исполнения ордера:', error);
      setMessage(getErrorMessage(error, 'Не удалось выполнить сделку. Проверьте инструмент, количество и режим торговли.'));
    } finally {
      setLoading(false);
    }
  };

  const handleLoadPrice = async () => {
    if (!figi) {
      setMessage('Пожалуйста, выберите инструмент');
      return;
    }
    try {
      const response = await marketAPI.getCurrentPrice(figi);
      if (response.data && response.data.current_price != null) {
        setCurrentPrice(response.data.current_price);
        setCurrentLot(response.data.lot || 1);
        setCurrentLotPrice(response.data.lot_price || response.data.current_price);
        setMessage(`Текущая цена: ${response.data.current_price.toLocaleString('ru-RU')} ₽ за акцию, лот ${response.data.lot || 1} шт.`);
      } else {
        setMessage('Не удалось получить цену');
      }
    } catch (error) {
      console.error('Ошибка загрузки цены:', error);
      setMessage(getErrorMessage(error, 'Не удалось получить текущую цену. Проверьте инструмент или повторите позже.'));
    }
  };

  return (
    <div className="space-y-6">
      {message && (
        <div className={`p-4 rounded-2xl ${
          isProblemMessage(message)
            ? 'bg-red-100 border border-red-300 text-red-700 dark:bg-red-900/40 dark:border-red-500/35 dark:text-red-200'
            : 'bg-green-100 border border-green-300 text-green-700 dark:bg-green-500/10 dark:border-green-500/25 dark:text-green-200'
        }`}>
          {message}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="app-card rounded-3xl p-6">
          <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">Новая сделка</h3>
          <form onSubmit={handleSubmitOrder} className="space-y-4">
            <div className="flex rounded-2xl border border-yellow-400/10 bg-[#11100d] p-1">
              <button
                type="button"
                onClick={() => setOrderType('buy')}
                className={`flex-1 border py-3 px-4 rounded-2xl text-sm font-semibold transition-all duration-300 ${
                  orderType === 'buy'
                    ? 'border-emerald-400/35 bg-emerald-400/10 text-emerald-300 shadow-[0_0_18px_rgba(52,211,153,0.08)]'
                    : 'border-transparent text-gray-600 dark:text-zinc-500 hover:border-emerald-400/20 hover:text-emerald-200'
                }`}
              >
                Покупка
              </button>
              <button
                type="button"
                onClick={() => setOrderType('sell')}
                className={`flex-1 border py-3 px-4 rounded-2xl text-sm font-semibold transition-all duration-300 ${
                  orderType === 'sell'
                    ? 'border-red-400/35 bg-red-400/10 text-red-300 shadow-[0_0_18px_rgba(248,113,113,0.08)]'
                    : 'border-transparent text-gray-600 dark:text-zinc-500 hover:border-red-400/20 hover:text-red-200'
                }`}
              >
                Продажа
              </button>
            </div>

            <div className="relative">
              <label className="block text-sm font-medium text-gray-700 dark:text-zinc-300 mb-2">
                Инструмент
              </label>
              <input
                ref={inputRef}
                type="text"
                value={searchQuery}
                onChange={handleSearchChange}
                onFocus={handleInputFocus}
                maxLength={80}
                placeholder="Начните вводить тикер или название..."
                className="app-input w-full rounded-2xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-yellow-400/60"
                disabled={loading}
              />
              
              {/* Выпадающий список */}
              {showDropdown && filteredInstruments.length > 0 && (
                <div 
                  ref={dropdownRef}
                  className="app-muted-card absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-2xl shadow-lg"
                >
                  {filteredInstruments.map((instrument) => (
                    <div
                      key={instrument.figi}
                      className={`cursor-pointer px-4 py-3 transition-colors duration-200 hover:bg-[#211d13] ${figi === instrument.figi ? 'bg-yellow-400 text-black' : 'text-white'}`}
                      onClick={() => handleInstrumentSelect(instrument)}
                    >
                      <div className="flex justify-between items-center">
                        <div>
                          <div className="font-semibold">{instrument.symbol}</div>
                          <div className="text-sm opacity-70">{instrument.name}</div>
                        </div>
                        <div className="rounded border border-yellow-400/10 bg-black/25 px-2 py-1 text-xs text-zinc-400">
                          {instrument.figi}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Отображение выбранного FIGI */}
              {figi && (
                <div className="mt-2 text-sm text-gray-600 dark:text-zinc-500">
                  Выбран FIGI: <span className="font-mono">{figi}</span>
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-zinc-300 mb-2">
                Количество лотов
              </label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(sanitizeNumberInput(e.target.value, { min: 1, max: 1000000, integer: true, maxLength: 7 }))}
                placeholder="0"
                min="1"
                max="1000000"
                className="app-input w-full rounded-2xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-yellow-400/60"
                disabled={loading}
              />
            </div>

            <button
              type="button"
              onClick={handleLoadPrice}
              disabled={!figi || loading}
              className={`w-full py-2 rounded-2xl font-semibold transition-all duration-300 ${
                !figi || loading
                  ? 'cursor-not-allowed border border-zinc-800 bg-zinc-900 text-zinc-600'
                  : 'app-secondary-button'
              }`}
            >
              Показать текущую цену
            </button>

            {currentPrice && (
              <div className="app-muted-card rounded-2xl p-4">
                <div className="mb-2 text-xs text-gray-500 dark:text-zinc-500">
                  1 лот = {currentLot} шт. • Цена лота: {(currentLotPrice || currentPrice).toLocaleString('ru-RU', {minimumFractionDigits: 2})} ₽
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600 dark:text-zinc-500">Примерная сумма:</span>
                  <span className="text-lg font-bold text-gray-800 dark:text-white">
                    {(quantity * (currentLotPrice || currentPrice)).toLocaleString('ru-RU', {minimumFractionDigits: 2})} ₽
                  </span>
                </div>
                <div className="text-xs text-gray-500 dark:text-zinc-500 mt-1 text-center">
                  *Фактическая сумма может отличаться
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !quantity || quantity <= 0 || !figi}
              className={`w-full py-3 rounded-2xl font-semibold shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-50 disabled:transform-none disabled:hover:shadow-lg ${
                orderType === 'buy'
                  ? 'border border-yellow-300 bg-yellow-400 text-black hover:bg-yellow-300'
                  : 'border border-red-400/35 bg-red-500/15 text-red-200 hover:bg-red-500/25'
              }`}
            >
              {loading ? (
                <ButtonLoader label="Исполняем..." />
              ) : (
                `${orderType === 'buy' ? 'Купить' : 'Продать'} ${quantity} лотов`
              )}
            </button>
          </form>
        </div>

        {/* Блок с акциями MOEX для быстрого выбора */}
        <div className="app-card rounded-3xl p-6">
          <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
            Акции MOEX
          </h3>
          <div className="grid grid-cols-2 gap-3">
            {shareOptions.slice(0, 8).map((instrument) => (
              <button
                key={instrument.figi}
                onClick={() => handleInstrumentSelect(instrument)}
                className={`app-muted-card rounded-2xl p-3 text-left transition-all duration-300 hover:border-yellow-400/30 hover:bg-[#211d13] ${figi === instrument.figi ? 'ring-2 ring-yellow-400' : ''}`}
              >
                <div className="font-semibold text-gray-800 dark:text-white">
                  {instrument.symbol}
                </div>
                <div className="text-sm text-gray-600 dark:text-zinc-500">
                  {instrument.name}
                </div>
                <div className="text-xs text-gray-500 dark:text-zinc-600 mt-1">
                  {instrument.figi}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
