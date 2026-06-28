// services/api.js
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000/';
const DEBUG_API = process.env.REACT_APP_DEBUG_API === 'true';
const DEFAULT_TIMEOUT_MS = 10000;
const ML_OPERATION_TIMEOUT_MS = 180000;
const SENSITIVE_KEYS = ['password', 'tinkoff_token', 'access_token', 'token', 'cookie', 'authorization'];

const redact = (value) => {
  if (Array.isArray(value)) {
    return value.map(redact);
  }
  if (value && typeof value === 'object') {
    return Object.entries(value).reduce((acc, [key, item]) => {
      const normalizedKey = key.toLowerCase();
      acc[key] = SENSITIVE_KEYS.some((sensitiveKey) => normalizedKey.includes(sensitiveKey))
        ? '***REDACTED***'
        : redact(item);
      return acc;
    }, {});
  }
  return value;
};

const stringifyMessage = (value) => {
  if (!value) return '';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) {
    return value.map(stringifyMessage).filter(Boolean).join('; ');
  }
  if (typeof value === 'object') {
    if (typeof value.message === 'string') return value.message;
    if (typeof value.detail === 'string') return value.detail;
    try {
      return JSON.stringify(value);
    } catch (_error) {
      return '';
    }
  }
  return String(value);
};

const cleanTechnicalNoise = (message) => message
  .replace(/<StatusCode\.[^>]+>/gi, '')
  .replace(/Metadata\([^)]*\)/gi, '')
  .replace(/tracking_id=['"][^'"]+['"]/gi, '')
  .replace(/ratelimit_[a-z_]+=?['"]?[^,)]*['"]?/gi, '')
  .replace(/[(){}<>]/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

export const normalizeUserMessage = (value, fallback = 'Не удалось выполнить запрос. Попробуйте ещё раз.') => {
  const raw = stringifyMessage(value);
  const lower = raw.toLowerCase();

  if (!raw) return fallback;

  if (
    lower.includes('instrument is not available for trading') ||
    lower.includes('not available for trading') ||
    lower.includes('trading is not available')
  ) {
    return 'Сейчас этим инструментом нельзя торговать. Биржа может быть закрыта, инструмент может быть недоступен в песочнице или выбран не тот FIGI.';
  }

  if (lower.includes('market is closed') || lower.includes('exchange is closed') || lower.includes('trading session')) {
    return 'Биржа сейчас закрыта. Сделку можно повторить в торговые часы.';
  }

  if (lower.includes('rate limit') || lower.includes('ratelimit') || lower.includes('too many requests')) {
    return 'Слишком много запросов подряд. Подождите несколько секунд и повторите действие.';
  }

  if (lower.includes('not enough') || lower.includes('insufficient') || lower.includes('недостаточно')) {
    return 'Недостаточно денег или бумаг для этой операции. Проверьте баланс и количество.';
  }

  if (lower.includes('invalid argument') || lower.includes('validation') || lower.includes('422')) {
    return 'Запрос не принят. Проверьте выбранный инструмент, количество и параметры операции.';
  }

  if (lower.includes('unauthorized') || lower.includes('unauthenticated') || lower.includes('401')) {
    return 'Сессия истекла или токен недействителен. Войдите заново или обновите T-Invest API Token.';
  }

  if (lower.includes('forbidden') || lower.includes('permission') || lower.includes('403')) {
    return 'Нет доступа к этой операции. Проверьте права токена и режим торговли.';
  }

  if (lower.includes('not found') || lower.includes('404')) {
    return 'Данные не найдены. Проверьте выбранный инструмент или счёт.';
  }

  if (lower.includes('network error') || lower.includes('failed to fetch')) {
    return 'Сервер проекта недоступен. Проверьте, что он запущен, и повторите действие.';
  }

  if (lower.includes('timeout') || lower.includes('exceeded')) {
    return 'Сервер отвечает слишком долго. Повторите действие через несколько секунд.';
  }

  const cleaned = cleanTechnicalNoise(raw);
  if (!cleaned || cleaned.length < 3) return fallback;

  // Не показываем пользователю сырые grpc/python/metadata сообщения.
  if (/StatusCode\.|Metadata\(|tracking_id|ratelimit_/i.test(raw)) {
    return fallback;
  }

  return cleaned;
};

export const getErrorMessage = (error, fallback = 'Не удалось выполнить запрос. Попробуйте ещё раз.') => {
  const data = error?.response?.data;

  if (typeof data?.message === 'string') return normalizeUserMessage(data.message, fallback);
  if (typeof data?.detail === 'string') return normalizeUserMessage(data.detail, fallback);
  if (Array.isArray(data?.detail)) return 'Проверьте заполненные поля. В запросе есть некорректные данные.';
  if (data && typeof data === 'object') return normalizeUserMessage(data, fallback);

  if (error?.code === 'ECONNABORTED') {
    return 'Сервер отвечает слишком долго. Повторите действие через несколько секунд.';
  }

  if (typeof error?.message === 'string') return normalizeUserMessage(error.message, fallback);
  return fallback;
};

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: DEFAULT_TIMEOUT_MS,
});

api.interceptors.request.use(config => {
  if (DEBUG_API) {
    // eslint-disable-next-line no-console
    console.debug(`→ ${config.method?.toUpperCase()} ${config.url}`, redact(config.data));
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    if (DEBUG_API) {
      // eslint-disable-next-line no-console
      console.debug(`← ${response.status} ${response.config.url}`);
    }
    return response;
  },
  (error) => Promise.reject(error)
);

export const authAPI = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (userData) => api.post('/auth/register', userData),
  logout: () => api.post('/auth/logout'),
  getMe: () => api.get('/auth/me'),
  updateTinkoffToken: (tinkoffToken) => api.put('/auth/settings/tinkoff-token', { tinkoff_token: tinkoffToken }),
};

export const tradeAPI = {
  getPortfolio: (accountId = null) => api.get('/trade/portfolio', { params: { account_id: accountId } }),
  executeOrder: (orderData) => api.post('/trade/execute', orderData),
  openSandboxAccount: (accountType = 'ACCOUNT_TYPE_TINKOFF') => api.post('/accounts/open', { account_type: accountType }),
  sandboxPayIn: (accountId, amount, currency = 'RUB') => api.post('/accounts/payin', { account_id: accountId, amount, currency }),
  getAccounts: () => api.get('/accounts/'),
  getAccountBalance: (accountId = null) => api.get('/accounts/balance', { params: { account_id: accountId } }),
  getAccountPortfolio: (accountId = null) => api.get('/accounts/portfolio', { params: { account_id: accountId } }),
  getAccountOperations: (accountId, fromDate, toDate) => api.get('/accounts/operations', {
    params: { account_id: accountId, from_date: fromDate, to_date: toDate }
  }),
  closeAccount: (accountId) => api.delete(`/accounts/${accountId}`),
};

export const marketAPI = {
  loadCandles: (figi, days = 1, interval = '1min') => api.get(`/market/candles/${figi}`, { params: { days, interval } }),
  getShares: (limit = 1000) => api.get('/market/shares', { params: { limit } }),
  getPopularShares: () => api.get('/market/popular-shares'),
  getInstrument: (figi) => api.get(`/market/instrument/${figi}`),
  getCurrentPrice: (figi) => api.get(`/market/current-price/${figi}`),
  getTradingMode: () => api.get('/market/trading-mode'),
  getUserCandles: (skip = 0, limit = 100) => api.get('/market/user-candles', { params: { skip, limit } }),
  deleteUserCandles: (figi) => api.delete(`/market/user-candles/${figi}`),
  getCandleDataForML: (figi, startDate = null, endDate = null) => {
    const params = {};
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    return api.get(`/market/user-candles/${figi}/data`, { params });
  }
};

export const modelAPI = {
  trainSVR: (params = {}) => api.post('/models/train/svr', params, { timeout: ML_OPERATION_TIMEOUT_MS }),
  trainGPR: (params = {}) => api.post('/models/train/gpr', params, { timeout: ML_OPERATION_TIMEOUT_MS }),
  trainAdaptive: (params = {}) => api.post('/models/train/adaptive', params, { timeout: ML_OPERATION_TIMEOUT_MS }),
  forecast: (params = {}) => api.post('/models/forecast', params, { timeout: ML_OPERATION_TIMEOUT_MS }),
  compare: (params = {}) => api.post('/models/compare', params, { timeout: ML_OPERATION_TIMEOUT_MS }),
  getForecasts: (params = {}) => api.get('/models/forecasts', { params }),
  getDataQuality: (params = {}) => api.get('/models/data-quality', { params }),
  getModels: () => api.get('/models/my-models'),
};

export const botTradeAPI = {
  confirmAction: (payload = {}) => api.post('/bot-trades/confirm', payload),
  getHistory: (params = {}) => api.get('/bot-trades/history', { params }),
  getAnalytics: () => api.get('/bot-trades/analytics'),
  getAutoSellStatus: () => api.get('/bot-trades/auto-sell/status'),
  processAutoSellsOnce: (params = {}) => api.post('/bot-trades/auto-sell/process', null, { params }),
  startRandomBulk: (payload = {}) => api.post('/bot-trades/random-bulk/start', payload),
  listRandomBulk: (params = {}) => api.get('/bot-trades/random-bulk', { params }),
  getLatestRandomBulk: () => api.get('/bot-trades/random-bulk/latest'),
  getRandomBulk: (batchId) => api.get(`/bot-trades/random-bulk/${batchId}`),
  downloadRandomBulkCsv: (batchId) => api.get(`/bot-trades/random-bulk/${batchId}/csv`, { responseType: 'blob' }),
  getRandomBulkCsvUrl: (batchId) => `${API_BASE_URL.replace(/\/$/, '')}/bot-trades/random-bulk/${batchId}/csv`,
};

export const analyticsAPI = {
  getOverview: (params = {}) => api.get('/analytics/overview', { params }),
};

export const backtestAPI = {
  getBacktestResults: (params = {}) => api.get('/backtest/results', { params }),
  getBacktestResult: (resultId) => api.get(`/backtest/results/${resultId}`),
  deleteBacktestResult: (resultId) => api.delete(`/backtest/results/${resultId}`),
};

export default api;
