import React from 'react';
import { cleanup, render, waitFor } from '@testing-library/react';
import InteractiveMarketChart from './InteractiveMarketChart';

const candles = [
  {
    timestamp: new Date('2026-05-29T07:00:00Z'),
    open: 100,
    high: 105,
    low: 99,
    close: 104,
    volume: 1200,
  },
  {
    timestamp: new Date('2026-05-29T08:00:00Z'),
    open: 104,
    high: 108,
    low: 103,
    close: 106,
    volume: 1800,
  },
  {
    timestamp: new Date('2026-05-29T09:00:00Z'),
    open: 106,
    high: 107,
    low: 101,
    close: 102,
    volume: 1500,
  },
];

describe('InteractiveMarketChart', () => {
  let context;

  beforeEach(() => {
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

  test('draws after candles arrive following the empty state', async () => {
    const { rerender } = render(<InteractiveMarketChart data={[]} symbol="SBER" />);

    await waitFor(() => expect(context.setTransform).toHaveBeenCalled());
    const emptyDrawCount = context.setTransform.mock.calls.length;

    rerender(<InteractiveMarketChart data={candles} symbol="SBER" />);

    await waitFor(() => expect(context.setTransform.mock.calls.length).toBeGreaterThan(emptyDrawCount));
    expect(context.fillRect).toHaveBeenCalled();
  });
});
