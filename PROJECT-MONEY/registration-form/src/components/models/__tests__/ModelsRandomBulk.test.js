import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Models from '../Models';
import { botTradeAPI, marketAPI } from '../../../services/api';

jest.mock('../../../services/api', () => ({
  modelAPI: {
    compare: jest.fn(),
    forecast: jest.fn(),
    getDataQuality: jest.fn(),
    getForecasts: jest.fn(),
  },
  marketAPI: {
    deleteUserCandles: jest.fn(),
    getShares: jest.fn(),
    getPopularShares: jest.fn(),
    getTradingMode: jest.fn(),
    getUserCandles: jest.fn(),
    loadCandles: jest.fn(),
  },
  tradeAPI: {
    getPortfolio: jest.fn(),
  },
  botTradeAPI: {
    confirmAction: jest.fn(),
    startRandomBulk: jest.fn(),
    listRandomBulk: jest.fn(),
    getLatestRandomBulk: jest.fn(),
    getRandomBulk: jest.fn(),
    downloadRandomBulkCsv: jest.fn(),
    getRandomBulkCsvUrl: jest.fn((batchId) => `/bot-trades/random-bulk/${batchId}/csv`),
  },
  getErrorMessage: (_error, fallback) => fallback,
}));

jest.mock('../InstrumentSelector', () => function MockInstrumentSelector() {
  return <div />;
});
jest.mock('../ForecastHorizonSelector', () => function MockForecastHorizonSelector() {
  return <div />;
});
jest.mock('../ModelTypeSelector', () => function MockModelTypeSelector() {
  return <div />;
});
jest.mock('../charts/ForecastPriceChart', () => function MockForecastPriceChart() {
  return <div />;
});
jest.mock('../panels/ModelComparisonPanel', () => function MockModelComparisonPanel() {
  return <div />;
});
jest.mock('../panels/ForecastHistoryPanel', () => function MockForecastHistoryPanel() {
  return <div />;
});
jest.mock('../panels/ModelDataPanel', () => function MockModelDataPanel() {
  return <div />;
});
jest.mock('../panels/RiskSettingsPanel', () => function MockRiskSettingsPanel() {
  return <div />;
});
jest.mock('../ForecastResultCard', () => function MockForecastResultCard() {
  return <div />;
});
jest.mock('../BotTradeControls', () => function MockBotTradeControls() {
  return <div />;
});
jest.mock('../TradeRecommendationDialog', () => function MockTradeRecommendationDialog() {
  return <div />;
});

async function openRandomBulkPanel() {
  expect(screen.queryByRole('button', { name: /Запустить покупку 30/i })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /Дополнительно/i }));
  fireEvent.click(await screen.findByRole('button', { name: 'Покупка 30' }));

  return screen.findByRole('button', { name: /Запустить покупку 30/i });
}

describe('Models random bulk trading', () => {
  beforeEach(() => {
    marketAPI.getShares.mockResolvedValue({ data: { status: 'ok', items: [] } });
    marketAPI.loadCandles.mockResolvedValue({ data: { status: 'ok', candles: [] } });
    marketAPI.getTradingMode.mockResolvedValue({
      data: {
        status: 'ok',
        sandbox: true,
        mode: 'sandbox',
        bulk_trade_worker_enabled: true,
        auto_sell_dry_run: false,
      },
    });
    marketAPI.getUserCandles.mockResolvedValue({ data: { status: 'ok', candles_by_figi: [] } });

    const { modelAPI, tradeAPI } = require('../../../services/api');
    modelAPI.getDataQuality.mockResolvedValue({ data: { quality_status: 'empty', candle_count: 0 } });
    modelAPI.getForecasts.mockResolvedValue({ data: { status: 'ok', items: [] } });
    tradeAPI.getPortfolio.mockResolvedValue({ data: { positions: [], cash_balance: 0 } });
    botTradeAPI.getLatestRandomBulk.mockRejectedValue({ response: { status: 404 } });
  });

  afterEach(() => {
    window.localStorage.clear();
    jest.restoreAllMocks();
    jest.clearAllMocks();
  });

  test('keeps random bulk controls in the advanced bulk tab', async () => {
    render(<Models />);

    const button = await openRandomBulkPanel();
    expect(button).toBeInTheDocument();
  });

  test('starts random bulk batch with selected account id', async () => {
    botTradeAPI.startRandomBulk.mockResolvedValue({
      data: {
        id: 7,
        batch_id: 7,
        status: 'queued',
        target_count: 30,
        candidate_count: 0,
        scanned_count: 0,
        bought_count: 0,
        closed_count: 0,
        failed_count: 0,
        items: [],
      },
    });
    window.localStorage.setItem('trade.selected_account_id', 'acc-new');

    render(<Models />);

    const button = await openRandomBulkPanel();
    await waitFor(() => expect(button).not.toBeDisabled());
    fireEvent.click(button);

    await waitFor(() => expect(botTradeAPI.startRandomBulk).toHaveBeenCalledWith({
      target_count: 30,
      account_id: 'acc-new',
    }));
    expect(await screen.findByText(/Batch #7 выполняется/i)).toBeInTheDocument();
  });

  test('downloads csv through authenticated api when export is ready', async () => {
    window.URL.createObjectURL = jest.fn(() => 'blob:csv');
    window.URL.revokeObjectURL = jest.fn();
    jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    botTradeAPI.startRandomBulk.mockResolvedValue({
      data: {
        id: 8,
        batch_id: 8,
        status: 'completed',
        target_count: 30,
        candidate_count: 30,
        scanned_count: 30,
        bought_count: 30,
        closed_count: 30,
        failed_count: 0,
        csv_download_url: '/bot-trades/random-bulk/8/csv',
        items: [],
      },
    });
    botTradeAPI.downloadRandomBulkCsv.mockResolvedValue({
      data: new Blob(['batch_id,item_id\n8,1\n'], { type: 'text/csv' }),
    });

    render(<Models />);

    const button = await openRandomBulkPanel();
    await waitFor(() => expect(button).not.toBeDisabled());
    fireEvent.click(button);

    const csvButton = await screen.findByRole('button', { name: /Скачать CSV/i });
    fireEvent.click(csvButton);

    await waitFor(() => expect(botTradeAPI.downloadRandomBulkCsv).toHaveBeenCalledWith(8));
    expect(window.URL.createObjectURL).toHaveBeenCalled();
  });

  test('disables random bulk button when backend worker is off', async () => {
    marketAPI.getTradingMode.mockResolvedValue({
      data: {
        status: 'ok',
        sandbox: true,
        mode: 'sandbox',
        bulk_trade_worker_enabled: false,
        auto_sell_dry_run: false,
      },
    });

    render(<Models />);

    const button = await openRandomBulkPanel();
    await waitFor(() => expect(button).toBeDisabled());
    expect(await screen.findByText(/Bulk worker выключен/i)).toBeInTheDocument();
  });

  test('restores latest active batch after reload', async () => {
    botTradeAPI.getLatestRandomBulk.mockResolvedValue({
      data: {
        id: 9,
        batch_id: 9,
        status: 'scheduled_sell',
        status_label: 'Ожидаем продажу',
        next_action_label: 'Покупки сделаны. Ждём продажи.',
        target_count: 30,
        candidate_count: 251,
        scanned_count: 251,
        bought_count: 10,
        closed_count: 0,
        skipped_count: 20,
        failed_count: 0,
        nearest_scheduled_sell_at: new Date(Date.now() + 30 * 60000).toISOString(),
        items: [],
      },
    });

    render(<Models />);

    await waitFor(() => expect(botTradeAPI.getLatestRandomBulk).toHaveBeenCalled());
    await openRandomBulkPanel();
    expect(await screen.findByText(/Ожидаем продажу/i)).toBeInTheDocument();
    expect(await screen.findByText(/Batch #9 выполняется/i)).toBeInTheDocument();
  });
});
