"use client";

import { useEffect, useRef, useState } from "react";
import api from "../utils/api";

const getWsUrl = (path) => {
  const base = api.defaults?.baseURL || "http://localhost:8000";
  const url = new URL(path, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
};

/**
 * 보유 종목 전체에 대해 백그라운드 WebSocket을 열어 실시간 가격을 구독합니다.
 * holdingSymbols: 콤마 구분 정렬 문자열, e.g. "AAPL,NVDA,TSLA"
 */
export function useBackgroundPrices(holdingSymbols, enabled = true) {
  const [priceBySymbol, setPriceBySymbol] = useState({});
  const socketsRef = useRef({});

  useEffect(() => {
    if (typeof WebSocket === "undefined") return;

    // Close all existing connections before rebuilding
    for (const ws of Object.values(socketsRef.current)) {
      try { ws.close(); } catch {}
    }
    socketsRef.current = {};

    if (!enabled || !holdingSymbols) {
      setPriceBySymbol({});
      return;
    }

    const symbols = holdingSymbols.split(",").filter(Boolean);

    for (const sym of symbols) {
      const ws = new WebSocket(getWsUrl(`/api/chart/ws/${sym}`));
      socketsRef.current[sym] = ws;

      ws.onmessage = (event) => {
        let payload;
        try { payload = JSON.parse(event.data); } catch { return; }
        if (payload?.type !== "tick") return;
        const price = Number(payload.row?.close ?? payload.price);
        if (!Number.isFinite(price) || price <= 0) return;
        setPriceBySymbol((prev) => {
          if (prev[sym] === price) return prev;
          return { ...prev, [sym]: price };
        });
      };

      ws.onerror = () => { delete socketsRef.current[sym]; };
      ws.onclose = () => { delete socketsRef.current[sym]; };
    }

    return () => {
      for (const ws of Object.values(socketsRef.current)) {
        try { ws.close(); } catch {}
      }
      socketsRef.current = {};
    };
  }, [holdingSymbols, enabled]);

  return priceBySymbol;
}
