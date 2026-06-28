import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import InstrumentSelector from '../InstrumentSelector';

function renderSelector(overrides = {}) {
  const props = {
    isDark: false,
    selectedSource: 'popular',
    setSelectedSource: jest.fn(),
    selectedInstrument: { figi: 'BBG004730N88', ticker: 'SBER', name: 'Сбер Банк' },
    manualInstrument: { figi: '', ticker: '' },
    setManualInstrument: jest.fn(),
    instrumentOptions: [
      { figi: 'BBG004730N88', ticker: 'SBER', name: 'Сбер Банк' },
      { figi: 'BBG004731032', ticker: 'LKOH', name: 'Лукойл' },
    ],
    selectInstrument: jest.fn(),
    ...overrides,
  };
  render(<InstrumentSelector {...props} />);
  return props;
}

test('пользователь может переключиться на выбор из портфеля', () => {
  const props = renderSelector();

  fireEvent.click(screen.getByRole('button', { name: /портфель/i }));

  expect(props.setSelectedSource).toHaveBeenCalledWith('portfolio');
});

test('пользователь может выбрать популярную акцию', () => {
  const props = renderSelector();

  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'BBG004731032' } });

  expect(props.selectInstrument).toHaveBeenCalledWith(
    expect.objectContaining({ figi: 'BBG004731032', ticker: 'LKOH' }),
    'popular'
  );
});

test('пользователь может ввести FIGI вручную и подтвердить выбор', () => {
  const setManualInstrument = jest.fn((updater) => updater({ figi: '', ticker: '' }));
  const props = renderSelector({
    selectedSource: 'manual',
    manualInstrument: { figi: 'BBG004730N88', ticker: 'SBER' },
    setManualInstrument,
  });

  fireEvent.click(screen.getByRole('button', { name: /выбрать/i }));

  expect(props.selectInstrument).toHaveBeenCalledWith(
    { figi: 'BBG004730N88', ticker: 'SBER' },
    'manual'
  );
});
