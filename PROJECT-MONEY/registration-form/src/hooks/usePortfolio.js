// src/hooks/usePortfolio.js
import { useState, useCallback, useMemo, useEffect } from 'react';
import { getErrorMessage, tradeAPI } from '../services/api';
import { formatMoney } from '../utils/formatters';
import { getInstrumentDisplayName, getInstrumentSector, getInstrumentTicker } from '../utils/instruments';

const EMPTY_PORTFOLIO_DATA = {
  totalValue: 0,
  cashBalance: 0,
  totalStocksValue: 0,
  totalProfit: 0,
  profitPercent: 0,
  positionsCount: 0,
  positions: []
};

export const usePortfolio = (autoLoad = true) => {
  const [portfolioData, setPortfolioData] = useState(null);
  const [loading, setLoading] = useState(autoLoad);
  const [error, setError] = useState(null);

  const processPortfolioData = useCallback((apiData) => {
    const stockPositions = apiData?.positions?.filter(pos => pos.instrument_type === 'share') || [];
    const processedPositions = stockPositions.map(position => {
      const quantity = position.quantity || 0;
      const currentPrice = position.price || 0;
      const marketValue = position.value || 0;
      const profit = position.expected_yield || 0;
      const avgPrice = position.average_price || (quantity > 0 ? (marketValue - profit) / quantity : 0);
      const costBasis = avgPrice * quantity;
      const profitPercent = position.expected_yield_percent ?? (costBasis > 0 ? (profit / costBasis) * 100 : 0);

      return {
        figi: position.figi,
        symbol: getInstrumentTicker(position),
        ticker: getInstrumentTicker(position),
        name: getInstrumentDisplayName(position),
        quantity,
        avgPrice,
        currentPrice,
        marketValue,
        costBasis,
        profit,
        profitPercent,
        sector: getInstrumentSector(position),
        instrument_type: position.instrument_type,
        currency: position.currency
      };
    });

    return {
      totalValue: apiData?.total_value || 0,
      cashBalance: apiData?.cash_balance || 0,
      totalStocksValue: apiData?.total_stocks_value || 0,
      totalProfit: apiData?.total_profit || 0,
      profitPercent: apiData?.total_profit_percent || 0,
      positionsCount: apiData?.positions_count ?? stockPositions.length,
      positions: processedPositions
    };
  }, []);

  const loadPortfolioData = useCallback(async (accountId = null) => {
    try {
      setLoading(true);
      setError(null);
      const response = await tradeAPI.getPortfolio(accountId);
      setPortfolioData(processPortfolioData(response.data));
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось загрузить данные портфеля'));
      setPortfolioData(EMPTY_PORTFOLIO_DATA);
    } finally {
      setLoading(false);
    }
  }, [processPortfolioData]);

  useEffect(() => {
    if (autoLoad) {
      loadPortfolioData();
    }
  }, [autoLoad, loadPortfolioData]);

  const memoizedData = useMemo(() => portfolioData, [portfolioData]);

  return {
    portfolioData: memoizedData,
    loading,
    error,
    loadPortfolioData,
    formatCurrency: formatMoney
  };
};
