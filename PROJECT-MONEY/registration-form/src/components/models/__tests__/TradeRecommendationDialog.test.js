import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import TradeRecommendationDialog from '../TradeRecommendationDialog';

const formatMoney = (value) => String(value);

function renderDialog(overrides = {}) {
  const props = {
    forecastResult: {
      forecast_id: 1,
      horizon: '1h',
      current_price: 100,
      predicted_price: 105,
      price_delta_percent: 5,
      recommendation: {
        action: 'SELL',
        quantity: 3,
        cash_balance: 1000,
        max_affordable_quantity: 10,
      },
    },
    tradeControls: { visible: true, quantity: 3, buyNow: false, autoSell: false },
    setTradeControls: jest.fn(),
    tradeLoading: false,
    confirmBotTrade: jest.fn(),
    formatMoney,
    isDark: false,
    ...overrides,
  };
  render(<TradeRecommendationDialog {...props} />);
  return props;
}

test('SELL открывает диалог продажи и не выполняет сделку до клика', () => {
  const props = renderDialog();

  expect(screen.getByRole('dialog')).toBeInTheDocument();
  expect(screen.getByText(/подтверждение продажи/i)).toBeInTheDocument();
  expect(props.confirmBotTrade).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: /продать/i }));

  expect(props.confirmBotTrade).toHaveBeenCalledWith('sell');
});

test('BUY_OPTIONAL показывает сумму покупки и подтверждает buy только по клику', () => {
  const props = renderDialog({
    forecastResult: {
      current_price: 120,
      predicted_price: 125,
      price_delta_percent: 4.1,
      recommendation: {
        action: 'BUY_OPTIONAL',
        cash_balance: 1000,
        max_affordable_quantity: 8,
      },
    },
    tradeControls: { visible: true, quantity: 2, buyNow: true, autoSell: false },
  });

  expect(screen.getByText(/покупка по рекомендации модели/i)).toBeInTheDocument();
  expect(screen.getByText(/итого/i).parentElement).toHaveTextContent('240 ₽');
  expect(props.confirmBotTrade).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: /купить/i }));

  expect(props.confirmBotTrade).toHaveBeenCalledWith('buy');
});

test('HOLD_AND_OPTIONAL_BUY не подтверждается без выбора автопродажи или докупки', () => {
  renderDialog({
    forecastResult: {
      horizon: '1h',
      current_price: 100,
      predicted_price: 105,
      price_delta_percent: 5,
      recommendation: {
        action: 'HOLD_AND_OPTIONAL_BUY',
        cash_balance: 1000,
        max_affordable_quantity: 10,
      },
    },
    tradeControls: { visible: true, quantity: 1, buyNow: false, autoSell: false },
  });

  expect(screen.getByRole('button', { name: /запланировать автопродажу/i })).toBeDisabled();
});

test('покупка выше внутреннего лимита требует короткого ручного подтверждения', () => {
  const props = renderDialog({
    forecastResult: {
      current_price: 125,
      predicted_price: 126,
      price_delta_percent: 0.8,
      recommendation: {
        action: 'BUY_OPTIONAL',
        cash_balance: 20000,
        max_affordable_quantity: 160,
      },
    },
    tradeControls: { visible: true, quantity: 100, buyNow: true, autoSell: false, largeTradeConfirmed: false },
    riskSettings: { largeTradeConfirmAmount: 5000 },
  });

  const buyButton = screen.getByRole('button', { name: /купить/i });
  expect(screen.getByText(/^подтверждение$/i)).toBeInTheDocument();
  expect(screen.getByText(/покупка 12500 ₽/i)).toBeInTheDocument();
  expect(screen.queryByText(/порог/i)).not.toBeInTheDocument();
  expect(buyButton).toBeDisabled();

  fireEvent.click(screen.getByRole('checkbox', { name: /подтверждаю/i }));

  expect(props.setTradeControls).toHaveBeenCalledWith(expect.any(Function));
});
