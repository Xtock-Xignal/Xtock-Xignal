"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../utils/api";
import {
  defaultValuationDateRange,
  filterActiveHoldings,
} from "../utils/simulationPortfolio";

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
    const { start, end } = defaultValuationDateRange();
    let cancelled = false;

    (async () => {
      const next = {};
      await Promise.all(
        symbols.map(async (symbol) => {
          try {
            const res = await api.post("/api/recent-status", {
              text: symbol,
              start_date: start,
              end_date: end,
            });
            const series = res?.data?.stock_data || [];
            const last = series.length ? series[series.length - 1] : null;
            next[symbol] = Number(last?.close || 0);
          } catch (e) {
            console.error(`Failed to load valuation price for ${symbol}`, e);
            next[symbol] = 0;
          }
        })
      );
      if (!cancelled) setLatestPriceBySymbol(next);
    })();

    return () => {
      cancelled = true;
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
