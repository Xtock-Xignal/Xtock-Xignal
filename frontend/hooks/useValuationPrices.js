"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../utils/api";
import { filterActiveHoldings } from "../utils/simulationPortfolio";

/**
 * 보유 종목 평가용 최신 종가를 조회합니다. (시뮬레이션·포트폴리오 공통)
 */
export function useValuationPrices(holdings, enabled = true) {
  const [latestPriceBySymbol, setLatestPriceBySymbol] = useState({});

  const holdingList = useMemo(() => filterActiveHoldings(holdings), [holdings]);

  const holdingSymbols = useMemo(
    () => holdingList.map(([sym]) => sym).sort().join(","),
    [holdingList]
  );

  useEffect(() => {
    if (!enabled || !holdingSymbols) {
      const timeoutId = window.setTimeout(() => {
        setLatestPriceBySymbol({});
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }

    const symbols = holdingSymbols.split(",");
    let cancelled = false;

    const fetchPrices = async () => {
      const next = {};
      await Promise.all(
        symbols.map(async (symbol) => {
          try {
            const res = await api.get(`/api/chart/history/${symbol}`, {
              params: { period: "5d", interval: "1d" },
            });
            const rows = res?.data?.rows || [];
            const last = rows.length ? rows[rows.length - 1] : null;
            next[symbol] = Number(last?.close || 0);
          } catch (e) {
            console.error(`Failed to load valuation price for ${symbol}`, e);
            next[symbol] = 0;
          }
        })
      );
      if (!cancelled) setLatestPriceBySymbol(next);
    };

    fetchPrices();
    const intervalId = window.setInterval(fetchPrices, 10_000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [holdingSymbols, enabled]);

  const getValuationPrice = useCallback(
    (symbol) => {
      const px = latestPriceBySymbol[symbol];
      if (px > 0) return px;
      const h = holdings?.[symbol];
      return Number(h?.avgCost) || 0;
    },
    [latestPriceBySymbol, holdings]
  );

  return { holdingList, getValuationPrice, latestPriceBySymbol };
}
