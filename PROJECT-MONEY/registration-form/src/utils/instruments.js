const FALLBACK_MOEX_SHARE_SEED = [
  { figi: 'BBG004730N88', symbol: 'SBER', name: 'Сбербанк', sector: 'Финансы' },
  { figi: 'BBG004730RP0', symbol: 'GAZP', name: 'Газпром', sector: 'Энергетика' },
  { figi: 'BBG00475JZZ6', symbol: 'LKOH', name: 'Лукойл', sector: 'Энергетика' },
  { figi: 'BBG006L8G4H1', symbol: 'YNDX', name: 'Яндекс', sector: 'Технологии' },
  { figi: 'BBG004S681W1', symbol: 'VTBR', name: 'ВТБ', sector: 'Финансы' },
  { figi: 'BBG00475K2X9', symbol: 'ROSN', name: 'Роснефть', sector: 'Энергетика' },
  { figi: 'BBG004S68B31', symbol: 'ALRS', name: 'АЛРОСА', sector: 'Добыча' },
  { figi: 'BBG004RVFCY3', symbol: 'MGNT', name: 'Магнит', sector: 'Потребительские товары' },
  { figi: 'BBG004S683W7', symbol: 'TATN', name: 'Татнефть', sector: 'Энергетика' },
  { figi: 'BBG00475J7C8', symbol: 'MOEX', name: 'Московская биржа', sector: 'Финансы' },
  { figi: 'BBG004S68758', symbol: 'NLMK', name: 'НЛМК', sector: 'Металлургия' },
  { figi: 'BBG00475K6C4', symbol: 'GMKN', name: 'Норникель', sector: 'Добыча' },
  { figi: 'BBG004S681B4', symbol: 'MTSS', name: 'МТС', sector: 'Телеком' },
  { figi: 'BBG004S68507', symbol: 'AFKS', name: 'Система', sector: 'Холдинги' },
  { figi: 'BBG00475KKY8', symbol: 'PLZL', name: 'Полюс', sector: 'Добыча' },
];

const EXTRA_INSTRUMENT_METADATA = [
  { figi: 'BBG004731032', symbol: 'LKOH', name: 'Лукойл', sector: 'Энергетика' },
  { figi: 'BBG004731489', symbol: 'GMKN', name: 'Норникель', sector: 'Добыча' },
  { figi: 'BBG004731354', symbol: 'ROSN', name: 'Роснефть', sector: 'Энергетика' },
  { figi: 'BBG004730ZJ9', symbol: 'VTBR', name: 'ВТБ', sector: 'Финансы' },
  { figi: 'BBG000R607Y3', symbol: 'PLZL', name: 'Полюс', sector: 'Добыча' },
  { figi: 'BBG00475KKY8', symbol: 'NVTK', name: 'Новатэк', sector: 'Энергетика' },
  { figi: 'BBG004S689R0', symbol: 'PHOR', name: 'ФосАгро', sector: 'Химия' },
  { figi: 'BBG004S681M2', symbol: 'SNGSP', name: 'Сургутнефтегаз ап', sector: 'Энергетика' },
  { figi: 'BBG004S681W1', symbol: 'SNGSP', name: 'Сургутнефтегаз ап', sector: 'Энергетика' },
  { figi: 'BBG0047315D0', symbol: 'SNGS', name: 'Сургутнефтегаз', sector: 'Энергетика' },
  { figi: 'BBG004S68473', symbol: 'SIBN', name: 'Газпром нефть', sector: 'Энергетика' },
  { figi: 'BBG004S684M6', symbol: 'SIBN', name: 'Газпром нефть', sector: 'Энергетика' },
  { figi: 'BBG00475K6C3', symbol: 'CHMF', name: 'Северсталь', sector: 'Металлургия' },
  { figi: 'BBG004S68507', symbol: 'MAGN', name: 'ММК', sector: 'Металлургия' },
  { figi: 'BBG004S68614', symbol: 'AFKS', name: 'Система', sector: 'Холдинги' },
  { figi: 'BBG004S68829', symbol: 'TATNP', name: 'Татнефть ап', sector: 'Энергетика' },
  { figi: 'BBG004730JJ5', symbol: 'MOEX', name: 'Московская биржа', sector: 'Финансы' },
  { figi: 'BBG009GSYN76', symbol: 'CBOM', name: 'МКБ', sector: 'Финансы' },
  { figi: 'BBG00475KHX6', symbol: 'TRNFP', name: 'Транснефть ап', sector: 'Энергетика' },
  { figi: 'BBG008F2T3T2', symbol: 'RUAL', name: 'Русал', sector: 'Металлургия' },
  { figi: 'RUB000UTSTOM', symbol: 'RUB', name: 'Наличные рубли', sector: 'Деньги' },
];

const normalizeCode = (value) => String(value || '').trim().toUpperCase();

export const normalizeInstrument = (instrument) => {
  const figi = normalizeCode(instrument?.figi);
  if (!figi) return null;

  const symbol = normalizeCode(instrument?.symbol || instrument?.ticker || figi);
  const ticker = normalizeCode(instrument?.ticker || instrument?.symbol || symbol);
  const name = String(instrument?.name || ticker || symbol || figi).trim();

  return {
    ...instrument,
    figi,
    ticker,
    symbol,
    name,
  };
};

export const normalizeInstrumentList = (items = []) => {
  const seen = new Set();
  return items
    .map(normalizeInstrument)
    .filter((instrument) => {
      if (!instrument || seen.has(instrument.figi)) return false;
      seen.add(instrument.figi);
      return true;
    })
    .sort((a, b) => a.symbol.localeCompare(b.symbol, 'ru'));
};

const INSTRUMENT_METADATA = normalizeInstrumentList([
  ...FALLBACK_MOEX_SHARE_SEED,
  ...EXTRA_INSTRUMENT_METADATA,
]);

const INSTRUMENT_BY_FIGI = INSTRUMENT_METADATA.reduce((acc, instrument) => {
  acc[instrument.figi] = instrument;
  return acc;
}, {});

const INSTRUMENT_BY_TICKER = INSTRUMENT_METADATA.reduce((acc, instrument) => {
  acc[instrument.ticker] = instrument;
  acc[instrument.symbol] = instrument;
  return acc;
}, {});

export const FALLBACK_MOEX_SHARES = normalizeInstrumentList(FALLBACK_MOEX_SHARE_SEED);

export const getInstrumentMetadata = (instrument = {}) => {
  const ticker = normalizeCode(instrument.ticker || instrument.symbol);
  const figi = normalizeCode(instrument.figi);
  return INSTRUMENT_BY_TICKER[ticker] || INSTRUMENT_BY_FIGI[figi] || null;
};

export const getInstrumentTicker = (instrument = {}) => {
  const ticker = normalizeCode(instrument.ticker || instrument.symbol);
  const figi = normalizeCode(instrument.figi);

  if (ticker && ticker !== figi && !ticker.startsWith('BBG')) {
    return ticker;
  }

  const metadata = getInstrumentMetadata(instrument);
  if (metadata?.ticker) return metadata.ticker;
  return figi ? figi.slice(0, 4) : '—';
};

export const getInstrumentDisplayName = (instrument = {}) => {
  const ticker = getInstrumentTicker(instrument);
  const figi = normalizeCode(instrument.figi);
  const rawName = String(instrument.name || instrument.instrument_name || '').trim();
  const metadata = getInstrumentMetadata(instrument);

  if (rawName && normalizeCode(rawName) !== ticker && normalizeCode(rawName) !== figi && !rawName.startsWith('BBG')) {
    return rawName;
  }

  return metadata?.name || ticker || figi || '—';
};

export const getInstrumentSector = (instrument = {}) => (
  getInstrumentMetadata(instrument)?.sector || instrument.sector || 'Другое'
);
