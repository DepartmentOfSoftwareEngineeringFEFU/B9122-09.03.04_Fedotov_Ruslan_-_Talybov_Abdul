import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import Models from '../Models';
import { marketAPI } from '../../../services/api';

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

jest.mock('../InstrumentSelector', () => function MockInstrumentSelector({ instrumentOptions }) {
  const React = require('react');
  return React.createElement(
    'select',
    { 'aria-label': 'models instruments' },
    instrumentOptions.map((item) => React.createElement(
      'option',
      { key: item.figi, value: item.figi },
      `${item.ticker || item.symbol || item.figi} - ${item.name || item.figi}`
    ))
  );
});

jest.mock('../ForecastHorizonSelector', () => function MockForecastHorizonSelector() {
  const React = require('react');
  return React.createElement('div', null);
});
jest.mock('../ModelTypeSelector', () => function MockModelTypeSelector() {
  const React = require('react');
  return React.createElement('div', null);
});
jest.mock('../charts/ForecastPriceChart', () => function MockForecastPriceChart() {
  const React = require('react');
  return React.createElement('div', null);
});
jest.mock('../panels/ModelComparisonPanel', () => function MockModelComparisonPanel() {
  const React = require('react');
  return React.createElement('div', null);
});
jest.mock('../panels/ForecastHistoryPanel', () => function MockForecastHistoryPanel() {
  const React = require('react');
  return React.createElement('div', null);
});
jest.mock('../panels/ModelDataPanel', () => function MockModelDataPanel() {
  const React = require('react');
  return React.createElement('div', null);
});
jest.mock('../panels/RiskSettingsPanel', () => function MockRiskSettingsPanel() {
  const React = require('react');
  return React.createElement('div', null);
});
jest.mock('../ForecastResultCard', () => function MockForecastResultCard() {
  const React = require('react');
  return React.createElement('div', null);
});
jest.mock('../BotTradeControls', () => function MockBotTradeControls() {
  const React = require('react');
  return React.createElement('div', null);
});
jest.mock('../TradeRecommendationDialog', () => function MockTradeRecommendationDialog() {
  const React = require('react');
  return React.createElement('div', null);
});

const apiInstruments = [
  { figi: 'FIGI-WIDE-ONLY', ticker: 'WIDE', name: 'Широкий рынок' },
];

describe('Models shares source', () => {
  beforeEach(() => {
    marketAPI.getShares.mockResolvedValue({
      data: {
        status: 'ok',
        items: apiInstruments,
      },
    });
    marketAPI.loadCandles.mockResolvedValue({ data: { status: 'ok', candles: [] } });
    marketAPI.getTradingMode.mockResolvedValue({ data: { status: 'ok', sandbox: true, mode: 'sandbox' } });
    marketAPI.getUserCandles.mockResolvedValue({ data: { status: 'ok', candles_by_figi: [] } });

    marketAPI.getPopularShares.mockResolvedValue({ data: { status: 'ok', items: [] } });

    const { modelAPI, tradeAPI, botTradeAPI } = require('../../../services/api');
    modelAPI.getDataQuality.mockResolvedValue({ data: { quality_status: 'empty', candle_count: 0 } });
    modelAPI.getForecasts.mockResolvedValue({ data: { status: 'ok', items: [] } });
    tradeAPI.getPortfolio.mockResolvedValue({ data: { positions: [], cash_balance: 0 } });
    botTradeAPI.getLatestRandomBulk.mockRejectedValue({ response: { status: 404 } });
  });

  afterEach(() => {
    window.localStorage.clear();
    jest.clearAllMocks();
  });

  test('loads broad MOEX shares instead of the popular-shares endpoint', async () => {
    render(<Models />);

    await waitFor(() => expect(marketAPI.getShares).toHaveBeenCalledWith(1000));

    expect(marketAPI.getPopularShares).not.toHaveBeenCalled();
    expect(await screen.findByRole('option', { name: /WIDE - Широкий рынок/i })).toBeInTheDocument();
  });
});
