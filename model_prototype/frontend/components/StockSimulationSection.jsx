"use client";

import { useCallback, useMemo, useState } from "react";
import api from "../utils/api";
import {
  ComposedChart,
  Line,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  useXAxisScale,
  useYAxisScale,
} from "recharts";
import { TrendingDown, TrendingUp } from "lucide-react";

const clamp = (v, min, max) => Math.min(max, Math.max(min, v));

const formatMoney = (n) => {
  const num = Number(n);
  if (Number.isNaN(num)) return "$0.00";
  return `$${num.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};

const formatVolumeAxis = (v) => {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return "0";
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return String(Math.round(n));
};

function enrichWithSma(rows) {
  if (!rows?.length) return [];
  const periods = [5, 20, 60];
  return rows.map((row, i) => {
    const out = { ...row };
    for (const p of periods) {
      const key = `sma${p}`;
      if (i < p - 1) {
        out[key] = null;
      } else {
        let sum = 0;
        for (let k = i - p + 1; k <= i; k++) {
          sum += Number(rows[k].close);
        }
        out[key] = sum / p;
      }
    }
    return out;
  });
}

/** ComposedChart 안에서만 사용 (Recharts 3 scale 훅) */
function CandlestickMarks({ data }) {
  const xScale = useXAxisScale(0);
  const yScale = useYAxisScale("price");
  if (!xScale || !yScale || !data?.length) return null;
  // xScale은 상황에 따라 NaN을 줄 수 있으므로, 폭 계산(estW/bw)은 안전하게 폴백한다.
  const safeNumber = (v) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };

  const x0 = data.length >= 1 ? safeNumber(xScale(data[0].date)) : null;
  const x1 = data.length >= 2 ? safeNumber(xScale(data[1].date)) : null;
  const estW = x0 != null && x1 != null ? Math.abs(x1 - x0) : 14;
  const bw = Number.isFinite(estW) ? Math.max(5, estW * 0.55) : 5;
  return (
    <g className="recharts-candlesticks" pointerEvents="none">
      {data.map((d) => {
        const xL = xScale(d.date);
        if (xL == null || Number.isNaN(Number(xL))) return null;
        const cx = xL + estW / 2;
        const yH = yScale(Number(d.high));
        const yLo = yScale(Number(d.low));
        const yO = yScale(Number(d.open));
        const yC = yScale(Number(d.close));
        if ([yH, yLo, yO, yC].some((v) => v == null || Number.isNaN(Number(v)))) return null;
        const up = Number(d.close) >= Number(d.open);
        const col = up ? "#22c55e" : "#f87171";
        const bodyTop = Math.min(yO, yC);
        const bodyH = Math.max(1, Math.abs(yC - yO));
        return (
          <g key={String(d.date)}>
            <line x1={cx} y1={yH} x2={cx} y2={yLo} stroke={col} strokeWidth={1.5} />
            <rect
              x={cx - bw / 2}
              y={bodyTop}
              width={bw}
              height={bodyH}
              fill={col}
              opacity={0.92}
              stroke={col}
            />
          </g>
        );
      })}
    </g>
  );
}

function ChartOhlcTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="bg-slate-900/95 border border-slate-600 p-3 rounded-lg shadow-xl text-sm text-slate-100 min-w-[10rem]">
      <div className="font-semibold text-white mb-2 border-b border-slate-700 pb-1">{label}</div>
      <div className="space-y-1 text-xs">
        <div className="text-blue-300 font-medium">종가: {formatMoney(row.close)}</div>
        <div className="text-slate-300">시가: ${Number(row.open).toLocaleString()}</div>
        <div className="text-slate-300">고가: ${Number(row.high).toLocaleString()}</div>
        <div className="text-slate-300">저가: ${Number(row.low).toLocaleString()}</div>
        <div className="text-slate-500 pt-1 border-t border-slate-800 mt-1">
          거래량: {Number(row.volume ?? 0).toLocaleString()}
        </div>
      </div>
    </div>
  );
}

const INITIAL_CASH_DEFAULT = 5000; // 5000 달러(가상)

export default function StockSimulationSection() {
  const quickTickers = useMemo(
    () => [
      { symbol: "TSLA", name: "Tesla" },
      { symbol: "NVDA", name: "NVIDIA" },
      { symbol: "AAPL", name: "Apple" },
      { symbol: "MSFT", name: "Microsoft" },
      { symbol: "AMZN", name: "Amazon" },
    ],
    []
  );

  const [simulationStarted, setSimulationStarted] = useState(false);
  const [initialCashInput, setInitialCashInput] = useState(
    String(INITIAL_CASH_DEFAULT)
  );

  const [cash, setCash] = useState(0);
  const [holdings, setHoldings] = useState({}); // { [symbol]: { shares, avgCost, realizedPnl } }
  const [trades, setTrades] = useState([]); // [{ id, type, symbol, date, price, shares, cashFlow, realizedPnl }]

  const [symbolInput, setSymbolInput] = useState("");
  const [selectedSymbol, setSelectedSymbol] = useState("TSLA");
  const [loadingSymbol, setLoadingSymbol] = useState(false);

  const [priceSeriesBySymbol, setPriceSeriesBySymbol] = useState({}); // { [symbol]: [{date, open, high, low, close, volume}] }
  const [selectedDayBySymbol, setSelectedDayBySymbol] = useState({}); // { [symbol]: index }

  const [sharesInput, setSharesInput] = useState("1");

  const toISODateInput = (d) => {
    const x = new Date(d);
    // 날짜 입력은 시간대에 따라 하루 밀릴 수 있어서 정오 기준으로 맞춰 둡니다.
    x.setHours(12, 0, 0, 0);
    return x.toISOString().slice(0, 10);
  };

  const parseISODateInput = (s) => {
    if (!s || typeof s !== "string") return null;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
    const d = new Date(`${s}T12:00:00`);
    return Number.isFinite(d.getTime()) ? d : null;
  };

  // 성능/차트 렌더링을 위해 달력 기준 최대 범위를 제한합니다.
  const MAX_CALENDAR_DAYS = 800;

  const [stockStartDateInput, setStockStartDateInput] = useState(() => {
    const end = new Date();
    end.setHours(12, 0, 0, 0);
    const start = new Date(end);
    start.setDate(start.getDate() - 99);
    return toISODateInput(start);
  });

  const [stockEndDateInput, setStockEndDateInput] = useState(() => {
    return toISODateInput(new Date());
  });

  const dateRangeError = useMemo(() => {
    const startD = parseISODateInput(stockStartDateInput);
    const endD = parseISODateInput(stockEndDateInput);
    if (!startD || !endD) return "시작일/종료일을 올바르게 입력해주세요.";
    if (startD > endD) return "시작일은 종료일보다 이전이어야 합니다.";
    const diffDays = Math.floor((endD - startD) / (1000 * 60 * 60 * 24));
    if (diffDays > MAX_CALENDAR_DAYS) {
      return `기간은 최대 ${MAX_CALENDAR_DAYS}일까지만 선택할 수 있어요.`;
    }
    return "";
  }, [stockStartDateInput, stockEndDateInput]);

  /** ma: 5·20·60일 SMA + 종가 | candle: OHLC 캔들 */
  const [chartMode, setChartMode] = useState("ma");

  const series = useMemo(
    () => priceSeriesBySymbol[selectedSymbol] || [],
    [priceSeriesBySymbol, selectedSymbol]
  );
  const chartData = useMemo(() => enrichWithSma(series), [series]);
  const selectedDayIndex = clamp(
    selectedDayBySymbol[selectedSymbol] ?? (series.length ? series.length - 1 : 0),
    0,
    Math.max(0, series.length - 1)
  );
  const currentRow = series[selectedDayIndex];
  const currentPrice = Number(currentRow?.close || 0);
  const currentDate = currentRow?.date || "";

  const getCurrentPriceForSymbol = useCallback(
    (symbol) => {
      const s = priceSeriesBySymbol[symbol] || [];
      if (!s.length) return 0;
      const idx = selectedDayBySymbol[symbol] ?? s.length - 1;
      return Number(s[idx]?.close || 0);
    },
    [priceSeriesBySymbol, selectedDayBySymbol]
  );

  const portfolioMarketValue = useMemo(() => {
    return Object.entries(holdings).reduce((sum, [sym, h]) => {
      const px = getCurrentPriceForSymbol(sym);
      return sum + px * (Number(h.shares) || 0);
    }, 0);
  }, [holdings, getCurrentPriceForSymbol]);

  const realizedPnl = useMemo(() => {
    return Object.values(holdings).reduce(
      (sum, h) => sum + (Number(h.realizedPnl) || 0),
      0
    );
  }, [holdings]);

  const unrealizedPnl = useMemo(() => {
    return Object.entries(holdings).reduce((sum, [sym, h]) => {
      const px = getCurrentPriceForSymbol(sym);
      const shares = Number(h.shares) || 0;
      const avg = Number(h.avgCost) || 0;
      return sum + (px - avg) * shares;
    }, 0);
  }, [holdings, getCurrentPriceForSymbol]);

  const totalPnl = realizedPnl + unrealizedPnl;
  const totalValue = cash + portfolioMarketValue;

  const canTrade = simulationStarted && currentPrice > 0;
  const holdingForSelected = holdings[selectedSymbol] || {
    shares: 0,
    avgCost: 0,
    realizedPnl: 0,
  };

  const selectedShares = Math.max(0, Number(holdingForSelected.shares) || 0);
  const desiredShares = Math.floor(Number(sharesInput) || 0);
  const buyCost = desiredShares * currentPrice;
  const sellProceeds = desiredShares * currentPrice;

  const resetAccount = () => {
    const parsed = Math.floor(Number(initialCashInput) || INITIAL_CASH_DEFAULT);
    setCash(parsed);
    setHoldings({});
    setTrades([]);
    setSimulationStarted(true);
  };

  const fetchSymbolSeries = async (symbol) => {
    const normalized = (symbol || "").trim().toUpperCase();
    if (!normalized) return;

    if (dateRangeError) {
      alert(dateRangeError);
      return;
    }

    setLoadingSymbol(true);
    try {
      const res = await api.post("/api/recent-status", {
        text: normalized,
        start_date: stockStartDateInput,
        end_date: stockEndDateInput,
      });
      const nextSeries = res?.data?.stock_data || [];

      if (!Array.isArray(nextSeries) || nextSeries.length === 0) {
        alert("해당 종목의 주가 데이터를 불러올 수 없습니다.");
        return;
      }

      // 방어적으로 start_date/end_date 범위에 해당하는 거래일만 필터링합니다.
      // (yfinance/백엔드 처리 이슈가 있어도 UI가 사용자가 지정한 범위로 보이도록)
      const filteredSeries = nextSeries.filter((r) => {
        const d = r?.date;
        if (!d) return false;
        return d >= stockStartDateInput && d <= stockEndDateInput;
      });

      if (filteredSeries.length === 0) {
        alert("해당 기간(start~end)의 주가 데이터를 불러올 수 없습니다.");
        return;
      }

      setPriceSeriesBySymbol((prev) => ({
        ...prev,
        [normalized]: filteredSeries,
      }));

      setSelectedDayBySymbol((prev) => ({
        ...prev,
        [normalized]: filteredSeries.length - 1,
      }));

      setSelectedSymbol(normalized);
    } catch (e) {
      console.error(e);
      alert("서버 통신 오류가 발생했습니다.");
    } finally {
      setLoadingSymbol(false);
    }
  };

  // NOTE: 이 컴포넌트는 사용자가 종목을 조회했을 때만 API를 호출합니다.

  const buy = () => {
    if (!canTrade) return;
    if (desiredShares <= 0) {
      alert("매수할 수량을 입력해주세요.");
      return;
    }
    if (buyCost > cash) {
      alert(`가상 현금이 부족합니다. 필요: ${formatMoney(buyCost)}, 보유: ${formatMoney(cash)}`);
      return;
    }

    setCash((prev) => prev - buyCost);
    setHoldings((prev) => {
      const prevHolding = prev[selectedSymbol] || {
        shares: 0,
        avgCost: 0,
        realizedPnl: 0,
      };
      const prevShares = Number(prevHolding.shares) || 0;
      const prevAvg = Number(prevHolding.avgCost) || 0;
      const newShares = prevShares + desiredShares;
      const nextAvg =
        newShares > 0
          ? (prevAvg * prevShares + currentPrice * desiredShares) / newShares
          : 0;

      return {
        ...prev,
        [selectedSymbol]: {
          ...prevHolding,
          shares: newShares,
          avgCost: nextAvg,
        },
      };
    });

    setTrades((prev) => [
      {
        id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
        type: "BUY",
        symbol: selectedSymbol,
        date: currentDate,
        price: currentPrice,
        shares: desiredShares,
        cashFlow: -buyCost,
        realizedPnl: 0,
      },
      ...prev,
    ]);
  };

  const sell = () => {
    if (!canTrade) return;
    if (desiredShares <= 0) {
      alert("매도할 수량을 입력해주세요.");
      return;
    }
    if (desiredShares > selectedShares) {
      alert("보유 수량을 초과해서 매도할 수 없습니다.");
      return;
    }

    setCash((prev) => prev + sellProceeds);
    setHoldings((prev) => {
      const prevHolding = prev[selectedSymbol];
      const prevShares = Number(prevHolding?.shares) || 0;
      const prevAvg = Number(prevHolding?.avgCost) || 0;
      const remainingShares = prevShares - desiredShares;
      const realized = (currentPrice - prevAvg) * desiredShares;

      return {
        ...prev,
        [selectedSymbol]: {
          shares: remainingShares,
          avgCost: remainingShares > 0 ? prevAvg : 0,
          realizedPnl: (Number(prevHolding?.realizedPnl) || 0) + realized,
        },
      };
    });

    const realizedForTrade = (currentPrice - Number(holdingForSelected.avgCost || 0)) * desiredShares;
    setTrades((prev) => [
      {
        id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
        type: "SELL",
        symbol: selectedSymbol,
        date: currentDate,
        price: currentPrice,
        shares: desiredShares,
        cashFlow: sellProceeds,
        realizedPnl: realizedForTrade,
      },
      ...prev,
    ]);
  };

  const holdingList = Object.entries(holdings);

  return (
    <div className="space-y-6 bg-slate-900 border border-slate-800 rounded-2xl p-8 pb-24 animate-fade-in overflow-visible">
      <div className="flex flex-col lg:flex-row lg:items-start gap-4 justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1">주식 시뮬레이션</h2>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 lg:items-start items-stretch">
          {!simulationStarted ? (
            <div className="flex items-center gap-3">
              <div className="text-sm text-slate-300 whitespace-nowrap">초기 가상 자금</div>
              <input
                value={initialCashInput}
                onChange={(e) => setInitialCashInput(e.target.value)}
                inputMode="numeric"
                className="w-40 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          ) : null}

          <button
            onClick={resetAccount}
            className="px-5 py-2 rounded-lg font-semibold transition-colors bg-blue-600 hover:bg-blue-500 text-white"
          >
            {simulationStarted ? "계좌 초기화" : "시뮬레이션 시작"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 lg:items-start gap-6">
        {/* lg 미만: 차트·매수매도를 먼저 보여줌(세로 스택에서 왼쪽 열 아래로 밀리는 현상 방지) */}
        <div className="order-2 lg:order-none lg:col-span-5 space-y-5 min-w-0 overflow-visible">
          {/* Summary */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
              <div className="text-slate-400 text-xs mb-1">가상 현금</div>
              <div className="text-white text-xl font-bold">{formatMoney(cash)}</div>
            </div>
            <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
              <div className="text-slate-400 text-xs mb-1">계좌 총액</div>
              <div className="text-white text-xl font-bold">{formatMoney(totalValue)}</div>
            </div>
            <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4 sm:col-span-2">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-slate-400 text-xs mb-1">총 손익</div>
                  <div
                    className={`text-xl font-bold ${
                      totalPnl >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {totalPnl >= 0 ? "+" : "-"}
                    {formatMoney(Math.abs(totalPnl))}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-slate-400 text-xs">실현</div>
                  <div className={realizedPnl >= 0 ? "text-green-400" : "text-red-400"}>
                    {realizedPnl >= 0 ? "+" : "-"}
                    {formatMoney(Math.abs(realizedPnl))}
                  </div>
                  <div className="text-slate-400 text-xs mt-1">미실현</div>
                  <div className={unrealizedPnl >= 0 ? "text-green-400" : "text-red-400"}>
                    {unrealizedPnl >= 0 ? "+" : "-"}
                    {formatMoney(Math.abs(unrealizedPnl))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-slate-800/30 border border-slate-700 rounded-2xl p-4">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <div className="text-white font-semibold whitespace-nowrap">종목</div>
              <input
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                className="min-w-[8rem] flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="예: TSLA, AAPL"
                onKeyDown={(e) => e.key === "Enter" && fetchSymbolSeries(symbolInput)}
              />
              <div className="flex items-center gap-2">
                <span className="text-slate-300 text-xs whitespace-nowrap">기간</span>
                <input
                  type="date"
                  value={stockStartDateInput}
                  onChange={(e) => setStockStartDateInput(e.target.value)}
                  className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
                />
                <span className="text-slate-500 text-xs">~</span>
                <input
                  type="date"
                  value={stockEndDateInput}
                  onChange={(e) => setStockEndDateInput(e.target.value)}
                  className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              {dateRangeError ? (
                <div className="text-red-400 text-[11px] leading-tight">
                  {dateRangeError}
                </div>
              ) : null}
              <button
                onClick={() => fetchSymbolSeries(symbolInput)}
                disabled={loadingSymbol}
                className="px-4 py-2 rounded-lg font-semibold bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 shrink-0"
              >
                {loadingSymbol ? "조회 중..." : "조회"}
              </button>
            </div>

            <div className="flex flex-wrap gap-2">
              {quickTickers.map((t) => (
                <button
                  key={t.symbol}
                  onClick={() => {
                    setSymbolInput(t.symbol);
                    fetchSymbolSeries(t.symbol);
                  }}
                  className="px-3 py-1 rounded-full bg-slate-900 border border-slate-700 text-slate-200 hover:border-blue-500 hover:text-blue-300 transition-colors text-xs"
                >
                  {t.symbol}
                </button>
              ))}
            </div>
          </div>

          {/* Holdings */}
          <div className="bg-slate-800/30 border border-slate-700 rounded-2xl p-4 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div className="text-white font-semibold">보유 종목</div>
              <div className="text-slate-500 text-xs">{holdingList.length ? `${holdingList.length}개` : ""}</div>
            </div>
            {holdingList.length === 0 ? (
              <div className="text-slate-500 text-sm bg-slate-900/30 border border-slate-700 rounded-xl p-4 flex-1 flex items-center justify-center">
                아직 보유한 종목이 없습니다.
              </div>
            ) : (
              <div className="space-y-3 overflow-y-auto custom-scrollbar pr-1" style={{ maxHeight: 200 }}>
                {holdingList.map(([sym, h]) => {
                  const px = getCurrentPriceForSymbol(sym);
                  const shares = Number(h.shares) || 0;
                  const avg = Number(h.avgCost) || 0;
                  const pnl = (px - avg) * shares;
                  return (
                    <div key={sym} className="bg-slate-900/40 border border-slate-700 rounded-xl p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-white font-semibold">{sym}</div>
                          <div className="text-slate-400 text-xs mt-1">{shares}주</div>
                        </div>
                        <div className="text-right">
                          <div className="text-white font-bold">{formatMoney(px)}</div>
                          <div
                            className={`flex items-center justify-end gap-1 text-xs mt-1 ${
                              pnl >= 0 ? "text-green-400" : "text-red-400"
                            }`}
                          >
                            {pnl >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                            <span className="font-semibold">
                              {pnl >= 0 ? "+" : "-"}
                              {formatMoney(Math.abs(pnl))}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Trades */}
          <div className="bg-slate-800/30 border border-slate-700 rounded-2xl p-4 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div className="text-white font-semibold">거래 내역</div>
              <div className="text-slate-500 text-xs">{trades.length ? `${trades.length}건` : ""}</div>
            </div>
            {trades.length === 0 ? (
              <div className="text-slate-500 text-sm bg-slate-900/30 border border-slate-700 rounded-xl p-4 flex-1 flex items-center justify-center">
                거래 내역이 없습니다.
              </div>
            ) : (
              <div className="overflow-y-auto custom-scrollbar pr-1" style={{ maxHeight: 220 }}>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-400 border-b border-slate-700">
                      <th className="py-2 px-1">일자</th>
                      <th className="py-2 px-1">종목</th>
                      <th className="py-2 px-1">유형</th>
                      <th className="py-2 px-1 text-right">수량</th>
                      <th className="py-2 px-1 text-right">단가</th>
                      <th className="py-2 px-1 text-right">손익</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.slice(0, 30).map((t) => {
                      const isBuy = t.type === "BUY";
                      const pnl = Number(t.realizedPnl) || 0;
                      return (
                        <tr key={t.id} className="border-b border-slate-800/50">
                          <td className="py-2 px-1 text-slate-300">{t.date}</td>
                          <td className="py-2 px-1 text-white font-semibold">{t.symbol}</td>
                          <td className="py-2 px-1">
                            <span className={isBuy ? "text-blue-300" : "text-amber-300"}>
                              {isBuy ? "매수" : "매도"}
                            </span>
                          </td>
                          <td className="py-2 px-1 text-right text-slate-200">{t.shares}</td>
                          <td className="py-2 px-1 text-right text-slate-200">{formatMoney(t.price)}</td>
                          <td
                            className={`py-2 px-1 text-right ${
                              pnl >= 0 ? "text-green-400" : "text-red-400"
                            }`}
                          >
                            {t.type === "BUY"
                              ? "—"
                              : `${pnl >= 0 ? "+" : "-"}${formatMoney(Math.abs(pnl))}`}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <div className="order-1 lg:order-none lg:col-span-7 flex flex-col gap-4 min-w-0">
          <div className="bg-slate-800/30 border border-slate-700 rounded-2xl p-4 space-y-4">
            <div className="bg-slate-900/40 border border-slate-700 rounded-xl p-4 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="text-white font-semibold">매수 / 매도</div>
                  <div className="text-slate-400 text-xs mt-0.5">
                    현재가(선택일):{" "}
                    <span className="text-white font-bold">
                      {currentPrice ? formatMoney(currentPrice) : "-"}
                    </span>
                    <span className="text-slate-600"> · </span>
                    <span className="text-slate-400">보유 {Number(holdingForSelected.shares) || 0}주</span>
                  </div>
                </div>
                {!simulationStarted ? (
                  <div className="text-amber-400 text-xs font-semibold sm:text-right">
                    먼저 “시뮬레이션 시작”이 필요해요.
                  </div>
                ) : !series.length ? (
                  <div className="text-slate-500 text-xs sm:text-right">종목을 조회한 뒤 거래할 수 있어요.</div>
                ) : null}
              </div>

              <div className="flex flex-col sm:flex-row sm:items-end gap-4">
                <div className="flex-1 min-w-0">
                  <label className="block text-slate-300 text-xs mb-1">수량(주)</label>
                  <input
                    type="number"
                    value={sharesInput}
                    onChange={(e) => setSharesInput(e.target.value)}
                    className="w-full max-w-xs bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-white outline-none focus:ring-2 focus:ring-blue-500"
                    min={0}
                    step={1}
                  />
                  <div className="text-slate-500 text-xs mt-2">
                    매수 총액:{" "}
                    <span className="text-white font-semibold">
                      {desiredShares > 0 ? formatMoney(buyCost) : "-"}
                    </span>
                    <span className="text-slate-600"> · </span>
                    매도 예상:{" "}
                    <span className="text-white font-semibold">
                      {desiredShares > 0 ? formatMoney(sellProceeds) : "-"}
                    </span>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0 w-full sm:w-auto">
                  <button
                    type="button"
                    onClick={buy}
                    disabled={!canTrade || desiredShares <= 0}
                    className="flex-1 sm:flex-initial sm:min-w-[7rem] px-4 py-2.5 rounded-xl font-bold bg-blue-600 hover:bg-blue-500 text-white text-sm disabled:opacity-50"
                  >
                    매수
                  </button>
                  <button
                    type="button"
                    onClick={sell}
                    disabled={!canTrade || desiredShares <= 0 || desiredShares > selectedShares}
                    className="flex-1 sm:flex-initial sm:min-w-[7rem] px-4 py-2.5 rounded-xl font-bold bg-slate-900 hover:bg-slate-800 border border-slate-700 text-white text-sm disabled:opacity-50"
                  >
                    매도
                  </button>
                </div>
              </div>
            </div>

            {series.length ? (
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() =>
                    setSelectedDayBySymbol((prev) => ({
                      ...prev,
                      [selectedSymbol]: clamp(selectedDayIndex - 1, 0, series.length - 1),
                    }))
                  }
                  className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 hover:border-blue-500 hover:text-blue-300 text-xs shrink-0"
                >
                  이전
                </button>
                <input
                  type="range"
                  min={0}
                  max={series.length - 1}
                  value={selectedDayIndex}
                  onChange={(e) =>
                    setSelectedDayBySymbol((prev) => ({
                      ...prev,
                      [selectedSymbol]: Number(e.target.value),
                    }))
                  }
                  className="flex-1 min-w-0 accent-blue-500"
                />
                <button
                  type="button"
                  onClick={() =>
                    setSelectedDayBySymbol((prev) => ({
                      ...prev,
                      [selectedSymbol]: clamp(selectedDayIndex + 1, 0, series.length - 1),
                    }))
                  }
                  className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 hover:border-blue-500 hover:text-blue-300 text-xs shrink-0"
                >
                  다음
                </button>
              </div>
            ) : null}
          </div>

          <div className="relative z-0 bg-slate-800/30 border border-slate-700 rounded-2xl p-4 min-h-0 isolate">
            <div className="flex flex-col gap-3 mb-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="text-white font-semibold text-lg">거래 차트</div>
                <div className="text-slate-400 text-xs mt-1">
                  {selectedSymbol} · 선택 날짜:{" "}
                  <span className="text-white font-semibold">{currentDate || "—"}</span>
                  <span className="text-slate-600"> · </span>
                  <span className="text-slate-500">막대: 거래량</span>
                  {chartMode === "ma" ? (
                    <span className="text-slate-600"> · </span>
                  ) : null}
                  {chartMode === "ma" ? (
                    <span className="text-slate-500">
                      노랑 5일 · 빨강 20일 · 초록 60일 이평
                    </span>
                  ) : null}
                </div>
              </div>
              <div className="flex flex-col items-stretch sm:items-end gap-2 shrink-0">
                <div className="flex flex-wrap gap-1.5 justify-end">
                  {[
                    { id: "ma", label: "이평선" },
                    { id: "candle", label: "캔들" },
                  ].map(({ id, label }) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setChartMode(id)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-colors ${
                        chartMode === id
                          ? "bg-blue-600 border-blue-500 text-white"
                          : "bg-slate-900/80 border-slate-600 text-slate-300 hover:border-slate-500"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <div className="text-right text-xs text-slate-500">
                  {series.length ? `데이터: ${series.length}개` : ""}
                </div>
              </div>
            </div>

            {series.length ? (
              <div className="h-[380px] w-full overflow-visible rounded-xl border border-slate-800/80 bg-slate-900/20">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 28, right: 20, left: 4, bottom: 8 }}>
                    <defs>
                      <linearGradient id="simLine" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#3b82f6" />
                        <stop offset="100%" stopColor="#8b5cf6" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: "#94a3b8", fontSize: 12 }}
                      tickFormatter={(val) => String(val).slice(5)}
                      minTickGap={20}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      yAxisId="price"
                      tick={{ fill: "#94a3b8", fontSize: 12 }}
                      tickFormatter={(v) => `$${Math.round(Number(v))}`}
                      width={64}
                      domain={["auto", "auto"]}
                    />
                    <YAxis
                      yAxisId="vol"
                      orientation="right"
                      tick={{ fill: "#64748b", fontSize: 11 }}
                      tickFormatter={formatVolumeAxis}
                      width={44}
                      domain={[0, "auto"]}
                    />
                    <Tooltip
                      content={<ChartOhlcTooltip />}
                      shared
                      allowEscapeViewBox={{ x: false, y: true }}
                      cursor={{ stroke: "#94a3b8", strokeWidth: 1, strokeDasharray: "4 4" }}
                      wrapperStyle={{ outline: "none", zIndex: 50 }}
                    />
                    {currentDate ? (
                      <ReferenceLine
                        yAxisId="price"
                        x={currentDate}
                        stroke="#fbbf24"
                        strokeWidth={2}
                        strokeDasharray="6 4"
                        label={{
                          position: "insideTop",
                          fill: "#fbbf24",
                          fontSize: 11,
                          fontWeight: "bold",
                          offset: 6,
                        }}
                      />
                    ) : null}
                    <Bar
                      yAxisId="vol"
                      dataKey="volume"
                      fill="#475569"
                      fillOpacity={0.45}
                      radius={[2, 2, 0, 0]}
                      maxBarSize={28}
                    />
                    {chartMode === "candle" ? <CandlestickMarks data={chartData} /> : null}
                    {chartMode === "ma" ? (
                      <>
                        <Line
                          yAxisId="price"
                          type="monotone"
                          dataKey="close"
                          name="종가"
                          stroke="#94a3b8"
                          strokeWidth={1.5}
                          dot={false}
                          activeDot={{ r: 5, fill: "#e2e8f0" }}
                        />
                        <Line
                          yAxisId="price"
                          type="monotone"
                          dataKey="sma5"
                          name="5일"
                          stroke="#fbbf24"
                          strokeWidth={1.75}
                          dot={false}
                          connectNulls
                        />
                        <Line
                          yAxisId="price"
                          type="monotone"
                          dataKey="sma20"
                          name="20일"
                          stroke="#ef4444"
                          strokeWidth={1.75}
                          dot={false}
                          connectNulls
                        />
                        <Line
                          yAxisId="price"
                          type="monotone"
                          dataKey="sma60"
                          name="60일"
                          stroke="#34d399"
                          strokeWidth={1.75}
                          dot={false}
                          connectNulls
                        />
                      </>
                    ) : null}
                    {chartMode === "candle" ? (
                      <Line
                        yAxisId="price"
                        type="monotone"
                        dataKey="close"
                        stroke="transparent"
                        strokeWidth={28}
                        dot={false}
                        isAnimationActive={false}
                        activeDot={{ r: 6, strokeWidth: 0, fill: "#fff" }}
                      />
                    ) : null}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-[380px] flex items-center justify-center text-slate-500 bg-slate-900/30 rounded-xl border border-slate-700">
                종목을 조회하면 가격 차트가 표시됩니다.
              </div>
            )}
          </div>

          <div className="bg-slate-800/30 border border-slate-700 rounded-2xl p-4">
            <div className="text-white font-semibold mb-2">시뮬레이션 방법</div>
            <div className="text-slate-400 text-sm space-y-2">
              <div>1) 시뮬레이션 시작 후 종목을 조회합니다.</div>
              <div>2) 날짜를 지정해 매수·매도합니다. (거래량: 차트 막대 참고)</div>
              <div>3) 계좌 총액과 손익이 실시간으로 갱신됩니다.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
