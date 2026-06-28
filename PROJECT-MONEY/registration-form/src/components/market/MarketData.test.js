import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import MarketData from './MarketData';
import { marketAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  marketAPI: {
    getShares: jest.fn(),
    loadCandles: jest.fn(),
  },
  getErrorMessage: (_error, fallback) => fallback,
}));

const apiInstruments = [
  { figi: 'BBG004730N88', ticker: 'SBER', name: 'Сбербанк' },
  { figi: 'BBG004730RP0', ticker: 'GAZP', name: 'Газпром' },
  { figi: 'BBG004731489', ticker: 'GMKN', name: 'Норникель' },
];

const apiCandles = [
  { x: '2026-05-29T07:00:00Z', o: 100, h: 105, l: 99, c: 104, v: 1200 },
  { x: '2026-05-29T08:00:00Z', o: 104, h: 108, l: 103, c: 106, v: 1800 },
  { x: '2026-05-29T09:00:00Z', o: 106, h: 107, l: 101, c: 102, v: 1500 },
];

describe('MarketData charts', () => {
  let context;

  beforeEach(() => {
    marketAPI.getShares.mockResolvedValue({
      data: {
        status: 'ok',
        items: apiInstruments,
      },
    });

    marketAPI.loadCandles.mockResolvedValue({
      data: {
        status: 'ok',
        candles: apiCandles,
      },
    });

    context = {
      arc: jest.fn(),
      beginPath: jest.fn(),
      clearRect: jest.fn(),
      closePath: jest.fn(),
      createLinearGradient: jest.fn(() => ({ addColorStop: jest.fn() })),
      fill: jest.fn(),
      fillRect: jest.fn(),
      fillText: jest.fn(),
      lineTo: jest.fn(),
      measureText: jest.fn((text) => ({ width: String(text).length * 7 })),
      moveTo: jest.fn(),
      quadraticCurveTo: jest.fn(),
      restore: jest.fn(),
      save: jest.fn(),
      setLineDash: jest.fn(),
      setTransform: jest.fn(),
      stroke: jest.fn(),
    };

    jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
    Object.defineProperty(HTMLCanvasElement.prototype, 'clientWidth', { configurable: true, get: () => 900 });
    Object.defineProperty(HTMLCanvasElement.prototype, 'clientHeight', { configurable: true, get: () => 520 });
    jest.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 900,
      height: 520,
      top: 0,
      right: 900,
      bottom: 520,
      left: 0,
      x: 0,
      y: 0,
      toJSON: () => {},
    });

    global.ResizeObserver = class ResizeObserver {
      observe() {}
      disconnect() {}
    };
  });

  afterEach(() => {
    cleanup();
    jest.restoreAllMocks();
    delete global.ResizeObserver;
  });

  test('loads candles and draws the market chart canvas', async () => {
    render(<MarketData />);

    await waitFor(() => expect(marketAPI.loadCandles).toHaveBeenCalledWith('BBG004730N88', 1, '5min'));
    await waitFor(() => expect(context.setTransform).toHaveBeenCalled());
    expect(context.fillRect).toHaveBeenCalled();
  });

  test('shows a fallback chart when the market API fails', async () => {
    marketAPI.loadCandles.mockRejectedValueOnce(new Error('network down'));

    render(<MarketData />);

    expect(await screen.findByText(/локальный резервный график/i)).toBeInTheDocument();
    await waitFor(() => expect(context.setTransform).toHaveBeenCalled());
  });

  test('opens instrument dropdown from the instrument field and selects another instrument', async () => {
    render(<MarketData />);

    await waitFor(() => expect(marketAPI.getShares).toHaveBeenCalledWith(1000));
    await waitFor(() => expect(marketAPI.loadCandles).toHaveBeenCalledWith('BBG004730N88', 1, '5min'));
    expect(screen.queryByText('Популярные инструменты')).not.toBeInTheDocument();

    fireEvent.focus(screen.getByLabelText('Инструмент'));

    const norilskOption = screen.getByRole('option', { name: /GMKN/i });
    expect(norilskOption).toBeInTheDocument();

    fireEvent.click(norilskOption);

    expect(screen.getByLabelText('Инструмент')).toHaveValue('GMKN - Норникель');
    await waitFor(() => expect(marketAPI.loadCandles).toHaveBeenCalledWith('BBG004731489', 1, '5min'));
  });

  test('keeps fallback instruments when shares loading fails', async () => {
    marketAPI.getShares.mockRejectedValueOnce(new Error('shares unavailable'));

    render(<MarketData />);

    await waitFor(() => expect(marketAPI.getShares).toHaveBeenCalledWith(1000));

    fireEvent.focus(screen.getByLabelText('Инструмент'));

    expect(screen.getByRole('option', { name: /SBER/i })).toBeInTheDocument();
  });
});
