import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Trading from './Trading';
import { marketAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  tradeAPI: {
    executeOrder: jest.fn(),
  },
  marketAPI: {
    getShares: jest.fn(),
    getCurrentPrice: jest.fn(),
  },
  getErrorMessage: (_error, fallback) => fallback,
}));

const apiInstruments = [
  { figi: 'FIGI-WIDE-ONLY', ticker: 'WIDE', name: 'Широкий рынок' },
];

describe('Trading instrument picker', () => {
  beforeEach(() => {
    marketAPI.getShares.mockResolvedValue({
      data: {
        status: 'ok',
        items: apiInstruments,
      },
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('loads the broad shares list and allows selecting an API-only instrument', async () => {
    render(<Trading />);

    await waitFor(() => expect(marketAPI.getShares).toHaveBeenCalledWith(1000));

    const input = screen.getByPlaceholderText(/Начните вводить/i);
    fireEvent.change(input, { target: { value: 'WIDE' } });

    const matches = await screen.findAllByText('Широкий рынок');
    fireEvent.click(matches[0]);

    expect(input).toHaveValue('WIDE - Широкий рынок');
    expect(screen.getAllByText(/FIGI-WIDE-ONLY/).length).toBeGreaterThan(0);
  });

  test('keeps fallback instruments when broad shares loading fails', async () => {
    marketAPI.getShares.mockRejectedValueOnce(new Error('shares unavailable'));

    render(<Trading />);

    await waitFor(() => expect(marketAPI.getShares).toHaveBeenCalledWith(1000));

    const input = screen.getByPlaceholderText(/Начните вводить/i);
    fireEvent.change(input, { target: { value: 'SBER' } });

    expect(screen.getByText('Сбербанк')).toBeInTheDocument();
  });
});
