"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import api from "../utils/api";
import { useValuationPrices } from "../hooks/useValuationPrices";
import { computeSimulationMetrics } from "../utils/simulationPortfolio";

const formatMoney = (n) => {
  const num = Number(n);
  if (Number.isNaN(num)) return "$0.00";
  return `$${num.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};

export default function PortfolioSection({ user = null, isActive = true }) {
  const [loading, setLoading] = useState(false);
  const [cash, setCash] = useState(0);
  const [holdings, setHoldings] = useState({});
  const [trades, setTrades] = useState([]);
  const [simulationStarted, setSimulationStarted] = useState(false);

  const email = user?.email?.trim();

  const loadSimulationState = useCallback(async () => {
    if (!email) {
      setCash(0);
      setHoldings({});
      setTrades([]);
      setSimulationStarted(false);
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("/api/simulation/state/get", { email });
      const state = res?.data?.state;

      if (res?.data?.success && res?.data?.exists && state) {
        setCash(Number(state.cash) || 0);
        setHoldings(state.holdings || {});
        setTrades(Array.isArray(state.trades) ? state.trades : []);
        setSimulationStarted(Boolean(state.simulation_started));
      } else {
        setCash(0);
        setHoldings({});
        setTrades([]);
        setSimulationStarted(false);
      }
    } catch (e) {
      console.error("Failed to load portfolio simulation state", e);
      setCash(0);
      setHoldings({});
      setTrades([]);
      setSimulationStarted(false);
    } finally {
      setLoading(false);
    }
  }, [email]);

  useEffect(() => {
    if (!isActive) return;
    void loadSimulationState();
  }, [loadSimulationState, isActive]);

  const { holdingList, getValuationPrice } = useValuationPrices(
    holdings,
    Boolean(email && simulationStarted && isActive)
  );

  const { totalValue, totalPnl } = useMemo(
    () => computeSimulationMetrics(cash, holdings, getValuationPrice),
    [cash, holdings, getValuationPrice]
  );

  if (!email) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8">
        <p className="text-slate-400 text-sm">로그인 후 시뮬레이션 포트폴리오를 확인할 수 있습니다.</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 space-y-6">
      {loading ? (
        <p className="text-slate-400 text-sm">포트폴리오를 불러오는 중…</p>
      ) : !simulationStarted ? (
        <p className="text-slate-400 text-sm">
          아직 시작한 시뮬레이션이 없습니다. 주식 시뮬레이션 메뉴에서 계좌를 시작해 보세요.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
              <div className="text-slate-400 text-xs mb-1">가상 현금</div>
              <div className="text-white text-xl font-bold">{formatMoney(cash)}</div>
            </div>
            <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
              <div className="text-slate-400 text-xs mb-1">계좌 총액</div>
              <div className="text-white text-xl font-bold">{formatMoney(totalValue)}</div>
            </div>
            <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
              <div className="text-slate-400 text-xs mb-1">총 손익</div>
              <div
                className={`text-xl font-bold flex items-center gap-1 ${
                  totalPnl >= 0 ? "text-green-400" : "text-red-400"
                }`}
              >
                {totalPnl >= 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                {totalPnl >= 0 ? "+" : "-"}
                {formatMoney(Math.abs(totalPnl))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-slate-800/30 border border-slate-700 rounded-2xl p-4 flex flex-col min-h-[280px]">
              <div className="flex items-center justify-between mb-3">
                <div className="text-white font-semibold">보유 종목</div>
                <div className="text-slate-500 text-xs">
                  {holdingList.length ? `${holdingList.length}개` : ""}
                </div>
              </div>
              {holdingList.length === 0 ? (
                <div className="text-slate-500 text-sm bg-slate-900/30 border border-slate-700 rounded-xl p-4 flex-1 flex items-center justify-center">
                  아직 보유한 종목이 없습니다.
                </div>
              ) : (
                <div
                  className="space-y-3 overflow-y-auto custom-scrollbar pr-1 flex-1"
                  style={{ maxHeight: 320 }}
                >
                  {holdingList.map(([sym, h]) => {
                    const px = getValuationPrice(sym);
                    const shares = Number(h.shares) || 0;
                    const avg = Number(h.avgCost) || 0;
                    const pnl = (px - avg) * shares;
                    return (
                      <div
                        key={sym}
                        className="bg-slate-900/40 border border-slate-700 rounded-xl p-3"
                      >
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

            <div className="bg-slate-800/30 border border-slate-700 rounded-2xl p-4 flex flex-col min-h-[280px]">
              <div className="flex items-center justify-between mb-3">
                <div className="text-white font-semibold">거래 내역</div>
                <div className="text-slate-500 text-xs">
                  {trades.length ? `${trades.length}건` : ""}
                </div>
              </div>
              {trades.length === 0 ? (
                <div className="text-slate-500 text-sm bg-slate-900/30 border border-slate-700 rounded-xl p-4 flex-1 flex items-center justify-center">
                  거래 내역이 없습니다.
                </div>
              ) : (
                <div
                  className="overflow-y-auto custom-scrollbar pr-1 flex-1"
                  style={{ maxHeight: 320 }}
                >
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
                            <td className="py-2 px-1 text-right text-slate-200">
                              {formatMoney(t.price)}
                            </td>
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
        </>
      )}
    </div>
  );
}