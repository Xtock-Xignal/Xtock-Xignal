import { describe, expect, it } from "vitest";

import { calculateOrderAmounts, computeSimulationMetrics } from "./simulationPortfolio";

describe("simulationPortfolio utilities", () => {
  it("includes trading fees in buy cost and sell proceeds", () => {
    const amounts = calculateOrderAmounts(2, 123);

    expect(amounts.grossAmount).toBe(246);
    expect(amounts.fee).toBe(0.12);
    expect(amounts.buyCost).toBe(246.12);
    expect(amounts.sellProceeds).toBe(245.88);
  });

  it("combines realized and unrealized pnl consistently", () => {
    const metrics = computeSimulationMetrics(
      1000,
      {
        AAPL: { shares: 2, avgCost: 100, realizedPnl: 15 },
      },
      () => 110
    );

    expect(metrics.portfolioMarketValue).toBe(220);
    expect(metrics.realizedPnl).toBe(15);
    expect(metrics.unrealizedPnl).toBe(20);
    expect(metrics.totalPnl).toBe(35);
    expect(metrics.totalValue).toBe(1220);
  });
});
