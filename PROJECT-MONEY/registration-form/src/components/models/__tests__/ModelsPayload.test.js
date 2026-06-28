import { withStoredAccountId } from '../accountScope';

test('forecast payload includes selected account id from storage', () => {
  window.localStorage.setItem('trade.selected_account_id', 'acc-new');

  expect(withStoredAccountId({ figi: 'BBG004730N88' })).toEqual({
    figi: 'BBG004730N88',
    account_id: 'acc-new',
  });
});

test('forecast payload is unchanged when no account is selected', () => {
  window.localStorage.removeItem('trade.selected_account_id');

  expect(withStoredAccountId({ figi: 'BBG004730N88' })).toEqual({
    figi: 'BBG004730N88',
  });
});
