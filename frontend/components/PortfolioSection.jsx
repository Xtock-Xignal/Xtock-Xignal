"use client";

import { useState, useEffect, useCallback } from "react";
import api from "../utils/api";
import { TrendingUp, TrendingDown, Plus, X, Trash2, PieChart as PieIcon } from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend
} from "recharts";

const COLORS = ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444', '#ec4899', '#6366f1', '#14b8a6'];
const INITIAL_CASH = 100000;
const FEE_RATE = 0.0015;
const MAX_HISTORY = 12;
const STORAGE_PREFIX = "xtock-mock-sim";
const BEGINNER_SYMBOLS = [
  { symbol: "AAPL", description: "애플, 대형 성장 + 안정성" },
  { symbol: "MSFT", description: "마이크로소프트, 클라우드/소프트웨어" },
  { symbol: "TSLA", description: "테슬라, 변동성 높은 변화를 직접 체험" },
  { symbol: "NVDA", description: "반도체/AI 테마로 변동성 연습용" },
  { symbol: "AMZN", description: "전자상거래 + AI 연계 성장주" },
  { symbol: "GOOGL", description: "알파벳, 플랫폼 기업 예시" },
];

export default function PortfolioSection({ user }) {
  const [portfolio, setPortfolio] = useState([]);
  const [showTradeModal, setShowTradeModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [priceLoading, setPriceLoading] = useState(false);
  const [cash, setCash] = useState(INITIAL_CASH);
  const [initialCash, setInitialCash] = useState(INITIAL_CASH);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [tradeError, setTradeError] = useState("");

  const [tradeForm, setTradeForm] = useState({
    mode: "buy",
    symbol: "",
    shares: "",
    price: "",
  });

  const getStorageKey = useCallback(() => `${STORAGE_PREFIX}-${user?.email || "guest"}`, [user?.email]);

  const loadSimulationState = useCallback(() => {
    try {
      const raw = localStorage.getItem(getStorageKey());
      if (!raw) return;

      const parsed = JSON.parse(raw);
      if (typeof parsed.cash === "number" && Number.isFinite(parsed.cash)) {
        setCash(parsed.cash);
      }
      if (typeof parsed.initialCash === "number" && parsed.initialCash > 0) {
        setInitialCash(parsed.initialCash);
      }
      if (Array.isArray(parsed.tradeHistory)) {
        setTradeHistory(parsed.tradeHistory);
      }
    } catch {
      // 저장값 파싱 실패 시 무시
    }
  }, [getStorageKey]);

  const fetchLatestPrice = useCallback(async (symbol) => {
    try {
      const res = await api.post("/api/recent-status", { text: symbol });
      const data = res?.data?.stock_data;
      if (Array.isArray(data) && data.length > 0) {
        const last = data[data.length - 1];
        const candidate = Number(last?.close);
        if (Number.isFinite(candidate) && candidate > 0) {
          return candidate;
        }
      }
    } catch {
      // fallback
    }
    return null;
  }, []);

  const enrichPrices = useCallback(async (items) => {
    const updated = await Promise.all(
      items.map(async (item) => {
        const live = await fetchLatestPrice(item.symbol);
        return {
          ...item,
          currentPrice: live && live > 0 ? live : item.currentPrice
        };
      })
    );
    return updated;
  }, [fetchLatestPrice]);

  const fetchPortfolio = useCallback(async () => {
    try {
      const res = await api.post("/api/portfolio/list", { email: user.email });
      if (!res.data.success) {
        return;
      }

      const mappedPortfolio = res.data.portfolio.map((item) => ({
        id: item.symbol,
        symbol: item.symbol,
        name: item.symbol,
        shares: Number(item.quantity),
        avgPrice: Number(item.price),
        currentPrice: Number(item.price),
      }));

      const updatedPortfolio = await enrichPrices(mappedPortfolio);
      setPortfolio(updatedPortfolio);
    } catch (error) {
      console.error(error);
    }
  }, [user?.email, enrichPrices]);

  const syncToServer = async (symbol, nextShares, nextPrice) => {
    if (nextShares <= 0) {
      const res = await api.post("/api/portfolio/remove", {
        email: user.email,
        symbol,
      });
      return res.data;
    }

    const res = await api.post("/api/portfolio/add", {
      email: user.email,
      symbol,
      price: nextPrice,
      quantity: nextShares,
    });

    return res.data;
  };

  const appendTradeHistory = (entry) => {
    setTradeHistory((prev) =>
      [{ id: `${Date.now()}-${Math.random().toString(16).slice(2, 7)}`, ...entry }, ...prev].slice(
        0,
        MAX_HISTORY
      )
    );
  };

  useEffect(() => {
    if (!user?.email) {
      return;
    }

    loadSimulationState();
    fetchPortfolio();
  }, [user?.email, loadSimulationState, fetchPortfolio]);

  useEffect(() => {
    if (!user?.email) {
      return;
    }

    const state = {
      cash,
      initialCash,
      tradeHistory,
    };

    try {
      localStorage.setItem(getStorageKey(), JSON.stringify(state));
    } catch {
      // 브라우저 저장소 접근 불가 시 무시
    }
  }, [cash, initialCash, tradeHistory, getStorageKey, user?.email]);

  const toNumber = (value, fallback = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  const formatMoney = (value) =>
    `$${toNumber(value, 0).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}`;

  const submitTrade = async () => {
    setTradeError("");
    const symbol = tradeForm.symbol.trim().toUpperCase();
    const shares = Math.floor(toNumber(tradeForm.shares, 0));
    const price = toNumber(tradeForm.price, 0);

    if (!symbol || shares <= 0 || price <= 0) {
      setTradeError("티커, 수량, 가격을 모두 올바르게 입력해 주세요.");
      return;
    }

    if (!user?.email) {
      setTradeError("로그인이 필요합니다.");
      return;
    }

    setLoading(true);
    const prevPortfolio = [...portfolio];
    const prevCash = cash;

      try {
        const exists = portfolio.find((stock) => stock.symbol === symbol);
      const tradeValue = shares * price;
      const fee = tradeValue * FEE_RATE;

      let nextPortfolio = [...portfolio];
      let nextCash = cash;
      let nextShares = 0;
      let nextPrice = price;

      if (tradeForm.mode === "buy") {
        if (cash < tradeValue + fee) {
          setTradeError("현재 현금이 부족해요. 모의 계좌에 남은 돈을 확인하세요.");
          setLoading(false);
          return;
        }

        const nextTotalShares = (exists?.shares ?? 0) + shares;
        const weightedAvg = exists
          ? ((exists.avgPrice * exists.shares) + (price * shares)) / nextTotalShares
          : price;
        const idx = nextPortfolio.findIndex((stock) => stock.symbol === symbol);

        if (idx >= 0) {
          nextPortfolio[idx] = {
            ...nextPortfolio[idx],
            shares: nextTotalShares,
            avgPrice: weightedAvg,
            currentPrice: price,
          };
        } else {
          nextPortfolio.push({
            id: symbol,
            symbol,
            name: symbol,
            shares: shares,
            avgPrice: price,
            currentPrice: price,
          });
        }

        nextCash = cash - tradeValue - fee;
        nextShares = nextTotalShares;
        nextPrice = weightedAvg;

        appendTradeHistory({
          mode: "buy",
          symbol,
          shares,
          price,
          amount: tradeValue,
          fee,
          timestamp: new Date().toLocaleString("ko-KR"),
          label: "매수"
        });
      } else {
        if (!exists) {
          setTradeError("선택한 종목을 먼저 보유하고 있지 않습니다. 먼저 매수 주문을 넣어야 매도할 수 있어요.");
          setLoading(false);
          return;
        }
        if (shares > exists.shares) {
          setTradeError(`보유 수량은 ${exists.shares}주입니다. 그보다 많이 매도할 수 없습니다.`);
          setLoading(false);
          return;
        }

        const nextTotalShares = exists.shares - shares;
        const idx = nextPortfolio.findIndex((stock) => stock.symbol === symbol);

        if (idx >= 0) {
          if (nextTotalShares === 0) {
            nextPortfolio.splice(idx, 1);
          } else {
            nextPortfolio[idx] = {
              ...nextPortfolio[idx],
              shares: nextTotalShares,
              currentPrice: price,
            };
          }
        }

        nextCash = cash + (tradeValue - fee);
        nextShares = nextTotalShares;
        nextPrice = exists.avgPrice;

        appendTradeHistory({
          mode: "sell",
          symbol,
          shares,
          price,
          amount: tradeValue,
          fee,
          timestamp: new Date().toLocaleString("ko-KR"),
          label: "매도"
        });
      }

      await syncToServer(symbol, nextShares, nextPrice);

      setPortfolio(nextPortfolio);
      setCash(nextCash);

      setTradeForm({
        mode: tradeForm.mode,
        symbol: "",
        shares: "",
        price: "",
      });
      setShowTradeModal(false);
    } catch (error) {
      console.error(error);
      setPortfolio(prevPortfolio);
      setCash(prevCash);
      setTradeError("주문 동기화 중 오류가 발생했습니다. 잠시 후 다시 시도하세요.");
    } finally {
      setLoading(false);
    }
  };

  const quickSellAll = (symbol) => {
    const target = portfolio.find((stock) => stock.symbol === symbol);
    if (!target) return;

    setTradeForm({
      mode: "sell",
      symbol,
      shares: String(target.shares),
      price: target.currentPrice ? Number(target.currentPrice).toFixed(2) : "",
    });
    setTradeError("");
    setShowTradeModal(true);
  };

  const refreshQuote = async () => {
    if (!tradeForm.symbol) {
      alert("티커를 먼저 입력해주세요.");
      return;
    }
    setPriceLoading(true);
    const quote = await fetchLatestPrice(tradeForm.symbol.toUpperCase());
    if (quote && quote > 0) {
      setTradeForm((prev) => ({ ...prev, price: quote.toFixed(2) }));
    } else {
      alert("현재가 조회 실패. 직접 입력해 주세요.");
    }
    setPriceLoading(false);
  };

  const refreshPortfolioPrices = async () => {
    if (portfolio.length === 0) {
      return;
    }
    const next = await enrichPrices(portfolio);
    setPortfolio(next);
  };

  const resetAccount = () => {
    if (!confirm("데모 계좌와 체결 이력을 초기화할까요?")) {
      return;
    }
    setCash(initialCash);
    setTradeHistory([]);
  };

  const totalValue = portfolio.reduce((sum, stock) => sum + stock.currentPrice * stock.shares, 0);
  const totalCost = portfolio.reduce((sum, stock) => sum + stock.avgPrice * stock.shares, 0);
  const totalReturn = totalValue - totalCost;
  const totalReturnPercent = totalCost > 0 ? (totalReturn / totalCost) * 100 : 0;
  const totalAssets = cash + totalValue;
  const accountReturn = totalAssets - initialCash;
  const accountReturnPct = initialCash > 0 ? (accountReturn / initialCash) * 100 : 0;

  const estimatedSymbol = tradeForm.symbol.trim().toUpperCase();
  const estimatedShares = Math.floor(toNumber(tradeForm.shares, 0));
  const estimatedPrice = toNumber(tradeForm.price, 0);
  const estimatedTradeValue = estimatedShares * estimatedPrice;
  const estimatedFee = estimatedTradeValue * FEE_RATE;
  const estimatedCashAfter = tradeForm.mode === "buy"
    ? cash - estimatedTradeValue - estimatedFee
    : cash + estimatedTradeValue - estimatedFee;
  const selectedHolding = portfolio.find((stock) => stock.symbol === estimatedSymbol);
  const estimatedSellLimitMessage = tradeForm.mode === "sell" && selectedHolding
    ? `${selectedHolding.shares}주까지 매도 가능`
    : "";
  const canSubmitTrade = estimatedShares > 0 && estimatedPrice > 0 && estimatedSymbol.length > 0 && (
    tradeForm.mode === "buy"
      ? estimatedCashAfter >= 0
      : !!selectedHolding && estimatedShares <= selectedHolding.shares
  );

  const fillStarterSymbol = (symbol) => {
    setTradeError("");
    setTradeForm((prev) => ({
      ...prev,
      symbol,
      shares: prev.shares || "1",
      price: prev.price || "",
    }));
    setShowTradeModal(true);
  };

  const pieData = portfolio.map((stock) => ({
    name: stock.symbol,
    value: stock.currentPrice * stock.shares,
  })).sort((a, b) => b.value - a.value);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => {
            setTradeError("");
            setTradeForm({
              mode: "buy",
              symbol: "",
              shares: "",
              price: "",
            });
            setShowTradeModal(true);
          }}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-lg font-semibold transition-colors text-white shadow-lg shadow-blue-900/20"
        >
          <Plus size={20} />
          모의 투자 주문
        </button>
        <div className="flex gap-2 text-sm">
          <button
            onClick={refreshPortfolioPrices}
            className="px-4 py-2 rounded-lg bg-slate-800 text-slate-200 border border-slate-700 hover:bg-slate-700"
          >
            현재가 갱신
          </button>
          <button
            onClick={resetAccount}
            className="px-4 py-2 rounded-lg bg-slate-800 text-slate-400 border border-slate-700 hover:text-white"
          >
            데모 계좌 초기화
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <p className="text-slate-400 text-sm mb-1 font-medium">현재 현금</p>
          <p className="text-white text-2xl font-bold tracking-tight">{formatMoney(cash)}</p>
        </div>
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <p className="text-slate-400 text-sm mb-1 font-medium">보유 자산</p>
          <p className="text-white text-2xl font-bold tracking-tight">{formatMoney(totalValue)}</p>
        </div>
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <p className="text-slate-400 text-sm mb-1 font-medium">총 자산</p>
          <p className="text-white text-2xl font-bold tracking-tight">{formatMoney(totalAssets)}</p>
        </div>
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <p className="text-slate-400 text-sm mb-1 font-medium">총 수익률</p>
          <p className={`text-2xl font-bold tracking-tight ${accountReturn >= 0 ? "text-green-400" : "text-red-400"}`}>
            {accountReturn >= 0 ? "+" : ""}{formatMoney(accountReturn).replace("$", "")} ({accountReturnPct.toFixed(2)}%)
          </p>
        </div>
      </div>

      <div className="bg-slate-800/70 border border-slate-700 rounded-xl p-4 mb-8 text-sm">
        <p className="text-slate-300 font-semibold mb-2">초보자용 모의투자 가이드</p>
        <p className="text-slate-400">
          1) 먼저 종목 티커(예: AAPL), 수량, 가격을 입력하고 <b>매수</b>를 실행하세요.  
        </p>
        <p className="text-slate-400">
          2) 주문 패널에서 예측되는 잔액을 확인한 뒤 수수료가 반영된 실제 처리 금액을 이해합니다.
        </p>
        <p className="text-slate-400">
          3) 보유 종목 카드의 현재가/수익률을 보고 매도 버튼으로 연습해보세요.
        </p>
      </div>

      <div className="bg-slate-800/70 border border-slate-700 rounded-xl p-4 mb-8">
        <p className="text-slate-200 font-semibold mb-3">처음이라면 이런 종목부터 시작해보세요</p>
        <p className="text-slate-400 text-sm mb-3">
          티커를 몰라도 괜찮아요. 아래 버튼을 누르면 주문창이 열리고 바로 종목이 채워집니다.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {BEGINNER_SYMBOLS.map((item) => (
            <button
              key={item.symbol}
              onClick={() => fillStarterSymbol(item.symbol)}
              className="rounded-xl border border-slate-700 bg-slate-900 p-3 text-left hover:bg-slate-900/70 transition-colors"
            >
              <p className="text-white font-bold">{item.symbol}</p>
              <p className="text-slate-400 text-xs mt-1">{item.description}</p>
            </button>
              ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="flex flex-col h-full">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
            📋 보유 종목 현황
          </h3>
          {portfolio.length === 0 ? (
            <div className="bg-slate-800/50 rounded-xl p-10 text-center border border-slate-700 border-dashed">
              <p className="text-slate-400">아직 보유 종목이 없습니다.</p>
              <p className="text-slate-500 text-sm mt-2">모의 주문으로 먼저 종목을 매수해보세요.</p>
            </div>
          ) : (
            <div className="space-y-3 flex-1 overflow-y-auto max-h-[400px] custom-scrollbar pr-2">
              {portfolio.map((stock) => {
                const returnVal = (stock.currentPrice - stock.avgPrice) * stock.shares;
                const returnPct = ((stock.currentPrice - stock.avgPrice) / stock.avgPrice) * 100;

                return (
                  <div
                    key={stock.id}
                    className="bg-slate-800 rounded-xl p-5 border border-slate-700/50 hover:border-slate-600 transition-all"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center text-white font-bold">
                          {stock.symbol[0]}
                        </div>
                        <div>
                          <h4 className="text-white font-bold">{stock.symbol}</h4>
                          <p className="text-slate-400 text-xs">{stock.shares}주 보유 · 평균가 {formatMoney(stock.avgPrice)}</p>
                        </div>
                      </div>
                      <button
                        onClick={() => quickSellAll(stock.symbol)}
                        className="text-slate-500 hover:text-red-400 hover:bg-red-400/10 p-2 rounded-lg transition-colors"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>

                    <div className="flex items-end justify-between pt-2 border-t border-slate-700/50">
                      <div>
                        <p className="text-slate-400 text-xs mb-0.5">평가금액</p>
                        <p className="text-white font-bold">{formatMoney(stock.currentPrice * stock.shares)}</p>
                        <p className="text-slate-500 text-xs">현재가 {formatMoney(stock.currentPrice)}</p>
                      </div>
                      <div className="text-right">
                        <div className={`flex items-center justify-end gap-1 ${returnPct >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {returnPct >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                          <span className="font-bold text-sm">{returnPct >= 0 ? "+" : ""}{returnPct.toFixed(2)}%</span>
                        </div>
                        <p className={`text-xs ${returnVal >= 0 ? "text-green-500/70" : "text-red-500/70"}`}>
                          {returnVal >= 0 ? "+" : ""}{formatMoney(returnVal)}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex flex-col h-full">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
            <PieIcon className="text-purple-500" size={20} />
            자산 구성
          </h3>
          <div className="bg-slate-800 rounded-2xl p-6 border border-slate-700 relative min-h-[260px]">
            {portfolio.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={70}
                    outerRadius={105}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} stroke="rgba(0,0,0,0.2)" />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
                    contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc", borderRadius: "12px" }}
                    itemStyle={{ color: "#fff" }}
                  />
                  <Legend
                    verticalAlign="bottom"
                    height={36}
                    iconType="circle"
                    formatter={(value) => <span className="text-slate-300 ml-1">{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-center text-slate-500 py-6">
                <PieIcon size={48} className="mx-auto mb-4 opacity-20" />
                <p>데이터가 없습니다.</p>
                <p className="text-sm">보유 종목이 있어야 차트가 표시됩니다.</p>
              </div>
            )}
            <div className="mt-4 pt-4 border-t border-slate-700">
              <p className="text-slate-400 text-xs mb-2">보유 종목 총 수익금</p>
              <p className={`text-xl font-bold ${totalReturn >= 0 ? "text-green-400" : "text-red-400"}`}>
                {totalReturn >= 0 ? "+" : ""}{formatMoney(totalReturn)} ({totalReturnPercent.toFixed(2)}%)
              </p>
            </div>
          </div>

          <div className="mt-4 bg-slate-800 rounded-xl border border-slate-700 p-4">
            <h4 className="text-white font-bold mb-3">체결 이력</h4>
            {tradeHistory.length === 0 ? (
              <p className="text-slate-500 text-sm">아직 주문 이력이 없습니다.</p>
            ) : (
              <div className="space-y-2 max-h-[220px] overflow-y-auto custom-scrollbar">
                {tradeHistory.map((history) => (
                  <div key={history.id} className="bg-slate-900/60 rounded-lg p-3 border border-slate-700/80 text-sm">
                    <div className="flex items-center justify-between">
                      <p className="font-bold text-white">{history.label} {history.symbol}</p>
                      <p className={`font-bold ${history.mode === "buy" ? "text-red-400" : "text-emerald-400"}`}>
                        {history.mode === "buy" ? "-" : "+"}{formatMoney(history.amount)}
                      </p>
                    </div>
                    <p className="text-slate-400 mt-1">
                      {history.shares}주 · 단가 {formatMoney(history.price)} · 수수료 {formatMoney(history.fee)} · {history.timestamp}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {showTradeModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
          <div className="bg-slate-900 rounded-2xl p-8 w-full max-w-md border border-slate-700 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-bold text-white">모의 투자 주문</h3>
              <button
                onClick={() => {
                  setTradeError("");
                  setShowTradeModal(false);
                }}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <X size={24} />
              </button>
            </div>

            <div className="mb-5">
              <label className="block text-slate-400 text-xs font-bold mb-2 uppercase tracking-wider">주문 유형</label>
              <select
                value={tradeForm.mode}
                onChange={(e) => {
                  setTradeError("");
                  setTradeForm({ ...tradeForm, mode: e.target.value });
                }}
                className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="buy">매수</option>
                <option value="sell">매도</option>
              </select>
            </div>

            <div className="space-y-5">
              <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-3">
                <p className="text-xs text-slate-300 mb-2">빠른 시작 종목</p>
                <div className="flex flex-wrap gap-2">
                  {BEGINNER_SYMBOLS.slice(0, 4).map((item) => (
                    <button
                      key={`modal-${item.symbol}`}
                      type="button"
                      onClick={() => fillStarterSymbol(item.symbol)}
                      className="text-xs rounded-full border border-slate-700 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200"
                    >
                      {item.symbol}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-slate-400 text-xs font-bold mb-2 uppercase tracking-wider">
                  종목 티커
                </label>
                <input
                  type="text"
                  value={tradeForm.symbol}
                  onChange={(e) => {
                    setTradeError("");
                    setTradeForm({ ...tradeForm, symbol: e.target.value.toUpperCase() });
                  }}
                  placeholder="예: AAPL, TSLA"
                  className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all uppercase"
                />
              </div>

              <div>
                <label className="block text-slate-400 text-xs font-bold mb-2 uppercase tracking-wider">
                  수량
                </label>
                <input
                  type="number"
                  value={tradeForm.shares}
                  onChange={(e) => {
                    setTradeError("");
                    setTradeForm({ ...tradeForm, shares: e.target.value });
                  }}
                  placeholder="0"
                  className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              <div>
                <label className="block text-slate-400 text-xs font-bold mb-2 uppercase tracking-wider">
                  체결 가격 (단가)
                </label>
                <div className="relative">
                  <span className="absolute left-4 top-3 text-slate-500">$</span>
                  <input
                    type="number"
                    step="0.01"
                    value={tradeForm.price}
                    onChange={(e) => {
                      setTradeError("");
                      setTradeForm({ ...tradeForm, price: e.target.value });
                    }}
                    placeholder="0.00"
                    className="w-full bg-slate-800 text-white rounded-xl pl-8 pr-4 py-3 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                  />
                  <button
                    type="button"
                    onClick={refreshQuote}
                    disabled={priceLoading}
                    className="absolute right-2 top-2 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs disabled:opacity-50"
                  >
                    {priceLoading ? "조회중" : "현재가"}
                  </button>
                </div>
              </div>

              {estimatedShares > 0 && estimatedPrice > 0 && (
                <div className="bg-slate-800/70 border border-slate-700 rounded-xl p-4 text-sm">
                  <p className="text-slate-300 mb-1">
                    예상 거래금액: <span className="text-white font-semibold">{formatMoney(estimatedTradeValue)}</span>
                  </p>
                  <p className="text-slate-400 mb-1">
                    수수료({(FEE_RATE * 100).toFixed(2)}%): <span className="text-white">{formatMoney(estimatedFee)}</span>
                  </p>
                  <p className={`font-semibold ${estimatedCashAfter >= 0 ? "text-emerald-300" : "text-red-300"}`}>
                    주문 후 예상 현금: {formatMoney(estimatedCashAfter)}
                  </p>
                  {estimatedSellLimitMessage && (
                    <p className="text-slate-400 text-xs mt-1">
                      매도 가능 수량: {estimatedSellLimitMessage}
                    </p>
                  )}
                  {!selectedHolding && tradeForm.mode === "sell" && estimatedSymbol && (
                    <p className="text-red-300 text-xs mt-1">
                      보유하지 않은 종목입니다.
                    </p>
                  )}
                </div>
              )}

              <button
                onClick={submitTrade}
                disabled={loading || !canSubmitTrade}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3.5 rounded-xl transition-all shadow-lg shadow-blue-900/20 disabled:opacity-50 mt-2"
              >
                {loading ? "주문 처리 중..." : `${tradeForm.mode === "buy" ? "매수" : "매도"} 주문`}
              </button>
            </div>

            {tradeError && (
              <p className="mt-3 text-sm text-red-300 bg-red-900/30 border border-red-800/80 rounded-lg px-3 py-2">
                {tradeError}
              </p>
            )}

            <p className="mt-4 text-xs text-slate-400">
              수수료 {FEE_RATE * 100}%가 자동 반영됩니다.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
