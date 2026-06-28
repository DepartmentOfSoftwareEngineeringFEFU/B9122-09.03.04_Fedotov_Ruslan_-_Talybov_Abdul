import {
  getInstrumentDisplayName,
  getInstrumentSector,
  getInstrumentTicker,
} from './instruments';

test('resolves readable portfolio names for MOEX tickers', () => {
  expect(getInstrumentDisplayName({ figi: 'BBG004S681M2', ticker: 'SNGSP' })).toBe('Сургутнефтегаз ап');
  expect(getInstrumentDisplayName({ figi: 'BBG004S684M6', ticker: 'SIBN' })).toBe('Газпром нефть');
  expect(getInstrumentDisplayName({ figi: 'BBG000R607Y3', ticker: 'PLZL' })).toBe('Полюс');
});

test('keeps ticker for compact badges while using sector metadata', () => {
  const position = { figi: 'BBG004S681M2', ticker: 'SNGSP', name: 'SNGSP' };

  expect(getInstrumentTicker(position)).toBe('SNGSP');
  expect(getInstrumentDisplayName(position)).toBe('Сургутнефтегаз ап');
  expect(getInstrumentSector(position)).toBe('Энергетика');
});

test('replaces raw ticker names from portfolio rows', () => {
  expect(getInstrumentDisplayName({ figi: 'BBG004S684M6', symbol: 'SIBN', name: 'SIBN' })).toBe('Газпром нефть');
  expect(getInstrumentDisplayName({ figi: 'BBG000R607Y3', symbol: 'PLZL', name: 'PLZL' })).toBe('Полюс');
});
