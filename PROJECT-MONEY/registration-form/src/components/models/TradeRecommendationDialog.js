import React, { useEffect, useRef } from 'react';
import { sanitizeNumberInput } from '../../utils/numberInput';
import { ButtonLoader } from '../common/LoadingSpinner';

const defaultIsProblemMessage = (message) => {
  const normalized = String(message || '').toLowerCase();
  return ['ошибка', 'не удалось', 'нельзя', 'закрыт', 'закрыта', 'проверьте', 'недостаточно', 'отключена', 'отключен', 'сначала', 'укажите', 'выберите'].some((marker) => normalized.includes(marker));
};

export default function TradeRecommendationDialog({
  forecastResult,
  tradeControls,
  setTradeControls,
  tradeLoading,
  confirmBotTrade,
  formatMoney,
  isDark,
  riskSettings = {},
  tradeStatusMessage = '',
  isProblemMessage = defaultIsProblemMessage,
}) {
  const panelRef = useRef(null);
  const closeDialog = () => setTradeControls(prev => ({ ...prev, visible: false }));

  const action = forecastResult?.recommendation?.action;
  const recommendation = forecastResult?.recommendation || {};
  const currentPrice = Number(forecastResult?.current_price || 0);
  const quantity = Number(tradeControls.quantity || 0);
  const amount = currentPrice * quantity;
  const largeTradeConfirmAmount = Number(riskSettings.largeTradeConfirmAmount || 0);
  const isBuyFlow = action === 'BUY_OPTIONAL' || (action === 'HOLD_AND_OPTIONAL_BUY' && tradeControls.buyNow);
  const needsLargeTradeConfirmation = isBuyFlow && largeTradeConfirmAmount > 0 && amount > largeTradeConfirmAmount;
  const largeTradeConfirmed = !needsLargeTradeConfirmation || Boolean(tradeControls.largeTradeConfirmed);
  const inputClass = `mt-2 w-full rounded-xl px-4 py-3 outline-none border ${
    isDark ? 'bg-gray-900 border-gray-700 text-white' : 'bg-white border-gray-200 text-gray-900'
  }`;
  const quantityInput = (event, max) => setTradeControls(prev => ({
    ...prev,
    quantity: sanitizeNumberInput(event.target.value, { min: 1, max, integer: true, maxLength: 7 }),
    largeTradeConfirmed: false,
  }));

  useEffect(() => {
    panelRef.current?.focus?.();
  }, [action]);

  const handleDialogKeyDown = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeDialog();
    }
  };

  const renderTradeStatus = () => {
    if (!tradeStatusMessage) return null;
    const problem = isProblemMessage(tradeStatusMessage);
    return (
      <div className={`mb-4 border p-3 text-sm ${
        problem
          ? 'border-red-500/25 bg-red-500/10 text-red-200'
          : 'border-green-500/25 bg-green-500/10 text-green-200'
      }`}>
        {tradeStatusMessage}
      </div>
    );
  };

  const renderLargeTradeConfirmation = () => {
    if (!needsLargeTradeConfirmation) return null;
    return (
      <div className="mb-4 border border-yellow-400/12 bg-[#11100d] p-3 text-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.18em] text-yellow-400/70">Подтверждение</div>
            <div className="mt-1 font-bold text-white">Покупка {formatMoney(amount)} ₽</div>
          </div>
          <label className="inline-flex w-fit items-center gap-3 text-zinc-100">
            <input
              type="checkbox"
              checked={Boolean(tradeControls.largeTradeConfirmed)}
              onChange={(event) => setTradeControls(prev => ({ ...prev, largeTradeConfirmed: event.target.checked }))}
              className="h-4 w-4 accent-yellow-400"
            />
            <span className="font-semibold">Подтверждаю</span>
          </label>
        </div>
      </div>
    );
  };

  if (!forecastResult || !tradeControls.visible) return null;

  if (action === 'SELL') {
    return (
      <div ref={panelRef} tabIndex={-1} onKeyDown={handleDialogKeyDown} role="dialog" aria-modal="true" aria-labelledby="trade-recommendation-sell-title" className="mt-5 rounded-2xl p-5 border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 focus:outline-none focus:ring-2 focus:ring-red-400/60">
        <h3 id="trade-recommendation-sell-title" className="text-lg font-bold text-red-700 dark:text-red-200 mb-2">Подтверждение продажи</h3>
        <p className="text-sm text-red-700 dark:text-red-100 mb-4">
          Модель прогнозирует падение на {forecastResult.price_delta_percent?.toFixed(2)}%. Рекомендуется продать позицию после подтверждения.
        </p>
        {renderTradeStatus()}
        <label className="block text-sm text-gray-700 dark:text-zinc-300 mb-4">
          Количество к продаже, шт.
          <input
            type="number"
            min="1"
            max={Math.max(1, Math.floor(Number(recommendation.quantity || 1)))}
            value={tradeControls.quantity}
            onChange={(event) => quantityInput(event, Math.max(1, Math.floor(Number(recommendation.quantity || 1))))}
            className={inputClass}
          />
        </label>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => confirmBotTrade('sell')}
            disabled={tradeLoading || quantity <= 0}
            className="px-5 py-3 rounded-xl font-bold bg-red-600 hover:bg-red-500 disabled:bg-gray-400 text-white"
          >
            {tradeLoading ? <ButtonLoader label="Продаем..." /> : 'Продать'}
          </button>
          <button
            type="button"
            onClick={closeDialog}
            className="px-5 py-3 rounded-xl font-bold bg-white dark:bg-[#111111] border border-gray-200 dark:border-zinc-800"
          >
            Отмена
          </button>
        </div>
      </div>
    );
  }

  if (action === 'BUY_OPTIONAL') {
    return (
      <div ref={panelRef} tabIndex={-1} onKeyDown={handleDialogKeyDown} role="dialog" aria-modal="true" aria-labelledby="trade-recommendation-buy-title" className="mt-5 rounded-2xl p-5 border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 focus:outline-none focus:ring-2 focus:ring-green-400/60">
        <h3 id="trade-recommendation-buy-title" className="text-lg font-bold text-green-700 dark:text-green-200 mb-2">Покупка по рекомендации модели</h3>
        <p className="text-sm text-green-700 dark:text-green-100 mb-4">
          Акции нет в портфеле. Модель прогнозирует рост на {forecastResult.price_delta_percent?.toFixed(2)}%.
        </p>
        {renderTradeStatus()}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div className="rounded-xl p-4 bg-white/70 dark:bg-[#070707]/70 border border-green-100 dark:border-green-800">
            <div className="text-xs text-gray-500">Текущая цена</div>
            <div className="font-bold text-gray-900 dark:text-white">{formatMoney(forecastResult.current_price)} ₽</div>
          </div>
          <div className="rounded-xl p-4 bg-white/70 dark:bg-[#070707]/70 border border-green-100 dark:border-green-800">
            <div className="text-xs text-gray-500">Свободные деньги</div>
            <div className="font-bold text-gray-900 dark:text-white">{formatMoney(recommendation.cash_balance)} ₽</div>
          </div>
          <label className="text-sm text-gray-700 dark:text-zinc-300">
            Количество к покупке
            <input
              type="number"
              min="1"
              max={Math.max(1, Number(recommendation.max_affordable_quantity || 1))}
              value={tradeControls.quantity}
              onChange={(event) => quantityInput(event, Math.max(1, Number(recommendation.max_affordable_quantity || 1)))}
              className={inputClass}
            />
          </label>
          <div className="rounded-xl p-4 bg-white/70 dark:bg-[#070707]/70 border border-green-100 dark:border-green-800">
            <div className="text-xs text-gray-500">Итого</div>
            <div className="font-bold text-gray-900 dark:text-white">{formatMoney(amount)} ₽</div>
          </div>
        </div>
        <div className="text-xs text-gray-500 mb-4">Максимум по свободным деньгам: {recommendation.max_affordable_quantity || 0} шт.</div>
        {renderLargeTradeConfirmation()}
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => confirmBotTrade('buy')}
            disabled={tradeLoading || quantity <= 0 || !largeTradeConfirmed}
            className="px-5 py-3 rounded-xl font-bold bg-green-600 hover:bg-green-500 disabled:bg-gray-400 text-white"
          >
            {tradeLoading ? <ButtonLoader label="Покупаем..." /> : 'Купить'}
          </button>
          <button
            type="button"
            onClick={closeDialog}
            className="px-5 py-3 rounded-xl font-bold bg-white dark:bg-[#111111] border border-gray-200 dark:border-zinc-800"
          >
            Отмена
          </button>
        </div>
      </div>
    );
  }

  if (action === 'HOLD_AND_OPTIONAL_BUY') {
    return (
      <div ref={panelRef} tabIndex={-1} onKeyDown={handleDialogKeyDown} role="dialog" aria-modal="true" aria-labelledby="trade-recommendation-hold-title" className="mt-5 rounded-2xl p-5 border border-blue-200 dark:border-yellow-500/20 bg-blue-50 dark:bg-yellow-400/10 focus:outline-none focus:ring-2 focus:ring-yellow-400/60">
        <h3 id="trade-recommendation-hold-title" className="text-lg font-bold text-blue-700 dark:text-yellow-200 mb-2">Держать позицию / опционально докупить</h3>
        <p className="text-sm text-blue-700 dark:text-yellow-100 mb-4">
          План: держать акцию и продать через выбранный горизонт, если цена достигнет прогнозного уровня {formatMoney(forecastResult.predicted_price)} ₽.
        </p>
        {renderTradeStatus()}
        <div className="space-y-3 mb-4">
          <label className="flex items-center gap-3 text-sm text-gray-700 dark:text-zinc-300">
            <input
              type="checkbox"
              checked={tradeControls.autoSell}
              onChange={(event) => setTradeControls(prev => ({ ...prev, autoSell: event.target.checked }))}
            />
            Автоматически продать через выбранный горизонт
          </label>
          <label className="flex items-center gap-3 text-sm text-gray-700 dark:text-zinc-300">
            <input
              type="checkbox"
              checked={tradeControls.buyNow}
              onChange={(event) => setTradeControls(prev => ({ ...prev, buyNow: event.target.checked, largeTradeConfirmed: false }))}
            />
            Докупить сейчас
          </label>
        </div>

        {tradeControls.buyNow && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div className="rounded-xl p-4 bg-white/70 dark:bg-[#070707]/70 border border-blue-100 dark:border-yellow-500/20">
              <div className="text-xs text-gray-500">Текущая цена</div>
              <div className="font-bold text-gray-900 dark:text-white">{formatMoney(forecastResult.current_price)} ₽</div>
            </div>
            <div className="rounded-xl p-4 bg-white/70 dark:bg-[#070707]/70 border border-blue-100 dark:border-yellow-500/20">
              <div className="text-xs text-gray-500">Свободные деньги</div>
              <div className="font-bold text-gray-900 dark:text-white">{formatMoney(recommendation.cash_balance)} ₽</div>
            </div>
            <label className="text-sm text-gray-700 dark:text-zinc-300">
              Сколько купить, шт.
              <input
                type="number"
                min="1"
                max={Math.max(1, Number(recommendation.max_affordable_quantity || 1))}
                value={tradeControls.quantity}
                onChange={(event) => quantityInput(event, Math.max(1, Number(recommendation.max_affordable_quantity || 1)))}
                className={inputClass}
              />
            </label>
            <div className="rounded-xl p-4 bg-white/70 dark:bg-[#070707]/70 border border-blue-100 dark:border-yellow-500/20">
              <div className="text-xs text-gray-500">Сумма покупки</div>
              <div className="font-bold text-gray-900 dark:text-white">{formatMoney(amount)} ₽</div>
            </div>
          </div>
        )}

        {tradeControls.buyNow && renderLargeTradeConfirmation()}

        {tradeControls.autoSell && (
          <div className="mb-4 text-sm text-gray-600 dark:text-zinc-300">
            Будет сохранено запланированное действие продажи через {forecastResult.horizon === '1d' ? 'день' : 'час'} по целевой цене {formatMoney(forecastResult.predicted_price)} ₽. Для исполнения нужен включённый фоновый обработчик.
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => confirmBotTrade(tradeControls.buyNow ? 'buy' : 'schedule_sell')}
            disabled={tradeLoading || (!tradeControls.buyNow && !tradeControls.autoSell) || (tradeControls.buyNow && !largeTradeConfirmed)}
            className="px-5 py-3 rounded-xl font-bold bg-yellow-400 hover:bg-yellow-300 disabled:bg-gray-700 text-black"
          >
            {tradeLoading ? <ButtonLoader label="Подтверждаем..." dark /> : tradeControls.buyNow ? 'Докупить' : 'Запланировать автопродажу'}
          </button>
          <button
            type="button"
            onClick={closeDialog}
            className="px-5 py-3 rounded-xl font-bold bg-white dark:bg-[#111111] border border-gray-200 dark:border-zinc-800"
          >
            Отмена
          </button>
        </div>
      </div>
    );
  }

  return null;
}
