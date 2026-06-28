import { render, screen } from '@testing-library/react';
import App from './App';

jest.mock('./services/api', () => ({
  authAPI: {
    getMe: jest.fn().mockRejectedValue(new Error('Not authenticated')),
    login: jest.fn(),
    register: jest.fn(),
    logout: jest.fn(),
    updateTinkoffToken: jest.fn(),
  },
  tradeAPI: {},
  marketAPI: {},
  modelAPI: {},
  botTradeAPI: {},
  analyticsAPI: {},
  backtestAPI: {},
  getErrorMessage: jest.fn((error, fallback) => fallback || error.message),
}));

test('renders login screen for unauthenticated users', async () => {
  render(<App />);

  expect(await screen.findByRole('heading', { name: /вход/i })).toBeInTheDocument();
});
