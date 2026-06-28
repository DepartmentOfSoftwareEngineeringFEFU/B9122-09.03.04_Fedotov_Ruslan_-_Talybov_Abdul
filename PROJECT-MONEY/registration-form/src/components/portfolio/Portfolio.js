// src/components/portfolio/Portfolio.js
import React, { useState, useEffect } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { usePortfolio } from '../../hooks/usePortfolio';
import { tradeAPI, getErrorMessage } from '../../services/api';
import { clampNumber, sanitizeNumberInput } from '../../utils/numberInput';
import ConfirmDialog from '../common/ConfirmDialog';
import { formatShortId } from '../../utils/formatters';
import { getInstrumentDisplayName, getInstrumentTicker } from '../../utils/instruments';
import LoadingSpinner, { ButtonLoader } from '../common/LoadingSpinner';

const SELECTED_ACCOUNT_STORAGE_KEY = 'trade.selected_account_id';

function getStoredAccountId() {
  try {
    return window.localStorage.getItem(SELECTED_ACCOUNT_STORAGE_KEY) || '';
  } catch (_error) {
    return '';
  }
}

function storeAccountId(accountId) {
  try {
    if (accountId) {
      window.localStorage.setItem(SELECTED_ACCOUNT_STORAGE_KEY, accountId);
    } else {
      window.localStorage.removeItem(SELECTED_ACCOUNT_STORAGE_KEY);
    }
  } catch (_error) {
    // Ignore unavailable localStorage; account selection still works in memory.
  }
}

export default function Portfolio() {
  const { portfolioData, loading, error, loadPortfolioData, formatCurrency } = usePortfolio(false);
  const { isDark } = useTheme();
  const [sandboxLoading, setSandboxLoading] = useState(false);
  const [sandboxMessage, setSandboxMessage] = useState('');
  const [userAccounts, setUserAccounts] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [showAmountInput, setShowAmountInput] = useState(false);
  const [amount, setAmount] = useState('100000');
  const [accountBalance, setAccountBalance] = useState(null);
  const [pendingCloseAccount, setPendingCloseAccount] = useState(null);

  const normalizeAccountStatus = (status) => {
    const rawStatus = String(status ?? '').toUpperCase();
    if (rawStatus.includes('ACCOUNT_STATUS_OPEN') || rawStatus === '2' || rawStatus === 'OPEN') {
      return 'open';
    }
    if (rawStatus.includes('ACCOUNT_STATUS_CLOSED') || rawStatus === '3' || rawStatus === 'CLOSED') {
      return 'closed';
    }
    return 'unknown';
  };

  const isOpenAccount = (account) => normalizeAccountStatus(account?.status) !== 'closed';

  // Загружаем список счетов при монтировании компонента
  useEffect(() => {
    loadUserAccounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Загружаем баланс при выборе счета
  useEffect(() => {
    if (selectedAccount) {
      loadAccountBalance(selectedAccount.id);
      loadPortfolioData(selectedAccount.id); // Передаем account_id в хук
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAccount]);

  const loadUserAccounts = async () => {
    setAccountsLoading(true);
    try {
      const response = await tradeAPI.getAccounts();

      const accounts = (response.data.accounts || []).map((account) => {
        const normalizedStatus = normalizeAccountStatus(account?.status);
        return {
          ...account,
          status: normalizedStatus === 'closed' ? 'ACCOUNT_STATUS_CLOSED' : 'ACCOUNT_STATUS_OPEN',
        };
      });

      setUserAccounts(accounts);

      const storedAccountId = getStoredAccountId();
      const openAccount = accounts.find((account) => isOpenAccount(account) && account.id === storedAccountId)
        || accounts.find(isOpenAccount);
      if (openAccount && (!selectedAccount || !isOpenAccount(selectedAccount))) {
        setSelectedAccount(openAccount);
        storeAccountId(openAccount.id);
      } else if (!openAccount) {
        setSelectedAccount(null);
        setAccountBalance(null);
        storeAccountId('');
      }

    } catch (error) {
      console.error('Ошибка загрузки счетов:', error);
      setUserAccounts([]);
    } finally {
      setAccountsLoading(false);
    }
  };

  const loadAccountBalance = async (accountId) => {
    try {
      const response = await tradeAPI.getAccountBalance(accountId);
      setAccountBalance(response.data.balance);
    } catch (error) {
      console.error('Ошибка загрузки баланса:', error);
    }
  };

  const handleAccountSelect = (account) => {
    if (!isOpenAccount(account)) {
      setSandboxMessage('Этот sandbox-счет закрыт. Создайте или выберите открытый счет.');
      return;
    }
    setSelectedAccount(account);
    storeAccountId(account.id);
    setSandboxMessage(`Выбран счет: ${formatShortId(account.id)}`);
  };

  const handleOpenSandboxAccount = async () => {
    setSandboxLoading(true);
    setSandboxMessage('');
    try {
      const response = await tradeAPI.openSandboxAccount("ACCOUNT_TYPE_TINKOFF");
      setSandboxMessage(`${response.data.message || 'Счет в песочнице успешно создан!'}`);

      // Обновляем список счетов
      setTimeout(() => {
        loadUserAccounts();
      }, 1000);
    } catch (error) {
      console.error('Ошибка создания счета:', error);
      setSandboxMessage(getErrorMessage(error, 'Не удалось создать счёт в песочнице. Повторите попытку позже.'));
    } finally {
      setSandboxLoading(false);
    }
  };

  const handleSandboxPayIn = async () => {
    if (!selectedAccount) {
      setSandboxMessage('Сначала выберите счет для пополнения');
      return;
    }
    setShowAmountInput(true);
  };

  const handleConfirmAmount = async () => {
    if (!amount || isNaN(amount) || parseFloat(amount) <= 0) {
      setSandboxMessage('Введите корректную сумму');
      setShowAmountInput(false);
      return;
    }

    setShowAmountInput(false);
    await processPayIn(selectedAccount.id, clampNumber(amount, { min: 1, max: 1000000000 }));
  };

  const processPayIn = async (accountId, amount) => {
    setSandboxLoading(true);
    setSandboxMessage('');
    try {
      const response = await tradeAPI.sandboxPayIn(accountId, amount, "RUB");
      setSandboxMessage(`${response.data.message || `Счет пополнен на ${amount} рублей!`}`);

      // Перезагружаем баланс и портфель
      setTimeout(() => {
        loadAccountBalance(accountId);
        loadPortfolioData(accountId);
      }, 1000);
    } catch (error) {
      console.error('Ошибка пополнения счета:', error);
      setSandboxMessage(getErrorMessage(error, 'Не удалось пополнить счёт. Проверьте сумму и повторите попытку.'));
    } finally {
      setSandboxLoading(false);
    }
  };

  const handleCloseAccount = (accountId) => {
    setPendingCloseAccount(accountId);
  };

  const confirmCloseAccount = async () => {
    const accountId = pendingCloseAccount;
    if (!accountId) return;

    setSandboxLoading(true);
    setPendingCloseAccount(null);
    try {
      await tradeAPI.closeAccount(accountId);
      setSandboxMessage('Счет успешно закрыт');

      setTimeout(() => {
        loadUserAccounts();
        if (selectedAccount?.id === accountId) {
          setSelectedAccount(null);
          setAccountBalance(null);
          storeAccountId('');
        }
      }, 1000);
    } catch (error) {
      console.error('Ошибка закрытия счета:', error);
      setSandboxMessage(getErrorMessage(error, 'Не удалось закрыть счёт. Повторите попытку позже.'));
    } finally {
      setSandboxLoading(false);
    }
  };

  if (loading) {
    return <LoadingSpinner label="Собираем портфель..." />;
  }

  return (
    <div className="space-y-6">

      <ConfirmDialog
        open={Boolean(pendingCloseAccount)}
        title="Закрыть sandbox-счёт?"
        description={pendingCloseAccount ? `Счёт ${formatShortId(pendingCloseAccount)} будет закрыт. Действие нельзя отменить.` : ''}
        confirmLabel="Закрыть"
        cancelLabel="Отмена"
        danger
        loading={sandboxLoading}
        onConfirm={confirmCloseAccount}
        onCancel={() => setPendingCloseAccount(null)}
      />

      {/* Модальное окно ввода суммы */}
      {showAmountInput && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4" role="presentation">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="payin-dialog-title"
            className={`w-full max-w-md rounded-3xl border p-6 shadow-2xl ${
              isDark ? 'border-zinc-800 bg-[#111111]' : 'border-gray-200 bg-white'
            }`}
          >
            <h3 id="payin-dialog-title" className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              Пополнение счета
            </h3>
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-zinc-300 mb-2">
                Введите сумму пополнения (рубли):
              </label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(sanitizeNumberInput(e.target.value, { min: 1, max: 1000000000, integer: false, maxLength: 12 }))}
                className={`w-full px-4 py-3 rounded-2xl border ${
                  isDark
                    ? 'bg-gray-700 border-gray-600 text-white'
                    : 'bg-white border-gray-300 text-gray-900'
                } focus:outline-none focus:ring-2 focus:ring-yellow-400`}
                placeholder="100000"
                min="1"
                max="1000000000"
                step="1000"
              />
            </div>
            <div className="flex space-x-3">
              <button
                type="button"
                onClick={handleConfirmAmount}
                className={`flex-1 py-3 rounded-2xl font-semibold text-white bg-yellow-400 hover:bg-yellow-300 transition-all duration-300 ${
                  isDark ? 'hover:shadow-lg' : 'hover:shadow-md'
                }`}
              >
                Пополнить
              </button>
              <button
                type="button"
                onClick={() => setShowAmountInput(false)}
                className={`flex-1 py-3 rounded-2xl font-medium ${
                  isDark
                    ? 'bg-gray-600 hover:bg-gray-500 text-white'
                    : 'bg-gray-200 hover:bg-gray-300 text-gray-900'
                }`}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Шапка с выбором счета */}
      <div className="app-card rounded-3xl p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Портфель</h1>
            <p className="mt-1 text-sm text-gray-600 dark:text-zinc-500">
              {selectedAccount
                ? `Счет: ${formatShortId(selectedAccount.id)}`
                : 'Выберите счет для просмотра'
              }
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 lg:justify-end">
            <button
              onClick={handleOpenSandboxAccount}
              disabled={sandboxLoading}
              className="app-primary-button h-10 inline-flex items-center justify-center rounded-2xl px-4 text-sm transition-all duration-300 disabled:opacity-50"
            >
              {sandboxLoading ? <ButtonLoader label="Создаем..." dark /> : 'Создать счет'}
            </button>
            <button
              onClick={handleSandboxPayIn}
              disabled={sandboxLoading || !selectedAccount}
              className="app-secondary-button h-10 inline-flex items-center justify-center rounded-2xl px-4 text-sm font-semibold transition-all duration-300 disabled:opacity-50"
            >
              {sandboxLoading ? <ButtonLoader label="Пополняем..." /> : 'Пополнить счет'}
            </button>
            <button
              onClick={() => selectedAccount && loadPortfolioData(selectedAccount.id)}
              disabled={!selectedAccount || sandboxLoading}
              className="h-10 inline-flex items-center justify-center rounded-2xl border border-yellow-400/12 bg-transparent px-4 text-sm font-semibold text-zinc-300 transition-all duration-300 hover:border-yellow-400/35 hover:bg-[#1b170f] hover:text-white disabled:opacity-50"
            >
              Обновить
            </button>
          </div>
        </div>
      </div>

      {/* Блок выбора счета */}
      <div className={`rounded-3xl p-6 shadow-lg ${
        isDark
          ? 'bg-[#11100d] border border-yellow-400/10'
          : 'bg-white border border-gray-200'
      }`}>
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Выбор счета
            </h3>
            <p className="text-sm text-gray-600 dark:text-zinc-500 mt-1">
              Активный sandbox-счет для портфеля и операций
            </p>
          </div>
          {selectedAccount && (
            <span className="shrink-0 rounded-full border border-yellow-400/20 bg-yellow-400/10 px-3 py-1 text-xs font-semibold text-yellow-300">
              выбран
            </span>
          )}
        </div>

        {accountsLoading ? (
          <LoadingSpinner label="Загружаем счета..." compact />
        ) : userAccounts.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {userAccounts.map((account) => {
              const isSelected = selectedAccount?.id === account.id;
              const isOpen = isOpenAccount(account);

              return (
                <div
                  key={account.id}
                  className={`group relative overflow-hidden rounded-3xl border cursor-pointer transition-all duration-200 ${
                    isSelected
                      ? isDark
                        ? 'border-yellow-400/70 bg-yellow-400/[0.07] shadow-[0_0_0_1px_rgba(250,204,21,0.16)]'
                        : 'border-blue-500 bg-blue-50'
                      : !isOpen
                        ? isDark
                          ? 'border-red-500/10 bg-[#171111] opacity-70'
                          : 'border-red-100 bg-red-50 opacity-80'
                      : isDark
                        ? 'border-yellow-400/10 bg-[#18150f] hover:border-yellow-400/35 hover:bg-[#1d1a12]'
                        : 'border-gray-200 bg-gray-50 hover:border-gray-300'
                  }`}
                  onClick={() => handleAccountSelect(account)}
                >
                  <div className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full bg-yellow-400/10 blur-2xl" />
                  <div className="relative p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs uppercase tracking-[0.24em] text-gray-500 dark:text-zinc-500">Sandbox</p>
                        <h4 className="mt-1 truncate font-semibold text-gray-900 dark:text-white">
                          {account.name || 'Торговый счет'}
                        </h4>
                      </div>
                      <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${
                        isOpen
                          ? isDark ? 'bg-green-500/15 text-green-400' : 'bg-green-100 text-green-700'
                          : isDark ? 'bg-red-500/15 text-red-400' : 'bg-red-100 text-red-700'
                      }`}>
                        {account.status === 'ACCOUNT_STATUS_OPEN' ? 'Открыт' : 'Закрыт'}
                      </span>
                    </div>

                    <div className="mt-4 rounded-2xl border border-white/5 bg-black/20 px-3 py-3">
                      <p className="text-xs text-gray-500 dark:text-zinc-500">ID счета</p>
                      <p className="mt-1 break-all font-mono text-sm text-gray-800 dark:text-zinc-200">
                        {account.id}
                      </p>
                    </div>

                    <div className="mt-4 flex items-center justify-between gap-3">
                      <span className={`rounded-full px-3 py-1 text-xs ${
                        isDark ? 'bg-black/25 text-zinc-400' : 'bg-gray-200 text-gray-700'
                      }`}>
                        {account.type || 'Песочница'}
                      </span>
                      {isSelected && isOpen && (
                        <span className="inline-flex items-center gap-2 text-xs font-semibold text-yellow-300">
                          <span className="h-2 w-2 rounded-full bg-yellow-400" />
                          активен
                        </span>
                      )}
                    </div>

                    {isSelected && isOpen && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCloseAccount(account.id);
                        }}
                        className="mt-4 h-9 w-full rounded-xl border border-red-500/20 text-xs font-semibold text-red-400 hover:bg-red-500/10 transition-colors"
                      >
                        Закрыть счет
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className={`text-center py-6 rounded-2xl ${
            isDark ? 'bg-gray-700/50' : 'bg-gray-50'
          }`}>
            <p className="text-gray-600 dark:text-zinc-500 mb-4">
              Нет доступных счетов
            </p>
            <button
              onClick={handleOpenSandboxAccount}
              className={`px-4 py-2 rounded-2xl font-semibold ${
                isDark
                  ? 'bg-yellow-400 text-black hover:bg-yellow-300'
                  : 'bg-yellow-400 hover:bg-yellow-300 text-black'
              }`}
            >
              Создать первый счет
            </button>
          </div>
        )}
      </div>

      {/* Информация о балансе выбранного счета */}
      {selectedAccount && accountBalance && (
        <div className={`rounded-2xl p-6 ${
          isDark ? 'bg-gray-800 border border-gray-700' : 'bg-white border border-gray-200 shadow-lg'
        }`}>
          <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
            Баланс счета
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className={`p-4 rounded-2xl ${
              isDark ? 'bg-gray-700' : 'bg-blue-50'
            }`}>
              <p className="text-sm text-gray-600 dark:text-zinc-500">Общая сумма</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {formatCurrency(accountBalance.total_amount || 0)} ₽
              </p>
            </div>
            <div className={`p-4 rounded-2xl ${
              isDark ? 'bg-gray-700' : 'bg-green-50'
            }`}>
              <p className="text-sm text-gray-600 dark:text-zinc-500">Доступно</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {formatCurrency(accountBalance.available_amount || 0)} ₽
              </p>
            </div>
            <div className={`p-4 rounded-2xl ${
              isDark ? 'bg-gray-700' : 'bg-purple-50'
            }`}>
              <p className="text-sm text-gray-600 dark:text-zinc-500">Валюта</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {accountBalance.currency || 'RUB'}
              </p>
            </div>
          </div>
        </div>
      )}

      {sandboxMessage && (
        <div className={`p-4 rounded-2xl ${
          sandboxMessage.toLowerCase().includes('ошибка') || sandboxMessage.toLowerCase().includes('сначала') || sandboxMessage.toLowerCase().includes('введите')
            ? 'bg-red-100 border border-red-300 text-red-700 dark:bg-red-900 dark:border-red-700 dark:text-red-200'
            : 'bg-green-100 border border-green-300 text-green-700 dark:bg-green-900 dark:border-green-700 dark:text-green-200'
        }`}>
          {sandboxMessage}
        </div>
      )}

      {error && (
        <div className={`rounded-2xl p-4 border ${
          isDark ? 'bg-red-500/10 border-red-500/30 text-red-300' : 'bg-red-50 border-red-200 text-red-700'
        }`}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center">
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => loadPortfolioData(selectedAccount?.id || null)}
              className="rounded-xl border border-current px-3 py-2 text-sm font-semibold hover:bg-white/10"
            >
              Повторить
            </button>
          </div>
        </div>
      )}

      {/* Основная информация о портфеле */}
      {selectedAccount ? (
        <>
          <PortfolioSummary portfolioData={portfolioData} isDark={isDark} formatCurrency={formatCurrency} />
          <CashBalance cashBalance={portfolioData?.cashBalance} isDark={isDark} formatCurrency={formatCurrency} />
          <PortfolioDetails positions={portfolioData?.positions} isDark={isDark} formatCurrency={formatCurrency} />
        </>
      ) : (
        <div className={`rounded-2xl p-8 text-center ${
          isDark ? 'bg-gray-800 border border-gray-700' : 'bg-white border border-gray-200 shadow-lg'
        }`}>
          <div className={`w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center ${
            isDark ? 'bg-gray-700' : 'bg-gray-100'
          }`}>
            <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <h4 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Выберите счет для просмотра портфеля
          </h4>
          <p className="text-gray-600 dark:text-zinc-500">
            Выберите счет из списка выше, чтобы увидеть детальную информацию о ваших инвестициях
          </p>
        </div>
      )}
    </div>
  );
}

// Остальные компоненты (PortfolioSummary, CashBalance, PortfolioDetails и т.д.) остаются без изменений
// ... (они такие же как в предыдущем коде)
const PortfolioSummary = React.memo(({ portfolioData, isDark, formatCurrency }) => (
  <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
    <SummaryCard
      title="Общая стоимость"
      value={`${formatCurrency(portfolioData?.totalValue || 0)} ₽`}
      subtitle="Включая наличные"
      isDark={isDark}
    />
    <SummaryCard
      title="Общая прибыль"
      value={`${portfolioData?.totalProfit >= 0 ? '+' : ''}${formatCurrency(portfolioData?.totalProfit || 0)} ₽`}
      subtitle="По акциям"
      isDark={isDark}
      isProfit
    />
    <SummaryCard
      title="Доходность"
      value={`${portfolioData?.profitPercent >= 0 ? '+' : ''}${(portfolioData?.profitPercent || 0).toFixed(2)}%`}
      subtitle="По акциям"
      isDark={isDark}
      isProfit
    />
    <SummaryCard
      title="Акций в портфеле"
      value={portfolioData?.positionsCount || 0}
      subtitle="Позиции"
      isDark={isDark}
    />
  </div>
));

const SummaryCard = React.memo(({ title, value, subtitle, isDark, isProfit }) => (
  <div className="bg-white dark:bg-[#111111] rounded-3xl shadow-lg border border-gray-200 dark:border-zinc-800 p-6">
    <p className="text-sm font-medium text-gray-600 dark:text-zinc-500">{title}</p>
    <p className={`text-2xl font-bold mt-1 ${
      isProfit
        ? (typeof value === 'string' && value.includes('+')
            ? 'text-green-600 dark:text-green-400'
            : 'text-red-600 dark:text-red-400')
        : 'text-gray-900 dark:text-white'
    }`}>
      {value}
    </p>
    <p className="text-xs text-gray-500 dark:text-zinc-500 mt-1">{subtitle}</p>
  </div>
));

const CashBalance = React.memo(({ cashBalance, isDark, formatCurrency }) => (
  <div className="bg-white dark:bg-[#111111] rounded-3xl shadow-lg border border-gray-200 dark:border-zinc-800 p-6">
    <h3 className="text-lg font-semibold text-gray-800 dark:text-white mb-4">Наличные средства</h3>
    <div className="rounded-2xl border border-gray-200 dark:border-yellow-400/10 bg-gray-50 dark:bg-[#18150f] px-5 py-4">
      <p className="text-sm text-gray-600 dark:text-zinc-500">Доступно для инвестиций</p>
      <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
        {formatCurrency(cashBalance || 0)} ₽
      </p>
    </div>
  </div>
));

const PortfolioDetails = React.memo(({ positions, isDark, formatCurrency }) => (
  <div className="bg-white dark:bg-[#111111] rounded-3xl shadow-lg border border-gray-200 dark:border-zinc-800 overflow-hidden">
    <div className="px-6 py-4 border-b border-gray-200 dark:border-zinc-800 flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-center">
      <h3 className="text-xl font-semibold text-gray-800 dark:text-white">Акции в портфеле</h3>
      <span className="text-sm text-gray-500 dark:text-zinc-500">
        Обновлено: {new Date().toLocaleTimeString('ru-RU')}
      </span>
    </div>
    <div className="overflow-x-auto">
      {positions && positions.length > 0 ? (
        <table className="w-full min-w-[1180px] table-fixed">
          <colgroup>
            <col className="w-[250px]" />
            <col className="w-[130px]" />
            <col className="w-[155px]" />
            <col className="w-[155px]" />
            <col className="w-[190px]" />
            <col className="w-[220px]" />
            <col className="w-[180px]" />
          </colgroup>
          <thead>
            <tr className={`border-b border-gray-200 dark:border-zinc-800 ${
              isDark ? 'bg-[#18150f]' : 'bg-gray-50'
            }`}>
              <th className="text-left py-4 px-5 text-sm font-medium text-gray-600 dark:text-zinc-500">Актив</th>
              <th className="text-left py-4 px-5 text-sm font-medium text-gray-600 dark:text-zinc-500">Количество</th>
              <th className="text-left py-4 px-5 text-sm font-medium text-gray-600 dark:text-zinc-500">Средняя цена</th>
              <th className="text-left py-4 px-5 text-sm font-medium text-gray-600 dark:text-zinc-500">Текущая цена</th>
              <th className="text-left py-4 px-5 text-sm font-medium text-gray-600 dark:text-zinc-500">Рыночная стоимость</th>
              <th className="text-left py-4 px-5 text-sm font-medium text-gray-600 dark:text-zinc-500">Прибыль</th>
              <th className="text-left py-4 px-5 text-sm font-medium text-gray-600 dark:text-zinc-500">Сектор</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position, index) => (
              <PortfolioRow
                key={`${position.figi}-${index}`}
                position={position}
                isDark={isDark}
                formatCurrency={formatCurrency}
              />
            ))}
          </tbody>
        </table>
      ) : (
        <EmptyPortfolio isDark={isDark} />
      )}
    </div>
  </div>
));

const PortfolioRow = React.memo(({ position, isDark, formatCurrency }) => {
  const ticker = getInstrumentTicker(position);
  const displayName = getInstrumentDisplayName(position);
  const figi = position.figi || position.symbol || '—';

  return (
    <tr className={`border-b border-gray-200 dark:border-zinc-800 hover:${
      isDark ? 'bg-yellow-400/[0.03]' : 'bg-gray-50'
    } transition-colors duration-200`}>
      <td className="py-4 px-5 align-middle">
        <div className="flex min-w-0 items-center gap-3">
          <div className={`h-11 w-11 shrink-0 rounded-2xl flex items-center justify-center border ${
            position.profit >= 0
              ? (isDark ? 'bg-green-500/10 border-green-500/15' : 'bg-green-100 border-green-200')
              : (isDark ? 'bg-red-500/10 border-red-500/15' : 'bg-red-100 border-red-200')
          }`}>
            <span className={`max-w-[38px] truncate text-xs font-bold ${
              position.profit >= 0
                ? (isDark ? 'text-green-400' : 'text-green-600')
                : (isDark ? 'text-red-400' : 'text-red-600')
            }`}>
              {ticker}
            </span>
          </div>
          <div className="min-w-0">
            <p className="truncate font-semibold text-gray-800 dark:text-white">{displayName}</p>
            <p className="mt-0.5 break-all font-mono text-xs text-gray-600 dark:text-zinc-500">{figi}</p>
          </div>
        </div>
      </td>
      <td className="py-4 px-5 whitespace-nowrap text-gray-800 dark:text-white">
        {position.quantity.toLocaleString('ru-RU')} шт
      </td>
      <td className="py-4 px-5 whitespace-nowrap text-gray-800 dark:text-white">
        {formatCurrency(position.avgPrice)} ₽
      </td>
      <td className="py-4 px-5 whitespace-nowrap text-gray-800 dark:text-white">
        {formatCurrency(position.currentPrice)} ₽
      </td>
      <td className="py-4 px-5 whitespace-nowrap text-gray-800 dark:text-white">
        {formatCurrency(position.marketValue)} ₽
      </td>
      <td className="py-4 px-5">
        <div className={`inline-flex max-w-full items-center rounded-full px-3 py-1 text-sm font-medium ${
          position.profit >= 0
            ? (isDark ? 'bg-green-500/15 text-green-400' : 'bg-green-100 text-green-700')
            : (isDark ? 'bg-red-500/15 text-red-400' : 'bg-red-100 text-red-700')
        }`}>
          <span className="truncate">
            {position.profit >= 0 ? '+' : ''}{formatCurrency(position.profit)} ₽
            {' '}({position.profitPercent >= 0 ? '+' : ''}{position.profitPercent.toFixed(2)}%)
          </span>
        </div>
      </td>
      <td className="py-4 px-5">
        <span className={`inline-flex max-w-full items-center rounded-full px-3 py-1 text-sm font-medium ${
          isDark ? 'bg-yellow-400/10 text-yellow-300' : 'bg-blue-100 text-blue-700'
        }`}>
          <span className="truncate">{position.sector}</span>
        </span>
      </td>
    </tr>
  );
});

const EmptyPortfolio = React.memo(({ isDark }) => (
  <div className="text-center py-12">
    <div className={`w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center ${
      isDark ? 'bg-gray-700' : 'bg-gray-100'
    }`}>
      <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    </div>
    <h4 className="text-lg font-medium text-gray-900 dark:text-white mb-2">Портфель пуст</h4>
    <p className="text-gray-600 dark:text-zinc-500 max-w-sm mx-auto">
      Начните инвестировать, чтобы увидеть свои позиции здесь.
      Используйте раздел "Торговля" для покупки акций.
    </p>
  </div>
));
