"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api from "../utils/api";
import { useValuationPrices } from "../hooks/useValuationPrices";
import { useBackgroundPrices } from "../hooks/useBackgroundPrices";
import { SP500_SECTORS } from "../data/sp500Sectors";
import { calculateOrderAmounts, computeSimulationMetrics } from "../utils/simulationPortfolio";
import {
  ComposedChart,
  Customized,
  Line,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  useXAxisDomain,
  useYAxisDomain,
  usePlotArea,
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

const hasVolume = (row) => Number.isFinite(Number(row?.volume)) && Number(row.volume) > 0;

const normalizeMarketTime = (timeValue) => {
  if (timeValue == null || timeValue === "") return "";
  const raw = String(timeValue).trim();
  const numericValue = Number(raw);

  if (/^\d+(\.\d+)?$/.test(raw) && Number.isFinite(numericValue)) {
    const millis = numericValue > 1e12 ? numericValue : numericValue * 1000;
    const d = new Date(millis);
    if (Number.isFinite(d.getTime())) return d.toISOString();
  }

  const d = new Date(raw);
  if (Number.isFinite(d.getTime())) return d.toISOString();
  return raw;
};

const padDatePart = (value) => String(value).padStart(2, "0");

const parseMarketDate = (timeValue) => {
  const normalized = normalizeMarketTime(timeValue);
  if (!normalized) return null;
  const d = new Date(normalized);
  return Number.isFinite(d.getTime()) ? d : null;
};

const formatLocalDate = (date) =>
  `${date.getFullYear()}-${padDatePart(date.getMonth() + 1)}-${padDatePart(date.getDate())}`;

const formatLocalTime = (date) =>
  `${padDatePart(date.getHours())}:${padDatePart(date.getMinutes())}:${padDatePart(date.getSeconds())}`;

const toLocalMarketDate = (timeValue) => {
  const d = parseMarketDate(timeValue);
  if (d) return formatLocalDate(d);
  return String(timeValue || "").slice(0, 10);
};

const toLocalMarketTime = (timeValue) => {
  const d = parseMarketDate(timeValue);
  if (d) return formatLocalTime(d);
  return String(timeValue || "").slice(11, 19) || String(timeValue || "");
};

const toLocalMarketDateTimeLabel = (timeValue) => {
  const d = parseMarketDate(timeValue);
  if (d) return `${formatLocalDate(d)} ${formatLocalTime(d)}`;
  return String(timeValue || "");
};

const toRealtimeLabel = (timeValue) => {
  return toLocalMarketTime(timeValue);
};

const toMarketDate = (timeValue) => {
  return toLocalMarketDate(timeValue);
};

const toMarketDateTimeLabel = (timeValue) => {
  return toLocalMarketDateTimeLabel(timeValue);
};

const pointToRealtimeRow = (point, previousRow = null) => {
  const price = Number(point?.price);
  if (!Number.isFinite(price) || price <= 0) return null;

  const normalizedTime = normalizeMarketTime(point?.time);
  const label = toMarketDateTimeLabel(normalizedTime) || String(point?.time || "");
  const date = toMarketDate(normalizedTime) || String(point?.time || "");
  const previousClose = Number(previousRow?.close);
  const open = Number.isFinite(previousClose) && previousClose > 0 ? previousClose : price;

  return {
    date,
    xKey: label,
    time: normalizedTime || label,
    open,
    high: Math.max(open, price),
    low: Math.min(open, price),
    close: price,
    volume: Number(point?.volume || 0),
  };
};

const tickToDailyRealtimeRow = (tick, previousRow = null) => {
  const tickRow = tick?.row && typeof tick.row === "object" ? tick.row : null;
  const price = Number(tickRow?.close ?? tick?.price);
  if (!Number.isFinite(price) || price <= 0) return null;

  const tickTime = normalizeMarketTime(tickRow?.time || tick?.time || tickRow?.date);
  const tickDate = toMarketDate(tickRow?.date || tickTime) || formatLocalDate(new Date());
  const previousClose = Number(previousRow?.close);
  const rowOpen = Number(tickRow?.open);
  const open = Number.isFinite(rowOpen) && rowOpen > 0
    ? rowOpen
    : Number.isFinite(previousClose) && previousClose > 0
      ? previousClose
      : price;
  const rowHigh = Number(tickRow?.high);
  const rowLow = Number(tickRow?.low);
  const tickVolume = Number(tickRow?.volume ?? tick?.volume);
  const volume = Number.isFinite(tickVolume) && tickVolume > 0 ? tickVolume : null;
  const tickXKey = toMarketDateTimeLabel(tickTime) || tickDate;

  if ((previousRow?.xKey || previousRow?.date) === tickXKey) {
    const previousHigh = Number(previousRow.high);
    const previousLow = Number(previousRow.low);
    return {
      ...previousRow,
      time: tickTime || previousRow.time || previousRow.date,
      xKey: tickXKey,
      high: Math.max(
        Number.isFinite(previousHigh) ? previousHigh : price,
        Number.isFinite(rowHigh) ? rowHigh : price,
        price
      ),
      low: Math.min(
        Number.isFinite(previousLow) ? previousLow : price,
        Number.isFinite(rowLow) ? rowLow : price,
        price
      ),
      close: price,
      volume,
    };
  }

  return {
    date: tickDate,
    xKey: tickXKey,
    time: tickTime || tickDate,
    open,
    high: Math.max(open, Number.isFinite(rowHigh) ? rowHigh : price, price),
    low: Math.min(open, Number.isFinite(rowLow) ? rowLow : price, price),
    close: price,
    volume,
  };
};

const getWebSocketUrl = (path) => {
  const base = api.defaults?.baseURL || "http://localhost:8000";
  const url = new URL(path, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
};

const isNyseOpen = () => {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "numeric",
    minute: "numeric",
    hour12: false,
  }).formatToParts(now);
  const day = parts.find((p) => p.type === "weekday")?.value;
  const hour = parseInt(parts.find((p) => p.type === "hour")?.value || "0", 10);
  const minute = parseInt(parts.find((p) => p.type === "minute")?.value || "0", 10);
  if (day === "Sat" || day === "Sun") return false;
  const totalMinutes = hour * 60 + minute;
  return totalMinutes >= 9 * 60 + 30 && totalMinutes < 16 * 60;
};

const getNyseKstLabel = () => {
  const now = new Date();
  const tzName = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    timeZoneName: "short",
  }).formatToParts(now).find((p) => p.type === "timeZoneName")?.value;
  // EDT = UTC-4 (서머타임, 3~11월), EST = UTC-5 (겨울, 11~3월)
  const isEDT = tzName === "EDT";
  const open = isEDT ? "오후 10:30" : "오후 11:30";
  const close = isEDT ? "오전 5:00 (익일)" : "오전 6:00 (익일)";
  return { open, close };
};

const REALTIME_CHART_MAX_POINTS = 100;

const capRealtimeRows = (rows, maxLength = REALTIME_CHART_MAX_POINTS) =>
  rows.slice(-Math.max(1, maxLength));

const createRealtimePlaceholderRows = (maxLength = REALTIME_CHART_MAX_POINTS) =>
  Array.from({ length: maxLength }, (_, index) => ({
    date: "",
    xKey: `slot-${String(index + 1).padStart(3, "0")}`,
    time: "",
    open: null,
    high: null,
    low: null,
    close: null,
    volume: null,
    isPlaceholder: true,
  }));

const hasRealtimePrice = (row) => Number.isFinite(Number(row?.close)) && Number(row.close) > 0;

const getRealtimeFilledRows = (rows) => (Array.isArray(rows) ? rows.filter(hasRealtimePrice) : []);

const getLastFilledRowIndex = (rows) => {
  if (!Array.isArray(rows)) return -1;
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    if (hasRealtimePrice(rows[i])) return i;
  }
  return -1;
};

const formatChartXAxisTick = (value, index, source, firstRealtimeIndex = 0) => {
  const raw = String(value || "");
  if (!raw || raw.startsWith("slot-")) return "";

  if (source === "realtime") {
    return index === firstRealtimeIndex
      ? toLocalMarketDateTimeLabel(raw)
      : toLocalMarketTime(raw);
  }

  return raw.length > 10 ? raw.slice(5, 16) : raw.slice(5);
};

const mergeRealtimeTickRow = (rows, nextRow, maxLength = REALTIME_CHART_MAX_POINTS) => {
  const baseRows = Array.isArray(rows) && rows.length
    ? rows
    : createRealtimePlaceholderRows(maxLength);
  const lastFilledIndex = getLastFilledRowIndex(baseRows);
  const lastFilledRow = lastFilledIndex >= 0 ? baseRows[lastFilledIndex] : null;
  const nextKey = nextRow.xKey || nextRow.date;

  if (lastFilledRow && (lastFilledRow.xKey || lastFilledRow.date) === nextKey) {
    return baseRows.map((row, index) =>
      index === lastFilledIndex ? { ...lastFilledRow, ...nextRow, isPlaceholder: false } : row
    );
  }

  const filledRows = getRealtimeFilledRows(baseRows);
  if (filledRows.length < maxLength) {
    const insertIndex = lastFilledIndex + 1;
    return baseRows.map((row, index) =>
      index === insertIndex ? { ...nextRow, isPlaceholder: false } : row
    );
  }

  return capRealtimeRows([...filledRows, { ...nextRow, isPlaceholder: false }], maxLength);
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
        let validCount = 0;
        for (let k = i - p + 1; k <= i; k++) {
          const close = Number(rows[k].close);
          if (!Number.isFinite(close) || close <= 0) break;
          sum += close;
          validCount += 1;
        }
        out[key] = validCount === p ? sum / p : null;
      }
    }
    return out;
  });
}

function CandlestickMarks({ data }) {
  const xDomain = useXAxisDomain(0);
  const yDomain = useYAxisDomain("price");
  const plotArea = usePlotArea();

  if (!Array.isArray(xDomain) || xDomain.length === 0) return null;
  if (!Array.isArray(yDomain) || yDomain.length < 2) return null;
  if (!plotArea || !plotArea.width || !plotArea.height) return null;
  if (!data?.length) return null;

  const n = xDomain.length;
  const step = plotArea.width / n;
  const xIndexMap = new Map(xDomain.map((key, i) => [String(key), i]));
  const bw = Math.max(4, step * 0.55);

  const yMin = Number(yDomain[0]);
  const yMax = Number(yDomain[yDomain.length - 1]);
  if (!Number.isFinite(yMin) || !Number.isFinite(yMax) || yMax === yMin) return null;

  const yOf = (val) => {
    const v = Number(val);
    if (!Number.isFinite(v)) return null;
    return plotArea.y + plotArea.height * (1 - (v - yMin) / (yMax - yMin));
  };

  return (
    <g className="recharts-candlesticks" pointerEvents="none">
      {data.map((d) => {
        const idx = xIndexMap.get(String(d.xKey || d.date));
        if (idx == null) return null;
        const cx = plotArea.x + idx * step + step / 2;
        const yH = yOf(d.high);
        const yLo = yOf(d.low);
        const yO = yOf(d.open);
        const yC = yOf(d.close);
        if ([yH, yLo, yO, yC].some((v) => v == null)) return null;
        const up = Number(d.close) >= Number(d.open);
        const col = up ? "#22c55e" : "#f87171";
        const bodyTop = Math.min(yO, yC);
        const bodyH = Math.max(1, Math.abs(yC - yO));
        return (
          <g key={String(d.xKey || d.date)}>
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

/** 차트 플롯 영역 클릭으로 거래일 선택 */
function ChartDayClickBands({ data, selectedIndex, onSelectDay }) {
  const xDomain = useXAxisDomain(0);
  const plotArea = usePlotArea();

  if (!Array.isArray(xDomain) || xDomain.length === 0) return null;
  if (!plotArea || !plotArea.width || !plotArea.height) return null;
  if (!data?.length) return null;

  const n = xDomain.length;
  const step = plotArea.width / n;
  const xIndexMap = new Map(xDomain.map((key, i) => [String(key), i]));
  const colW = Math.max(5, step);

  return (
    <g className="chart-day-click-bands">
      {data.map((d, i) => {
        const idx = xIndexMap.get(String(d.xKey || d.date));
        if (idx == null) return null;
        const cx = plotArea.x + idx * step + step / 2;
        const isSelected = i === selectedIndex;
        return (
          <rect
            key={String(d.xKey || d.date)}
            x={cx - colW / 2}
            y={plotArea.y}
            width={colW}
            height={plotArea.height}
            fill={isSelected ? "rgba(251, 191, 36, 0.12)" : "transparent"}
            stroke={isSelected ? "#fbbf24" : "transparent"}
            strokeWidth={isSelected ? 1 : 0}
            strokeOpacity={0.35}
            style={{ cursor: "pointer" }}
            onClick={(e) => {
              e.stopPropagation();
              onSelectDay(i);
            }}
          />
        );
      })}
    </g>
  );
}

function ChartOhlcTooltip({ active, payload, label, isRealtime, sessionHigh, sessionLow }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="bg-slate-900/95 border border-slate-600 p-3 rounded-lg shadow-xl text-sm text-slate-100 min-w-[10rem]">
      <div className="font-semibold text-white mb-2 border-b border-slate-700 pb-1">{label}</div>
      <div className="space-y-1 text-xs">
        {isRealtime ? (
          <>
            <div className="text-blue-300 font-medium">현재가: {formatMoney(row.close)}</div>
            <div className="text-slate-300">
              고가: {sessionHigh != null ? `$${Number(sessionHigh).toLocaleString()}` : "—"}
            </div>
            <div className="text-slate-300">
              저가: {sessionLow != null ? `$${Number(sessionLow).toLocaleString()}` : "—"}
            </div>
          </>
        ) : (
          <>
            <div className="text-blue-300 font-medium">종가: {formatMoney(row.close)}</div>
            <div className="text-slate-300">시가: ${Number(row.open).toLocaleString()}</div>
            <div className="text-slate-300">고가: ${Number(row.high).toLocaleString()}</div>
            <div className="text-slate-300">저가: ${Number(row.low).toLocaleString()}</div>
          </>
        )}
        <div className="text-slate-500 pt-1 border-t border-slate-800 mt-1">
          거래량: {hasVolume(row) ? Number(row.volume).toLocaleString() : "제공 안 됨"}
        </div>
      </div>
    </div>
  );
}

const INITIAL_CASH_DEFAULT = 5000; // 5000 달러(가상)
export default function StockSimulationSection({ rewardCash = 0, user = null, initialTicker = null }) {
  const [activeSector, setActiveSector] = useState(SP500_SECTORS[0].id);
  const [selectedTickerInfo, setSelectedTickerInfo] = useState(null);

  const [simulationStarted, setSimulationStarted] = useState(false);
  const [initialCashInput, setInitialCashInput] = useState(
    String(INITIAL_CASH_DEFAULT)
  );
  const baseInitialCash = Math.floor(Number(initialCashInput) || INITIAL_CASH_DEFAULT);
  const effectiveInitialCash = baseInitialCash + Math.max(0, Number(rewardCash) || 0);

  const [cash, setCash] = useState(0);
  const [holdings, setHoldings] = useState({}); // { [symbol]: { shares, avgCost, realizedPnl } }
  const [trades, setTrades] = useState([]); // [{ id, type, symbol, date, price, shares, cashFlow, realizedPnl }]
  const [simulationHydrated, setSimulationHydrated] = useState(false);
  const [simulationLoading, setSimulationLoading] = useState(false);

  const [symbolInput, setSymbolInput] = useState("");
  const [selectedSymbol, setSelectedSymbol] = useState("-");
  const [loadingSymbol, setLoadingSymbol] = useState(false);

  const [priceSeriesBySymbol, setPriceSeriesBySymbol] = useState({}); // { [symbol]: [{date, open, high, low, close, volume}] }
  const [selectedDayBySymbol, setSelectedDayBySymbol] = useState({}); // { [symbol]: index }
  const priceSeriesBySymbolRef = useRef({});
  const realtimeSeriesBySymbolRef = useRef({});

  const [sharesInput, setSharesInput] = useState("1");

  const [pinIsSet, setPinIsSet] = useState(false);
  const [pinStatusLoaded, setPinStatusLoaded] = useState(false);
  const [setupPin, setSetupPin] = useState("");
  const [setupPinConfirm, setSetupPinConfirm] = useState("");
  const [setupPinBusy, setSetupPinBusy] = useState(false);
  const [pinGate, setPinGate] = useState({ open: false, action: null });
  const [tradePinInput, setTradePinInput] = useState("");
  const [pinGateBusy, setPinGateBusy] = useState(false);
  const [showPinChangeForm, setShowPinChangeForm] = useState(false);
  const [oldPinForChange, setOldPinForChange] = useState("");

  useEffect(() => {
    const email = user?.email?.trim();
    if (!email) {
      const timeoutId = window.setTimeout(() => {
        setPinStatusLoaded(false);
        setPinIsSet(false);
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }
    const statusTimeoutId = window.setTimeout(() => {
      setPinStatusLoaded(false);
    }, 0);
    let cancelled = false;
    (async () => {
      try {
        const res = await api.post("/api/simulation/pin/status", { email });
        if (!cancelled && res?.data?.success) {
          setPinIsSet(Boolean(res.data.pin_set));
        } else if (!cancelled) {
          setPinIsSet(false);
        }
      } catch (e) {
        console.error("Failed to load PIN status", e);
        if (!cancelled) setPinIsSet(false);
      } finally {
        if (!cancelled) setPinStatusLoaded(true);
      }
    })();
    return () => {
      window.clearTimeout(statusTimeoutId);
      cancelled = true;
    };
  }, [user?.email]);

  useEffect(() => {
    const email = user?.email?.trim();
    if (!email) {
      const timeoutId = window.setTimeout(() => {
        setSimulationHydrated(false);
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }

    let cancelled = false;
    const loadSimulationState = async () => {
      setSimulationLoading(true);
      try {
        const res = await api.post("/api/simulation/state/get", { email });
        const state = res?.data?.state;

        if (!cancelled && res?.data?.success && res?.data?.exists && state) {
          setCash(Number(state.cash) || 0);
          setHoldings(state.holdings || {});
          setTrades(Array.isArray(state.trades) ? state.trades : []);
          setSimulationStarted(Boolean(state.simulation_started));
        }
      } catch (e) {
        console.error("Failed to load simulation state", e);
      } finally {
        if (!cancelled) {
          setSimulationHydrated(true);
          setSimulationLoading(false);
        }
      }
    };

    const hydrateTimeoutId = window.setTimeout(() => {
      setSimulationHydrated(false);
      loadSimulationState();
    }, 0);

    return () => {
      window.clearTimeout(hydrateTimeoutId);
      cancelled = true;
    };
  }, [user?.email]);

  useEffect(() => {
    const email = user?.email?.trim();
    if (!email || !simulationHydrated) return;

    const timeoutId = setTimeout(async () => {
      try {
        await api.post("/api/simulation/state/save", {
          email,
          cash,
          holdings,
          trades,
          simulation_started: simulationStarted,
        });
      } catch (e) {
        console.error("Failed to save simulation state", e);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [user?.email, cash, holdings, trades, simulationStarted, simulationHydrated]);

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
  /** realtime: 최근 N거래일 | historical: 시작~종료일 기간 */
  const [chartSource, setChartSource] = useState("realtime");
  const [chartSourceBySymbol, setChartSourceBySymbol] = useState({});
  const activeChartSource =
    selectedSymbol && selectedSymbol !== "-"
      ? chartSourceBySymbol[selectedSymbol] ?? chartSource
      : chartSource;

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
  const effectiveChartMode = activeChartSource === "realtime" ? "ma" : chartMode;

  const series = useMemo(
    () => priceSeriesBySymbol[selectedSymbol] || [],
    [priceSeriesBySymbol, selectedSymbol]
  );

  useEffect(() => {
    priceSeriesBySymbolRef.current = priceSeriesBySymbol;
  }, [priceSeriesBySymbol]);
  const chartData = useMemo(() => enrichWithSma(series), [series]);
  const firstRealtimePointIndex = useMemo(
    () => (activeChartSource === "realtime" ? chartData.findIndex(hasRealtimePrice) : 0),
    [activeChartSource, chartData]
  );

  const realtimeSessionHighLow = useMemo(() => {
    if (activeChartSource !== "realtime" || !selectedSymbol || selectedSymbol === "-") return null;
    const prices = series
      .map((r) => Number(r.close))
      .filter((p) => Number.isFinite(p) && p > 0);
    if (!prices.length) return null;
    return { high: Math.max(...prices), low: Math.min(...prices) };
  }, [activeChartSource, series, selectedSymbol]);
  const realtimeFilledPointCount = useMemo(
    () => (activeChartSource === "realtime" ? getRealtimeFilledRows(series).length : series.length),
    [activeChartSource, series]
  );
  const chartDataCountLabel =
    activeChartSource === "realtime"
      ? `${realtimeFilledPointCount}/${REALTIME_CHART_MAX_POINTS}`
      : series.length
        ? String(series.length)
        : "";
  const selectedDayIndex = clamp(
    selectedDayBySymbol[selectedSymbol] ?? (series.length ? series.length - 1 : 0),
    0,
    Math.max(0, series.length - 1)
  );
  const currentRow = series[selectedDayIndex];
  const currentRowHasPrice = hasRealtimePrice(currentRow);
  const currentPrice = currentRowHasPrice ? Number(currentRow.close) : 0;
  const currentDate = currentRowHasPrice ? currentRow?.date || "" : "";
  const currentXKey = currentRowHasPrice ? currentRow?.xKey || currentDate : "";
  const currentTime = activeChartSource === "realtime" ? toRealtimeLabel(currentRow?.time || currentDate) : "";
  const currentDateTimeLabel =
    activeChartSource === "realtime" && currentTime
      ? `${toMarketDate(currentRow?.time || currentDate) || currentDate} ${currentTime}`
      : currentDate;
  const volumeLabel =
    activeChartSource === "realtime" && !hasVolume(currentRow)
      ? "실시간 거래량: 제공 안 됨"
      : "막대: 거래량";

  const handleSelectChartDay = useCallback(
    (index) => {
      if (!series.length) return;
      const next = clamp(index, 0, series.length - 1);
      setSelectedDayBySymbol((prev) => ({
        ...prev,
        [selectedSymbol]: next,
      }));
    },
    [selectedSymbol, series.length]
  );

  const { holdingList, getValuationPrice } = useValuationPrices(
    holdings,
    simulationStarted
  );

  const holdingSymbolsStr = useMemo(
    () => holdingList.map(([sym]) => sym).sort().join(","),
    [holdingList]
  );

  // 보유 종목 전체를 백그라운드 WebSocket으로 구독해 실시간 가격 수신
  const backgroundPrices = useBackgroundPrices(holdingSymbolsStr, simulationStarted);

  const getEnhancedValuationPrice = useCallback(
    (symbol) => {
      const bgPrice = backgroundPrices[symbol];
      if (bgPrice > 0) return bgPrice;
      return getValuationPrice(symbol);
    },
    [backgroundPrices, getValuationPrice]
  );

  const {
    totalValue,
    totalPnl,
    realizedPnl,
    unrealizedPnl,
  } = useMemo(
    () => computeSimulationMetrics(cash, holdings, getEnhancedValuationPrice),
    [cash, holdings, getEnhancedValuationPrice]
  );

  const canTrade = simulationStarted && currentPrice > 0 && pinIsSet && pinStatusLoaded;
  const holdingForSelected = holdings[selectedSymbol] || {
    shares: 0,
    avgCost: 0,
    realizedPnl: 0,
  };

  const selectedShares = Math.max(0, Number(holdingForSelected.shares) || 0);
  const desiredShares = Math.floor(Number(sharesInput) || 0);
  const {
    grossAmount: tradeGrossAmount,
    fee: tradeFee,
    buyCost,
    sellProceeds,
  } = calculateOrderAmounts(desiredShares, currentPrice);

  const resetAccount = async () => {
    const email = user?.email?.trim();
    const isAccountReset = simulationStarted;

    if (isAccountReset && email) {
      try {
        await api.post("/api/simulation/state/delete", { email });
      } catch (e) {
        console.error("Failed to delete simulation state", e);
      }
    }

    const nextCash = effectiveInitialCash;
    setCash(nextCash);
    setHoldings({});
    setTrades([]);
    setSimulationStarted(true);
    setSimulationHydrated(true);

    if (email) {
      try {
        await api.post("/api/simulation/state/save", {
          email,
          cash: nextCash,
          holdings: {},
          trades: [],
          simulation_started: true,
        });
      } catch (e) {
        console.error("Failed to save simulation state after reset", e);
      }
    }
  };

  const fetchSymbolSeries = async (symbol, sourceOverride) => {
    const normalized = (symbol || "").trim().toUpperCase();
    if (!normalized) return;

    const source = sourceOverride ?? chartSource;

    if (source === "historical" && dateRangeError) {
      alert(dateRangeError);
      return;
    }

    setLoadingSymbol(true);
    try {
      if (source === "realtime") {
        const savedRealtimeRows = realtimeSeriesBySymbolRef.current[normalized];
        const realtimeRows = Array.isArray(savedRealtimeRows) && savedRealtimeRows.length
          ? savedRealtimeRows
          : createRealtimePlaceholderRows();
        realtimeSeriesBySymbolRef.current = {
          ...realtimeSeriesBySymbolRef.current,
          [normalized]: realtimeRows,
        };
        priceSeriesBySymbolRef.current = {
          ...priceSeriesBySymbolRef.current,
          [normalized]: realtimeRows,
        };

        setPriceSeriesBySymbol((prev) => ({
          ...prev,
          [normalized]: realtimeRows,
        }));

        setChartSourceBySymbol((prev) => ({
          ...prev,
          [normalized]: source,
        }));

        setSelectedDayBySymbol((prev) => ({
          ...prev,
          [normalized]: Math.max(0, getLastFilledRowIndex(realtimeRows)),
        }));

        setSelectedSymbol(normalized);
        if (sourceOverride) setChartSource(source);
        return;
      }

      const res = await api.get(`/api/chart/history/${normalized}`, {
        params: {
          start_date: stockStartDateInput,
          end_date: stockEndDateInput,
          interval: "1d",
        },
      });

      const rawSeries = res?.data?.rows || [];
      const rawPoints = res?.data?.points || [];
      const nextSeries = rawSeries.length
        ? rawSeries.map((row) => ({
            ...row,
            xKey: row.xKey || row.date,
            time: row.time || row.date,
          }))
        : rawPoints
            .map((point, index, points) =>
              pointToRealtimeRow(
                point,
                index > 0 ? pointToRealtimeRow(points[index - 1]) : null
              )
            )
            .filter(Boolean);

      if (!Array.isArray(nextSeries) || nextSeries.length === 0) {
        alert("해당 종목의 주가 데이터를 불러올 수 없습니다.");
        return;
      }

      let filteredSeries = nextSeries;
      if (source === "historical") {
        filteredSeries = nextSeries.filter((r) => {
          const d = r?.date;
          if (!d) return false;
          return d >= stockStartDateInput && d <= stockEndDateInput;
        });
        if (filteredSeries.length === 0) {
          alert("해당 기간(start~end)의 주가 데이터를 불러올 수 없습니다.");
          return;
        }
      }

      setPriceSeriesBySymbol((prev) => ({
        ...prev,
        [normalized]: filteredSeries,
      }));

      setChartSourceBySymbol((prev) => ({
        ...prev,
        [normalized]: source,
      }));

      setSelectedDayBySymbol((prev) => ({
        ...prev,
        [normalized]: filteredSeries.length - 1,
      }));

      setSelectedSymbol(normalized);
      if (sourceOverride) setChartSource(source);
    } catch (e) {
      console.error(e);
      alert("서버 통신 오류가 발생했습니다.");
    } finally {
      setLoadingSymbol(false);
    }
  };

  const initialTickerRef = useRef(null);
  useEffect(() => {
    if (!initialTicker || initialTicker === initialTickerRef.current) return;
    initialTickerRef.current = initialTicker;
    setSymbolInput(initialTicker);
    void fetchSymbolSeries(initialTicker, "realtime");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialTicker]);

  const handleChartSourceChange = (mode) => {
    setChartSource(mode);
    if (mode === "realtime") {
      setChartMode("ma");
    }
    const sym = (symbolInput || selectedSymbol || "").trim().toUpperCase();
    if (sym && sym !== "-") {
      void fetchSymbolSeries(sym, mode);
    }
  };

  useEffect(() => {
    if (!selectedSymbol || selectedSymbol === "-" || activeChartSource !== "realtime") {
      return undefined;
    }
    if (typeof WebSocket === "undefined") return undefined;

    const socket = new WebSocket(getWebSocketUrl(`/api/chart/ws/${selectedSymbol}`));

    socket.onmessage = (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }

      if (payload?.type !== "tick") return;
      if (String(payload.symbol || "").toUpperCase() !== selectedSymbol) return;

      const rows =
        realtimeSeriesBySymbolRef.current[selectedSymbol] ||
        priceSeriesBySymbolRef.current[selectedSymbol] ||
        [];
      const filledRows = getRealtimeFilledRows(rows);
      const lastRow = filledRows[filledRows.length - 1] || null;
      const nextRow = tickToDailyRealtimeRow(payload, lastRow);
      if (!nextRow) return;

      const nextRows = mergeRealtimeTickRow(rows, nextRow, REALTIME_CHART_MAX_POINTS);

      const nextSeriesBySymbol = {
        ...priceSeriesBySymbolRef.current,
        [selectedSymbol]: nextRows,
      };
      realtimeSeriesBySymbolRef.current = {
        ...realtimeSeriesBySymbolRef.current,
        [selectedSymbol]: nextRows,
      };
      priceSeriesBySymbolRef.current = nextSeriesBySymbol;
      setPriceSeriesBySymbol(nextSeriesBySymbol);

      const lastFilledIndex = getLastFilledRowIndex(nextRows);
      if (lastFilledIndex >= 0) {
        setSelectedDayBySymbol((selectedPrev) => ({
          ...selectedPrev,
          [selectedSymbol]: lastFilledIndex,
        }));
      }
    };

    return () => {
      socket.close();
    };
  }, [selectedSymbol, activeChartSource]);

  useEffect(() => {
    if (!selectedSymbol || selectedSymbol === "-") return;
    const saved = chartSourceBySymbol[selectedSymbol];
    if (!saved) return;
    const timeoutId = window.setTimeout(() => {
      setChartSource(saved);
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [selectedSymbol, chartSourceBySymbol]);

  // NOTE: 이 컴포넌트는 사용자가 종목을 조회했을 때만 API를 호출합니다.

  const submitSetupPin = async () => {
    const email = user?.email?.trim();
    if (!email) return;
    if (setupPin.length !== 4 || setupPinConfirm.length !== 4 || !/^\d{4}$/.test(setupPin)) {
      alert("PIN은 4자리 숫자만 입력해주세요.");
      return;
    }
    if (setupPin !== setupPinConfirm) {
      alert("PIN과 확인 입력이 일치하지 않습니다.");
      return;
    }
    if (pinIsSet) {
      if (!showPinChangeForm) {
        alert("「PIN 변경」을 눌러 변경 폼을 연 뒤 입력해주세요.");
        return;
      }
      if (oldPinForChange.length !== 4 || !/^\d{4}$/.test(oldPinForChange)) {
        alert("기존 PIN 4자리를 입력해주세요.");
        return;
      }
    }
    setSetupPinBusy(true);
    try {
      const body = pinIsSet
        ? { email, pin: setupPin, old_pin: oldPinForChange }
        : { email, pin: setupPin };
      const res = await api.post("/api/simulation/pin/set", body);
      if (res?.data?.success) {
        setPinIsSet(true);
        setSetupPin("");
        setSetupPinConfirm("");
        setOldPinForChange("");
        setShowPinChangeForm(false);
        alert(res.data.msg || "저장되었습니다.");
      } else {
        alert(res?.data?.msg || "PIN 저장에 실패했습니다.");
      }
    } catch (e) {
      console.error(e);
      alert("서버 오류로 PIN을 저장하지 못했습니다.");
    } finally {
      setSetupPinBusy(false);
    }
  };

  const requestBuy = () => {
    if (!simulationStarted || !currentPrice || !pinIsSet || !pinStatusLoaded) return;
    if (desiredShares <= 0) {
      alert("매수할 수량을 입력해주세요.");
      return;
    }
    if (buyCost > cash) {
      alert(`가상 현금이 부족합니다. 필요: ${formatMoney(buyCost)}(수수료 ${formatMoney(tradeFee)} 포함), 보유: ${formatMoney(cash)}`);
      return;
    }
    setTradePinInput("");
    setPinGate({ open: true, action: "buy" });
  };

  const requestSell = () => {
    if (!simulationStarted || !currentPrice || !pinIsSet || !pinStatusLoaded) return;
    if (desiredShares <= 0) {
      alert("매도할 수량을 입력해주세요.");
      return;
    }
    if (desiredShares > selectedShares) {
      alert("보유 수량을 초과해서 매도할 수 없습니다.");
      return;
    }
    setTradePinInput("");
    setPinGate({ open: true, action: "sell" });
  };

  const confirmTradePin = async () => {
    const action = pinGate.action;
    const email = user?.email?.trim();
    if (!email || !action) return;
    const pin = tradePinInput.trim();
    if (!/^\d{4}$/.test(pin)) {
      alert("PIN 4자리 숫자를 입력해주세요.");
      return;
    }
    setPinGateBusy(true);
    try {
      const res = await api.post("/api/simulation/pin/verify", { email, pin });
      if (!res?.data?.success) {
        alert(res?.data?.msg || "PIN이 일치하지 않습니다.");
        return;
      }
      setPinGate({ open: false, action: null });
      setTradePinInput("");
      if (action === "buy") buy();
      else if (action === "sell") sell();
    } catch (e) {
      console.error(e);
      alert("PIN 확인 중 오류가 발생했습니다.");
    } finally {
      setPinGateBusy(false);
    }
  };

  const buy = () => {
    if (!canTrade) return;
    if (desiredShares <= 0) {
      alert("매수할 수량을 입력해주세요.");
      return;
    }
    if (buyCost > cash) {
      alert(`가상 현금이 부족합니다. 필요: ${formatMoney(buyCost)}(수수료 ${formatMoney(tradeFee)} 포함), 보유: ${formatMoney(cash)}`);
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
        fee: tradeFee,
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
      const realized = (currentPrice - prevAvg) * desiredShares - tradeFee;

      return {
        ...prev,
        [selectedSymbol]: {
          shares: remainingShares,
          avgCost: remainingShares > 0 ? prevAvg : 0,
          realizedPnl: (Number(prevHolding?.realizedPnl) || 0) + realized,
        },
      };
    });

    const realizedForTrade =
      (currentPrice - Number(holdingForSelected.avgCost || 0)) * desiredShares - tradeFee;
    setTrades((prev) => [
      {
        id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
        type: "SELL",
        symbol: selectedSymbol,
        date: currentDate,
        price: currentPrice,
        shares: desiredShares,
        fee: tradeFee,
        cashFlow: sellProceeds,
        realizedPnl: realizedForTrade,
      },
      ...prev,
    ]);
  };

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
              <div className="text-xs text-emerald-300 whitespace-nowrap">
                보너스 +{formatMoney(rewardCash)}
              </div>
            </div>
          ) : null}

          <button
            type="button"
            onClick={() => void resetAccount()}
            disabled={simulationLoading}
            className="px-5 py-2 rounded-lg font-semibold transition-colors bg-blue-600 hover:bg-blue-500 text-white"
          >
            {simulationLoading
              ? "불러오는 중"
              : simulationStarted
              ? "계좌 초기화"
              : "시뮬레이션 시작"}
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
              {/* {!simulationStarted ? (
                <div className="mt-1 text-[11px] text-slate-500">
                  시작 시 {formatMoney(baseInitialCash)} + 보너스 {formatMoney(rewardCash)} ={" "}
                  {formatMoney(effectiveInitialCash)}
                </div>
              ) : null} */}
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
            <div className="flex flex-wrap gap-1.5 mb-3">
              {[
                { id: "realtime", label: "실시간 차트" },
                { id: "historical", label: "과거 차트" },
              ].map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => handleChartSourceChange(id)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-colors ${
                    chartSource === id
                      ? "bg-blue-600 border-blue-500 text-white"
                      : "bg-slate-900/80 border-slate-600 text-slate-300 hover:border-slate-500"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <div className="text-white font-semibold whitespace-nowrap">종목</div>
              <input
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                className="min-w-[8rem] flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="예: TSLA, AAPL"
                onKeyDown={(e) => e.key === "Enter" && fetchSymbolSeries(symbolInput)}
              />
              {chartSource === "historical" ? (
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
              ) : null}
              {chartSource === "historical" && dateRangeError ? (
                <div className="text-red-400 text-[11px] leading-tight w-full sm:w-auto">
                  {dateRangeError}
                </div>
              ) : null}
              <button
                type="button"
                onClick={() => fetchSymbolSeries(symbolInput)}
                disabled={loadingSymbol || (chartSource === "historical" && Boolean(dateRangeError))}
                className="px-4 py-2 rounded-lg font-semibold bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 shrink-0"
              >
                {loadingSymbol ? "조회 중" : "조회"}
              </button>
            </div>

            {/* S&P 500 섹터 종목 피커 */}
            <div>
              {/* 섹터 탭 */}
              <div className="flex gap-1.5 overflow-x-auto pb-2 mb-3 custom-scrollbar">
                {SP500_SECTORS.map((sector) => (
                  <button
                    key={sector.id}
                    onClick={() => { setActiveSector(sector.id); setSelectedTickerInfo(null); }}
                    className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap border transition-colors shrink-0 ${
                      activeSector === sector.id
                        ? "bg-blue-600 border-blue-500 text-white"
                        : "bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-500"
                    }`}
                  >
                    {sector.name}
                  </button>
                ))}
              </div>

              {/* 선택된 섹터의 종목 그리드 */}
              {SP500_SECTORS.filter((s) => s.id === activeSector).map((sector) => (
                <div key={sector.id} className="flex flex-wrap gap-2 mb-3">
                  {sector.tickers.map((t) => (
                    <button
                      key={t.symbol}
                      onClick={() => {
                        setSymbolInput(t.symbol);
                        setSelectedTickerInfo(t);
                        fetchSymbolSeries(t.symbol);
                      }}
                      className={`flex flex-col items-start px-3 py-1.5 rounded-lg border text-xs transition-colors ${
                        selectedTickerInfo?.symbol === t.symbol
                          ? "bg-blue-600/20 border-blue-500 text-blue-300"
                          : "bg-slate-900 border-slate-700 text-slate-200 hover:border-slate-500"
                      }`}
                    >
                      <span className="font-bold">{t.symbol}</span>
                      <span className="text-slate-400 text-[10px]">{t.name}</span>
                    </button>
                  ))}
                </div>
              ))}

              {/* 선택 종목 설명 카드 */}
              {selectedTickerInfo && (
                <div className="rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-3 text-sm mb-1">
                  <span className="font-bold text-white">{selectedTickerInfo.symbol}</span>
                  <span className="text-slate-400 ml-2 text-xs">{selectedTickerInfo.name}</span>
                  <p className="mt-1 text-slate-300 leading-relaxed text-xs">{selectedTickerInfo.desc}</p>
                </div>
              )}
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
                  const px = getEnhancedValuationPrice(sym);
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
                </div>
                {!simulationStarted ? (
                  <div className="text-amber-400 text-xs font-semibold sm:text-right">
                    먼저 “시뮬레이션 시작”이 필요해요.
                  </div>
                ) : !series.length ? (
                  <div className="text-slate-500 text-xs sm:text-right">종목을 조회한 뒤 거래할 수 있어요.</div>
                ) : !pinStatusLoaded ? (
                  <div className="text-slate-500 text-xs sm:text-right">거래 PIN 확인 중</div>
                ) : !pinIsSet ? (
                  <div className="text-amber-400 text-xs font-semibold sm:text-right">
                    아래에서 거래 PIN(4자리)을 먼저 설정해주세요.
                  </div>
                ) : null}
              </div>

              {simulationStarted && pinStatusLoaded && !pinIsSet ? (
                <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 space-y-3">
                  <div className="text-amber-200 text-sm font-semibold">거래 PIN 설정 (4자리 숫자)</div>
                  <p className="text-amber-100/80 text-xs">
                    매수·매도 시마다 입력합니다. 서버에는 암호화 해시만 저장됩니다.
                  </p>
                  <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
                    <div className="flex-1 min-w-0">
                      <label className="block text-amber-100/90 text-xs mb-1">PIN</label>
                      <input
                        type="password"
                        inputMode="numeric"
                        maxLength={4}
                        value={setupPin}
                        onChange={(e) => setSetupPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
                        className="w-full max-w-[11rem] bg-slate-900 border border-amber-500/30 rounded-lg px-3 py-2 text-white tracking-widest outline-none focus:ring-2 focus:ring-amber-500"
                        placeholder="••••"
                        autoComplete="new-password"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <label className="block text-amber-100/90 text-xs mb-1">PIN 확인</label>
                      <input
                        type="password"
                        inputMode="numeric"
                        maxLength={4}
                        value={setupPinConfirm}
                        onChange={(e) => setSetupPinConfirm(e.target.value.replace(/\D/g, "").slice(0, 4))}
                        className="w-full max-w-[11rem] bg-slate-900 border border-amber-500/30 rounded-lg px-3 py-2 text-white tracking-widest outline-none focus:ring-2 focus:ring-amber-500"
                        placeholder="••••"
                        autoComplete="new-password"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => void submitSetupPin()}
                      disabled={setupPinBusy || setupPin.length !== 4 || setupPinConfirm.length !== 4}
                      className="px-4 py-2 rounded-lg font-semibold bg-amber-600 hover:bg-amber-500 text-white text-sm disabled:opacity-50 shrink-0"
                    >
                      {setupPinBusy ? "저장 중" : "PIN 저장"}
                    </button>
                  </div>
                </div>
              ) : null}

              {pinIsSet ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span>거래 PIN이 설정되어 있습니다.</span>
                    <button
                      type="button"
                      className="text-blue-400 hover:underline"
                      onClick={() => {
                        setShowPinChangeForm((v) => !v);
                        setOldPinForChange("");
                        setSetupPin("");
                        setSetupPinConfirm("");
                      }}
                    >
                      {showPinChangeForm ? "PIN 변경 취소" : "PIN 변경"}
                    </button>
                  </div>
                  {showPinChangeForm ? (
                    <div className="rounded-xl border border-slate-600 bg-slate-900/50 p-4 space-y-3">
                      <div className="text-slate-300 text-xs font-semibold">새 PIN으로 변경</div>
                      <div className="flex flex-col sm:flex-row gap-3 sm:items-end flex-wrap">
                        <div>
                          <label className="block text-slate-400 text-xs mb-1">기존 PIN</label>
                          <input
                            type="password"
                            inputMode="numeric"
                            maxLength={4}
                            value={oldPinForChange}
                            onChange={(e) =>
                              setOldPinForChange(e.target.value.replace(/\D/g, "").slice(0, 4))
                            }
                            className="w-full max-w-[11rem] bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white tracking-widest outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="••••"
                            autoComplete="off"
                          />
                        </div>
                        <div>
                          <label className="block text-slate-400 text-xs mb-1">새 PIN</label>
                          <input
                            type="password"
                            inputMode="numeric"
                            maxLength={4}
                            value={setupPin}
                            onChange={(e) => setSetupPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
                            className="w-full max-w-[11rem] bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white tracking-widest outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="••••"
                            autoComplete="new-password"
                          />
                        </div>
                        <div>
                          <label className="block text-slate-400 text-xs mb-1">새 PIN 확인</label>
                          <input
                            type="password"
                            inputMode="numeric"
                            maxLength={4}
                            value={setupPinConfirm}
                            onChange={(e) =>
                              setSetupPinConfirm(e.target.value.replace(/\D/g, "").slice(0, 4))
                            }
                            className="w-full max-w-[11rem] bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white tracking-widest outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="••••"
                            autoComplete="new-password"
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() => void submitSetupPin()}
                          disabled={
                            setupPinBusy ||
                            oldPinForChange.length !== 4 ||
                            setupPin.length !== 4 ||
                            setupPinConfirm.length !== 4
                          }
                          className="px-4 py-2 rounded-lg font-semibold bg-blue-600 hover:bg-blue-500 text-white text-sm disabled:opacity-50 shrink-0"
                        >
                          {setupPinBusy ? "저장 중" : "새 PIN 저장"}
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

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
                </div>
                <div className="flex gap-2 shrink-0 w-full sm:w-auto">
                  <button
                    type="button"
                    onClick={requestBuy}
                    disabled={!canTrade || desiredShares <= 0 || pinGateBusy}
                    className="flex-1 sm:flex-initial sm:min-w-[7rem] px-4 py-2.5 rounded-xl font-bold bg-blue-600 hover:bg-blue-500 text-white text-sm disabled:opacity-50"
                  >
                    매수
                  </button>
                  <button
                    type="button"
                    onClick={requestSell}
                    disabled={
                      !canTrade || desiredShares <= 0 || desiredShares > selectedShares || pinGateBusy
                    }
                    className="flex-1 sm:flex-initial sm:min-w-[7rem] px-4 py-2.5 rounded-xl font-bold bg-slate-900 hover:bg-slate-800 border border-slate-700 text-white text-sm disabled:opacity-50"
                  >
                    매도
                  </button>
                </div>
              </div>
            </div>

          </div>

          <div className="relative z-0 bg-slate-800/30 border border-slate-700 rounded-2xl p-4 min-h-0 isolate">
            <div className="flex flex-col gap-3 mb-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="text-white font-semibold text-lg">거래 차트</div>
                <div className="text-slate-400 text-xs mt-1">
                  {selectedSymbol} ·{" "}
                  <span
                    className={
                      activeChartSource === "realtime" ? "text-emerald-400" : "text-amber-400"
                    }
                  >
                    {activeChartSource === "realtime"
                      ? `실시간`
                      : `과거`}
                  </span>
                  <span className="text-slate-600"> · </span>
                  {activeChartSource === "realtime" ? "선택 시간:" : "선택 날짜:"}{" "}
                  <span className="text-white font-semibold">{currentDateTimeLabel || "—"}</span>
                  {activeChartSource === "realtime" && currentTime ? (
                    <>
                      <span className="text-slate-600"> · </span>
                      <span className="text-emerald-400 font-semibold">실시간 반영</span>
                    </>
                  ) : null}
                  {currentPrice > 0 ? (
                    <>
                      <span className="text-slate-600"> · </span>
                      현재가: <span className="text-white font-semibold">{formatMoney(currentPrice)}</span>
                    </>
                  ) : null}
                  <span className="text-slate-600"> · </span>
                  <span className="text-slate-500">{volumeLabel}</span>
                  {effectiveChartMode === "ma" ? (
                    <span className="text-slate-600"> · </span>
                  ) : null}
                  {effectiveChartMode === "ma" ? (
                    <span className="text-slate-500">
                      노랑 5일 · 빨강 20일 · 초록 60일 이평
                    </span>
                  ) : null}
                </div>
              </div>
              <div className="flex flex-col items-stretch sm:items-end gap-2 shrink-0">
                <div className="flex flex-wrap gap-1.5 justify-end">
                  {[
                    { id: "realtime", label: "\uC2E4\uC2DC\uAC04" },
                    { id: "historical", label: "\uACFC\uAC70" },
                  ].map(({ id, label }) => (
                    <button
                      key={id}
                      type="button"
                      aria-label={`${id} chart`}
                      onClick={() => handleChartSourceChange(id)}
                      disabled={loadingSymbol}
                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-colors disabled:opacity-50 ${
                        chartSource === id
                          ? "bg-emerald-600 border-emerald-500 text-white"
                          : "bg-slate-900/80 border-slate-600 text-slate-300 hover:border-slate-500"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {activeChartSource === "historical" ? (
                  <div className="flex flex-wrap gap-1.5 justify-end">
                    {[
                      { id: "ma", label: "\uC774\uD3C9\uC120" },
                      { id: "candle", label: "\uCE94\uB4E4" },
                    ].map(({ id, label }) => (
                      <button
                        key={id}
                        type="button"
                        aria-label={`${id} chart mode`}
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
                ) : null}
                <div className="text-right text-xs text-slate-500" data-testid="simulation-chart-data-count">
                  {chartDataCountLabel ? `\uB370\uC774\uD130: ${chartDataCountLabel}\uAC1C` : ""}
                </div>
              </div>
            </div>

            {activeChartSource === "realtime" && !isNyseOpen() && (() => {
              const kst = getNyseKstLabel();
              return (
                <div className="mb-3 rounded-lg border border-amber-900/50 bg-amber-900/20 px-4 py-3 text-sm text-amber-300">
                  <div className="flex items-center gap-2 font-semibold mb-1">
                    <span>🔴</span>
                    <span>현재 미국 주식 시장이 닫혀 있습니다</span>
                  </div>
                  <div className="text-xs text-amber-400/80 space-y-0.5 pl-6">
                    <div>NYSE 운영시간 · 미국(ET): 월~금 오전 9:30 ~ 오후 4:00</div>
                    <div>NYSE 운영시간 · 한국(KST): 월~금 {kst.open} ~ {kst.close}</div>
                    <div className="text-amber-500/60 mt-1">실시간 데이터가 지연되거나 수신되지 않을 수 있습니다.</div>
                  </div>
                </div>
              );
            })()}

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
                      dataKey="xKey"
                      tick={{ fill: "#94a3b8", fontSize: 12 }}
                      tickFormatter={(val, index) =>
                        formatChartXAxisTick(
                          val,
                          index,
                          activeChartSource,
                          firstRealtimePointIndex >= 0 ? firstRealtimePointIndex : 0
                        )
                      }
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
                      content={(props) => (
                        <ChartOhlcTooltip
                          {...props}
                          isRealtime={activeChartSource === "realtime"}
                          sessionHigh={realtimeSessionHighLow?.high}
                          sessionLow={realtimeSessionHighLow?.low}
                        />
                      )}
                      shared
                      allowEscapeViewBox={{ x: false, y: true }}
                      cursor={{ stroke: "#94a3b8", strokeWidth: 1, strokeDasharray: "4 4" }}
                      wrapperStyle={{ outline: "none", zIndex: 50 }}
                    />
                    {currentXKey ? (
                      <ReferenceLine
                        yAxisId="price"
                        x={currentXKey}
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
                    {effectiveChartMode === "candle" ? (
                      <Customized
                        component={() => <CandlestickMarks data={chartData} />}
                      />
                    ) : null}
                    {effectiveChartMode === "ma" ? (
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
                    {effectiveChartMode === "candle" ? (
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
                    <Customized
                      component={() => (
                        <ChartDayClickBands
                          data={chartData}
                          selectedIndex={selectedDayIndex}
                          onSelectDay={handleSelectChartDay}
                        />
                      )}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-[380px] flex items-center justify-center text-slate-500 bg-slate-900/30 rounded-xl border border-slate-700">
                종목을 조회하면 가격 차트가 표시됩니다.
              </div>
            )}
          </div>
        </div>
      </div>

      {pinGate.open ? (
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="trade-pin-title"
        >
          <div className="w-full max-w-sm rounded-2xl border border-slate-600 bg-slate-900 p-6 shadow-xl space-y-4">
            <div id="trade-pin-title" className="text-lg font-bold text-white">
              {pinGate.action === "buy" ? "매수" : "매도"}
            </div>
            <p className="text-slate-400 text-sm">4자리 PIN을 입력하세요.</p>
            <input
              type="password"
              inputMode="numeric"
              maxLength={4}
              value={tradePinInput}
              onChange={(e) => setTradePinInput(e.target.value.replace(/\D/g, "").slice(0, 4))}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-3 text-white text-center text-xl tracking-[0.4em] outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••"
              autoComplete="one-time-code"
              onKeyDown={(e) => {
                if (e.key === "Enter") void confirmTradePin();
              }}
            />
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => {
                  setPinGate({ open: false, action: null });
                  setTradePinInput("");
                }}
                disabled={pinGateBusy}
                className="px-4 py-2 rounded-lg text-slate-300 hover:bg-slate-800 text-sm disabled:opacity-50"
              >
                취소
              </button>
              <button
                type="button"
                onClick={() => void confirmTradePin()}
                disabled={pinGateBusy || tradePinInput.length !== 4}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold disabled:opacity-50"
              >
                {pinGateBusy ? "확인 중" : "확인"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
