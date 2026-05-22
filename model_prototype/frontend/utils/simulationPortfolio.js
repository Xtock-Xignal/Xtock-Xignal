export const toISODateInput = (d) => {
  const x = new Date(d);
  x.setHours(12, 0, 0, 0);
  return x.toISOString().slice(0, 10);
};

/** 시뮬레이션·포트폴리오 평가용 기본 조회 기간 (최근 100일) */
export const defaultValuationDateRange = () => {
  const end = new Date();
  end.setHours(12, 0, 0, 0);
  const start = new Date(end);
  start.setDate(start.getDate() - 99);
  return { start: toISODateInput(start), end: toISODateInput(end) };
};

export const filterActiveHoldings = (holdings) =>
  Object.entries(holdings || {}).filter(([, h]) => (Number(h?.shares) || 0) > 0);

/**
 * 가상 현금·계좌 총액·총 손익을 동일 규칙으로 계산합니다.
 * @param {number} cash
 * @param {Record<string, { shares, avgCost, realizedPnl }>} holdings
 * @param {(symbol: string) => number} getValuationPrice - 종목별 평가용 현재가
 */
export function computeSimulationMetrics(cash, holdings, getValuationPrice) {
  const holdingList = filterActiveHoldings(holdings);

  const portfolioMarketValue = holdingList.reduce((sum, [sym, h]) => {
    const px = getValuationPrice(sym);
    return sum + px * (Number(h.shares) || 0);
  }, 0);

  const realizedPnl = Object.values(holdings || {}).reduce(
    (sum, h) => sum + (Number(h.realizedPnl) || 0),
    0
  );

  const unrealizedPnl = holdingList.reduce((sum, [sym, h]) => {
    const px = getValuationPrice(sym);
    const shares = Number(h.shares) || 0;
    const avg = Number(h.avgCost) || 0;
    return sum + (px - avg) * shares;
  }, 0);

  const totalPnl = realizedPnl + unrealizedPnl;
  const totalValue = (Number(cash) || 0) + portfolioMarketValue;

  return {
    holdingList,
    portfolioMarketValue,
    realizedPnl,
    unrealizedPnl,
    totalPnl,
    totalValue,
  };
}
