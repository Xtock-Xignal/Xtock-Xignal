import { useEffect, useMemo, useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import api from "../utils/api";

const STOCK_ROWS = [
  { symbol: "TSLA", name: "Tesla", price: "$218.30", change: "+3.12%", prediction: "+1.8%", keywords: "#EV #일론머스크 #전기차" },
  { symbol: "NVDA", name: "NVIDIA", price: "$1,020.55", change: "+2.45%", prediction: "+1.2%", keywords: "#AI #GPU #데이터센터" },
  { symbol: "AAPL", name: "Apple Inc.", price: "$197.40", change: "-0.75%", prediction: "-0.3%", keywords: "#iPhone #서비스 #하드웨어" },
  { symbol: "AMZN", name: "Amazon", price: "$185.22", change: "+1.05%", prediction: "+0.7%", keywords: "#AWS #전자상거래 #클라우드" },
  { symbol: "MSFT", name: "Microsoft", price: "$412.67", change: "-0.92%", prediction: "-0.5%", keywords: "#Azure #AI #오피스365" },
  { symbol: "META", name: "Meta Platforms", price: "$488.34", change: "+1.55%", prediction: "+1.1%", keywords: "#SNS #AI #메타버스" },
  { symbol: "GOOGL", name: "Alphabet (Google)", price: "$153.20", change: "+0.68%", prediction: "+0.4%", keywords: "#검색엔진 #광고 #클라우드" },
  { symbol: "NFLX", name: "Netflix", price: "$489.50", change: "+1.3%", prediction: "+0.49%", keywords: "#스트리밍 #오리지널콘텐츠 #구독서비스" },
];

const formatMoney = (value) => {
  const n = Number(value);
  if (!Number.isFinite(n)) return "$0";
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};

const getWebSocketUrl = (path) => {
  const base = api.defaults?.baseURL || "http://localhost:8000";
  const url = new URL(path, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
};

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

const toMarketDate = (timeValue) => {
  const normalized = normalizeMarketTime(timeValue);
  if (!normalized) return "";
  const d = new Date(normalized);
  if (Number.isFinite(d.getTime())) return d.toISOString().slice(0, 10);
  return String(normalized).slice(0, 10);
};

const tickToChartRow = (tick, previousRow = null) => {
  const tickRow = tick?.row && typeof tick.row === "object" ? tick.row : null;
  const price = Number(tickRow?.close ?? tick?.price);
  if (!Number.isFinite(price) || price <= 0) return null;

  const tickTime = normalizeMarketTime(tickRow?.time || tick?.time || tickRow?.date);
  const date = toMarketDate(tickRow?.date || tickTime) || new Date().toISOString().slice(0, 10);
  const rowOpen = Number(tickRow?.open);
  const previousClose = Number(previousRow?.close);
  const open = Number.isFinite(rowOpen) && rowOpen > 0
    ? rowOpen
    : Number.isFinite(previousClose) && previousClose > 0
      ? previousClose
      : price;
  const rowHigh = Number(tickRow?.high);
  const rowLow = Number(tickRow?.low);
  const tickVolume = Number(tickRow?.volume ?? tick?.volume);
  const volume = Number.isFinite(tickVolume) && tickVolume > 0 ? tickVolume : null;

  if (previousRow?.date === date) {
    const previousHigh = Number(previousRow.high);
    const previousLow = Number(previousRow.low);
    return {
      ...previousRow,
      time: tickTime || previousRow.time || previousRow.date,
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
    date,
    time: tickTime || date,
    open,
    high: Math.max(open, Number.isFinite(rowHigh) ? rowHigh : price, price),
    low: Math.min(open, Number.isFinite(rowLow) ? rowLow : price, price),
    close: price,
    volume,
  };
};

export default function DashboardSection() {
  const [summary, setSummary] = useState(null);
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [chartRows, setChartRows] = useState([]);
  const [latestTick, setLatestTick] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get("/api/dashboard/summary");
        if (!cancelled) setSummary(res?.data || null);
      } catch (e) {
        console.error("Failed to load dashboard summary", e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const topLabel = useMemo(() => {
    const top = summary?.topStock;
    if (!top?.symbol) return "Tesla (TSLA)";
    return `${top.name || top.symbol} (${top.symbol})`;
  }, [summary]);

  const openStock = async (symbol) => {
    setSelectedSymbol(symbol);
    setLatestTick(null);
    try {
      const res = await api.get(`/api/chart/history/${symbol}`, {
        params: { period: "1mo", interval: "1d" },
      });
      setChartRows(Array.isArray(res?.data?.rows) ? res.data.rows : []);
    } catch (e) {
      console.error("Failed to load chart history", e);
      setChartRows([]);
    }
  };

  useEffect(() => {
    if (!selectedSymbol || typeof WebSocket === "undefined") return undefined;
    const socket = new WebSocket(getWebSocketUrl(`/api/chart/ws/${selectedSymbol}`));
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload?.type === "tick" && payload.symbol === selectedSymbol) {
          setLatestTick(payload);
          setChartRows((prevRows) => {
            const rows = Array.isArray(prevRows) ? prevRows : [];
            const lastRow = rows[rows.length - 1] || null;
            const nextRow = tickToChartRow(payload, lastRow);
            if (!nextRow) return rows;
            if (lastRow?.date === nextRow.date) {
              return [...rows.slice(0, -1), nextRow];
            }
            return [...rows, nextRow].slice(-Math.max(1, rows.length || 1));
          });
        }
      } catch {
        // Ignore malformed websocket payloads.
      }
    };
    return () => socket.close();
  }, [selectedSymbol]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <p className="text-sm text-slate-400 mb-2">오늘의 인기 추천</p>
          <h3 className="text-2xl font-bold mb-1">{topLabel}</h3>
          <p className="text-emerald-400 text-lg font-semibold">
            {summary?.topStock ? `${Number(summary.topStock.changePercent || 0).toFixed(2)}%` : "+3.12%"}
          </p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <p className="text-sm text-slate-400 mb-2">NASDAQ 지수</p>
          <h3 className="text-2xl font-bold mb-1">16,920.45</h3>
          <p className="text-emerald-400 text-lg font-semibold">+1.05%</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <p className="text-sm text-slate-400 mb-2">시장 예측 동향</p>
          <h3 className="text-2xl font-bold mb-1">긍정적</h3>
          <p className="text-emerald-400 text-lg font-semibold">↗ 상승 예측 우세</p>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">실시간 주가 변동 및 예측</h2>
          <div className="relative">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
              size={20}
            />
            <input
              type="text"
              placeholder="종목 검색"
              className="pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-slate-400 border-b border-slate-800">
                <th className="pb-3 font-medium">종목명</th>
                <th className="pb-3 font-medium">현재가</th>
                <th className="pb-3 font-medium">변동률</th>
                <th className="pb-3 font-medium">AI 예측</th>
                <th className="pb-3 font-medium">관련 키워드</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {STOCK_ROWS.map((row) => (
                <tr key={row.symbol} className="border-b border-slate-800">
                  <td className="py-4">
                    <button
                      type="button"
                      onClick={() => void openStock(row.symbol)}
                      className="text-left hover:text-blue-300"
                    >
                      {row.name}
                    </button>
                  </td>
                  <td className="py-4">{row.price}</td>
                  <td className={`py-4 ${row.change.startsWith("-") ? "text-rose-400" : "text-blue-400"}`}>
                    {row.change}
                  </td>
                  <td className={`py-4 ${row.prediction.startsWith("-") ? "text-rose-400" : "text-blue-400"}`}>
                    {row.prediction}
                  </td>
                  <td className="py-4 text-slate-400">{row.keywords}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {selectedSymbol ? (
          <div className="mt-5 border-t border-slate-800 pt-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <h3 className="text-white font-semibold">{selectedSymbol} 상세 차트</h3>
              {latestTick ? (
                <span className="text-emerald-400 text-sm font-semibold">
                  최신가 {formatMoney(latestTick.price)}
                </span>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2 text-sm text-slate-300">
              {chartRows.map((row) => (
                <span key={row.date} className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
                  {formatMoney(row.close)}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
