export const SELECTED_ACCOUNT_STORAGE_KEY = 'trade.selected_account_id';

export function getStoredAccountId() {
  try {
    return window.localStorage.getItem(SELECTED_ACCOUNT_STORAGE_KEY) || '';
  } catch (_error) {
    return '';
  }
}

export function withStoredAccountId(payload) {
  const accountId = getStoredAccountId();
  return accountId ? { ...payload, account_id: accountId } : payload;
}
