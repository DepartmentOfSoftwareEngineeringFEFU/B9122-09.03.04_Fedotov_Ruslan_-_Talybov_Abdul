import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import ForecastHorizonSelector from '../ForecastHorizonSelector';

test('выбор horizon, режима гиперпараметров и threshold меняет значения payload-state', () => {
  const setForecastHorizon = jest.fn();
  const setHyperparamMode = jest.fn();
  const setFlatThresholdPercent = jest.fn();

  render(
    <ForecastHorizonSelector
      isDark={false}
      forecastHorizon="1h"
      setForecastHorizon={setForecastHorizon}
      hyperparamMode="auto"
      setHyperparamMode={setHyperparamMode}
      flatThresholdPercent={1}
      setFlatThresholdPercent={setFlatThresholdPercent}
    />
  );

  fireEvent.change(screen.getByLabelText(/горизонт/i), { target: { value: '1d' } });
  fireEvent.change(screen.getByLabelText(/настройка/i), { target: { value: 'manual' } });
  fireEvent.change(screen.getByLabelText(/flat/i), { target: { value: '1.5' } });

  expect(setForecastHorizon).toHaveBeenCalledWith('1d');
  expect(setHyperparamMode).toHaveBeenCalledWith('manual');
  expect(setFlatThresholdPercent).toHaveBeenCalledWith('1.5');
});
