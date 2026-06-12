export const filterActiveHoldings = (holdings) =>
  Object.entries(holdings || {}).filter(([, h]) => (Number(h?.shares) || 0) > 0);

export const TRADE_FEE_RATE = 0.0005;

export const calculateTradeFee = (amount) => {
  const n = Number(amount);
  if (!Number.isFinite(n) || n <= 0) return 0;
  return Math.round(n * TRADE_FEE_RATE * 100) / 100;
};

export const calculateOrderAmounts = (shares, price) => {
  const quantity = Math.max(0, Math.floor(Number(shares) || 0));
  const unitPrice = Math.max(0, Number(price) || 0);
  const grossAmount = quantity * unitPrice;
  const fee = calculateTradeFee(grossAmount);

  return {
    quantity,
    grossAmount,
    fee,
    buyCost: grossAmount + fee,
    sellProceeds: Math.max(0, grossAmount - fee),
  };
};

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
