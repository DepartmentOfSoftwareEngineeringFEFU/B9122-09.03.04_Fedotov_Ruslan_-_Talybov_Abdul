import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import Backtest from './Backtest';
import { backtestAPI } from '../../services/api';

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true }),
}));

jest.mock('../../services/api', () => ({
  backtestAPI: {
    getBacktestResults: jest.fn(),
  },
  getErrorMessage: (_error, fallback) => fallback,
}));

describe('Backtest page', () => {
  beforeEach(() => {
    backtestAPI.getBacktestResults.mockResolvedValue({
      data: [
        {
          id: 1,
          name: 'SVR sandbox run',
          stock_symbols: ['SBER', 'GAZP'],
          total_return: 0.12,
        },
      ],
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('loads saved backtest results through the supported API client method', async () => {
    render(<Backtest />);

    await waitFor(() => expect(backtestAPI.getBacktestResults).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('SVR sandbox run')).toBeInTheDocument();
    expect(screen.getByText('SBER, GAZP')).toBeInTheDocument();
  });

  test('shows a clear error when saved results cannot be loaded', async () => {
    backtestAPI.getBacktestResults.mockRejectedValueOnce(new Error('network down'));

    render(<Backtest />);

    expect(await screen.findByText('Не удалось загрузить backtest-результаты')).toBeInTheDocument();
  });
});
