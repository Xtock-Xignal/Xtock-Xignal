import { Fragment, useEffect, useMemo, useState } from "react";
import { Search as SearchIcon, TrendingUp, TrendingDown, Activity, DollarSign, BarChart3, ChevronDown, ChevronUp } from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import api from "../utils/api";
import { SP500_LIST } from "../data/sp500_list";

const fmt = (n, digits = 2) =>
  Number.isFinite(Number(n))
    ? Number(n).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
    : "—";

const fmtCap = (cap) => {
  if (!cap || !Number.isFinite(cap)) return "—";
  if (cap > 1e12) return `$${(cap / 1e12).toFixed(2)}T`;
  if (cap > 1e9) return `$${(cap / 1e9).toFixed(2)}B`;
  return `$${cap.toLocaleString()}`;
};

const vixLevel = (price) => {
  const v = Number(price);
  if (!Number.isFinite(v) || v === 0) return { label: "—", color: "text-slate-400", bg: "bg-slate-700" };
  if (v < 15) return { label: "매우 안정", color: "text-emerald-400", bg: "bg-emerald-500/10" };
  if (v < 20) return { label: "안정", color: "text-emerald-400", bg: "bg-emerald-500/10" };
  if (v < 30) return { label: "주의", color: "text-amber-400", bg: "bg-amber-500/10" };
  if (v < 40) return { label: "공포", color: "text-rose-400", bg: "bg-rose-500/10" };
  return { label: "극도 공포", color: "text-rose-500", bg: "bg-rose-500/10" };
};

const ITEMS_PER_PAGE = 10;

export default function DashboardSection() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [expandedSymbol, setExpandedSymbol] = useState(null);
  const [expandedData, setExpandedData] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get("/api/dashboard/summary");
        if (!cancelled) setSummary(res?.data || null);
      } catch (e) {
        console.error("Failed to load dashboard summary", e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const topStock = summary?.topStock ?? null;
  const indices = Array.isArray(summary?.indices) ? summary.indices : [];

  const vixIndex = indices.find((i) => i.symbol === "^VIX");
  const mainIndices = indices.filter((i) => ["^GSPC", "^IXIC", "^DJI", "^TNX", "DX-Y.NYB"].includes(i.symbol));

  const priceRange = useMemo(() => {
    if (!topStock?.chartData?.length) return { min: 0, max: 0, percent: 50 };
    const prices = topStock.chartData.map((d) => d.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const current = topStock.price;
    const percent = max === min ? 50 : Math.max(0, Math.min(100, ((current - min) / (max - min)) * 100));
    return { min, max, percent };
  }, [topStock]);

  const isUp = (val) => Number(val) >= 0;

  const filteredList = useMemo(() => {
    const q = searchTerm.trim().toUpperCase();
    if (!q) return SP500_LIST;
    return SP500_LIST.filter(
      (s) => s.symbol.includes(q) || s.name.toUpperCase().includes(q)
    );
  }, [searchTerm]);

  const totalPages = Math.max(1, Math.ceil(filteredList.length / ITEMS_PER_PAGE));
  const currentList = filteredList.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const handleRowClick = async (symbol) => {
    if (expandedSymbol === symbol) {
      setExpandedSymbol(null);
      setExpandedData(null);
      return;
    }
    setExpandedSymbol(symbol);
    setExpandedData(null);
    setLoadingDetail(true);
    try {
      const res = await api.get(`/api/chart/history/${symbol}`, {
        params: { period: "1mo", interval: "1d" },
      });
      setExpandedData(Array.isArray(res?.data?.rows) ? res.data.rows : []);
    } catch (e) {
      console.error("Failed to load chart for", symbol, e);
      setExpandedData([]);
    } finally {
      setLoadingDetail(false);
    }
  };

  if (loading) {
    return (
      <div className="p-16 text-center text-slate-500 animate-pulse">
        시장 데이터를 불러오는 중...
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* ── 상단: 시총 1위 + VIX ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* 시총 1위 기업 */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity pointer-events-none">
            <Activity size={120} />
          </div>

          <div className="relative z-10">
            <span className="bg-blue-600 text-white text-xs font-bold px-2 py-1 rounded-full mb-3 inline-block tracking-wide">
              시총 1위
            </span>
            <div className="flex flex-col md:flex-row md:items-end gap-4 mb-5">
              <div>
                <h2 className="text-4xl font-black text-white tracking-tight">
                  {topStock?.symbol ?? "—"}
                </h2>
                <p className="text-slate-400 text-sm mt-0.5">Most Valuable Company</p>
              </div>
              <div className="flex items-baseline gap-3">
                <span className="text-4xl font-bold text-white">
                  ${fmt(topStock?.price)}
                </span>
                <span
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-base font-bold
                    ${isUp(topStock?.changePercent)
                      ? "bg-emerald-500/10 text-emerald-400"
                      : "bg-rose-500/10 text-rose-400"}`}
                >
                  {isUp(topStock?.changePercent) ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                  {isUp(topStock?.changePercent) ? "+" : ""}{fmt(topStock?.changePercent)}%
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* 시가총액 */}
              <div className="bg-black/20 rounded-xl p-4 border border-white/5">
                <p className="text-slate-400 text-xs font-bold uppercase flex items-center gap-1.5 mb-1">
                  <DollarSign size={13} /> 시가총액
                </p>
                <p className="text-2xl font-bold text-white">{fmtCap(topStock?.marketCap)}</p>
              </div>

              {/* 20일 가격 범위 */}
              <div className="bg-black/20 rounded-xl p-4 border border-white/5">
                <p className="text-slate-400 text-xs font-bold uppercase flex items-center gap-1.5 mb-3">
                  <BarChart3 size={13} /> 20일 가격 범위
                </p>
                <div className="h-2.5 bg-slate-700/60 rounded-full relative overflow-hidden">
                  <div
                    className={`absolute top-0 left-0 h-full rounded-full transition-all duration-700
                      ${isUp(topStock?.changePercent)
                        ? "bg-gradient-to-r from-emerald-700 to-emerald-400"
                        : "bg-gradient-to-r from-rose-700 to-rose-400"}`}
                    style={{ width: `${priceRange.percent}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-slate-400 mt-1.5 font-mono">
                  <span>${fmt(priceRange.min)}</span>
                  <span>${fmt(priceRange.max)}</span>
                </div>
              </div>
            </div>

            {/* 스파크라인 */}
            {topStock?.chartData?.length > 0 && (
              <div className="mt-4 h-[90px]">
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <AreaChart data={topStock.chartData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="topStockGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={isUp(topStock?.changePercent) ? "#10b981" : "#f43f5e"} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={isUp(topStock?.changePercent) ? "#10b981" : "#f43f5e"} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" hide />
                    <YAxis domain={["auto", "auto"]} hide />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", fontSize: 12 }}
                      formatter={(v) => [`$${fmt(v)}`, "종가"]}
                      labelFormatter={(l) => String(l).slice(5)}
                    />
                    <Area
                      type="monotone"
                      dataKey="price"
                      stroke={isUp(topStock?.changePercent) ? "#10b981" : "#f43f5e"}
                      strokeWidth={1.5}
                      fill="url(#topStockGrad)"
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>

        {/* VIX 공포지수 */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between">
          <div>
            <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">VIX 공포지수</p>
            <p className="text-slate-500 text-xs mb-4">시장 변동성 지표 (CBOE Volatility Index)</p>
            <div className="text-5xl font-black text-white mb-3 tracking-tight">
              {vixIndex ? fmt(vixIndex.price) : "—"}
            </div>
            {vixIndex && (
              <span className={`inline-block text-sm font-bold px-3 py-1 rounded-lg ${vixLevel(vixIndex.price).bg} ${vixLevel(vixIndex.price).color}`}>
                {vixLevel(vixIndex.price).label}
              </span>
            )}
          </div>
          <div className="mt-6 space-y-1.5 text-xs text-slate-500 border-t border-slate-800 pt-4">
            <div className="flex justify-between"><span>15 미만</span><span className="text-emerald-400">매우 안정</span></div>
            <div className="flex justify-between"><span>15 – 20</span><span className="text-emerald-400">안정</span></div>
            <div className="flex justify-between"><span>20 – 30</span><span className="text-amber-400">주의</span></div>
            <div className="flex justify-between"><span>30 – 40</span><span className="text-rose-400">공포</span></div>
            <div className="flex justify-between"><span>40 이상</span><span className="text-rose-500">극도 공포</span></div>
          </div>
          {vixIndex && (
            <div className={`mt-4 text-xs text-right ${isUp(vixIndex.changePercent) ? "text-rose-400" : "text-emerald-400"}`}>
              {isUp(vixIndex.changePercent) ? "+" : ""}{fmt(vixIndex.changePercent)}% 전일 대비
            </div>
          )}
        </div>
      </div>

      {/* ── 주요 지표 행 ── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {mainIndices.map((idx) => (
          <div
            key={idx.symbol}
            className="bg-slate-900 border border-slate-800 rounded-xl p-4 hover:border-slate-700 transition-colors"
          >
            <p className="text-slate-500 text-xs font-bold uppercase tracking-wide mb-2">{idx.name}</p>
            <p className="text-white text-lg font-bold leading-tight">
              {idx.symbol === "^TNX" || idx.symbol === "DX-Y.NYB"
                ? fmt(idx.price)
                : idx.price >= 1000
                  ? Number(idx.price).toLocaleString(undefined, { maximumFractionDigits: 0 })
                  : fmt(idx.price)}
              {idx.symbol === "^TNX" ? "%" : ""}
            </p>
            <p className={`text-xs font-semibold mt-1 ${isUp(idx.changePercent) ? "text-emerald-400" : "text-rose-400"}`}>
              {isUp(idx.changePercent) ? "+" : ""}{fmt(idx.changePercent)}%
            </p>
          </div>
        ))}
      </div>

      {/* ── S&P 500 종목 리스트 ── */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              S&P 500 종목 차트
              <span className="text-xs font-normal text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">
                {filteredList.length}개
              </span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">종목을 클릭하면 최근 1개월 차트를 확인할 수 있습니다.</p>
          </div>
          <div className="relative w-full sm:w-60">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
            <input
              type="text"
              placeholder="티커 또는 기업명 검색..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full pl-9 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-500 uppercase bg-slate-800/50">
              <tr>
                <th className="px-6 py-3 w-28">티커</th>
                <th className="px-6 py-3">기업명</th>
                <th className="px-6 py-3 text-right w-16"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {currentList.map((stock) => (
                <Fragment key={stock.symbol}>
                  <tr
                    onClick={() => handleRowClick(stock.symbol)}
                    className={`cursor-pointer transition-colors ${
                      expandedSymbol === stock.symbol
                        ? "bg-slate-800/70"
                        : "hover:bg-slate-800/40"
                    }`}
                  >
                    <td className="px-6 py-3.5 font-bold text-white font-mono">{stock.symbol}</td>
                    <td className="px-6 py-3.5 text-slate-300">{stock.name}</td>
                    <td className="px-6 py-3.5 text-right text-slate-500">
                      {expandedSymbol === stock.symbol ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </td>
                  </tr>

                  {expandedSymbol === stock.symbol && (
                    <tr>
                      <td colSpan={3} className="p-0 bg-slate-900/60 border-b border-slate-800">
                        <div className="p-5">
                          {loadingDetail ? (
                            <div className="py-10 text-center text-blue-400 text-sm animate-pulse">
                              {stock.symbol} 차트 데이터 불러오는 중...
                            </div>
                          ) : expandedData && expandedData.length > 0 ? (
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                              {/* 차트 */}
                              <div className="h-[280px] bg-black/20 rounded-xl p-4 border border-slate-700/50">
                                <p className="text-xs font-bold text-slate-400 mb-3">
                                  {stock.symbol} — 최근 1개월 종가
                                </p>
                                <ResponsiveContainer width="100%" height="90%" minWidth={0}>
                                  <AreaChart data={expandedData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                                    <defs>
                                      <linearGradient id={`grad-${stock.symbol}`} x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                      </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                                    <XAxis
                                      dataKey="date"
                                      stroke="#475569"
                                      tick={{ fontSize: 10, fill: "#64748b" }}
                                      tickFormatter={(v) => String(v).slice(5)}
                                      interval="preserveStartEnd"
                                    />
                                    <YAxis
                                      domain={["auto", "auto"]}
                                      stroke="#475569"
                                      width={52}
                                      tick={{ fontSize: 10, fill: "#64748b" }}
                                      tickFormatter={(v) => `$${Number(v).toLocaleString()}`}
                                    />
                                    <Tooltip
                                      contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", fontSize: 12 }}
                                      formatter={(v) => [`$${fmt(v)}`, "종가"]}
                                      labelFormatter={(l) => String(l)}
                                    />
                                    <Area
                                      type="monotone"
                                      dataKey="close"
                                      stroke="#3b82f6"
                                      strokeWidth={1.5}
                                      fillOpacity={1}
                                      fill={`url(#grad-${stock.symbol})`}
                                      dot={false}
                                    />
                                  </AreaChart>
                                </ResponsiveContainer>
                              </div>

                              {/* OHLC 테이블 */}
                              <div className="h-[280px] overflow-y-auto rounded-xl border border-slate-700/50 custom-scrollbar">
                                <table className="w-full text-xs text-right">
                                  <thead className="bg-slate-800 text-slate-400 sticky top-0">
                                    <tr>
                                      <th className="px-4 py-2 text-left">날짜</th>
                                      <th className="px-4 py-2 text-blue-400">종가</th>
                                      <th className="px-4 py-2">거래량</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-800">
                                    {expandedData.slice().reverse().map((d) => (
                                      <tr key={d.date} className="hover:bg-white/5">
                                        <td className="px-4 py-2 text-left text-slate-300">{d.date}</td>
                                        <td className="px-4 py-2 font-bold text-white">${fmt(d.close)}</td>
                                        <td className="px-4 py-2 text-slate-500">
                                          {d.volume ? Number(d.volume).toLocaleString() : "—"}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          ) : (
                            <div className="text-center text-slate-500 text-sm py-6">
                              차트 데이터를 불러올 수 없습니다.
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>

        {/* 페이지네이션 */}
        <div className="p-4 border-t border-slate-800 flex justify-center items-center gap-3">
          <button
            onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
            disabled={currentPage === 1}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            이전
          </button>
          <span className="text-sm text-slate-400">
            <span className="text-white font-bold">{currentPage}</span> / {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}
            disabled={currentPage === totalPages}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            다음
          </button>
        </div>
      </div>
    </div>
  );
}
