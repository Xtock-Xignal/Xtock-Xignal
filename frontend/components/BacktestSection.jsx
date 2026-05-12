"use client";

import React from "react";
import { useEffect, useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend
} from "recharts";
import { CircleHelp } from "lucide-react";
import api from "../utils/api";

const QUICK_SYMBOLS = ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN", "GOOGL", "JPM", "XOM", "JNJ", "BND", "SPY", "TLT", "GLD", "BRK.B"];
const INITIAL_CASH_PRESETS = [50000, 100000, 300000, 1000000];
const BACKTEST_PHASES = [
  "선택한 기간의 가격 데이터를 불러오는 중...",
  "단기/장기 이동평균 값을 계산하는 중...",
  "매수/매도 신호를 만들어 거래를 모의 실행하는 중...",
  "거래 결과를 취합해 수익률을 계산 중..."
];
const BACKTEST_PRESETS = [
  {
    id: "all-weather",
    name: "올웨더",
    description: "시장 환경 변화에 대응하기 위한 분산형 조합",
    positions: [
      { symbol: "SPY", weight: 0.4 },
      { symbol: "TLT", weight: 0.3 },
      { symbol: "GLD", weight: 0.2 },
      { symbol: "BND", weight: 0.1 },
    ],
  },
  {
    id: "balanced-growth",
    name: "성장형",
    description: "기술주 비중을 높여 성장 성향에 맞춘 조합",
    positions: [
      { symbol: "AAPL", weight: 0.35 },
      { symbol: "MSFT", weight: 0.3 },
      { symbol: "NVDA", weight: 0.25 },
      { symbol: "TSLA", weight: 0.1 },
    ],
  },
  {
    id: "conservative",
    name: "보수형",
    description: "변동성 줄이기를 우선한 안정형 조합",
    positions: [
      { symbol: "BND", weight: 0.5 },
      { symbol: "AAPL", weight: 0.2 },
      { symbol: "JNJ", weight: 0.15 },
      { symbol: "MSFT", weight: 0.15 },
    ],
  },
];

const DEFAULT_BASKET_ROW = { symbol: "", weight: "" };

const DEFAULT_FORM = {
  symbol: "AAPL",
  startDate: "",
  endDate: "",
  initialCash: "100000",
  shortWindow: "5",
  longWindow: "20",
  feeRate: "0.0015",
  presetId: "",
  mode: "single",
};

export default function BacktestSection() {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [symbolCatalog, setSymbolCatalog] = useState([]);
  const [symbolQuery, setSymbolQuery] = useState("");
  const [basketRows, setBasketRows] = useState([DEFAULT_BASKET_ROW]);
  const [hoveredSymbol, setHoveredSymbol] = useState("");
  const [selectedInfoSymbol, setSelectedInfoSymbol] = useState("");
  const [symbolInfoCache, setSymbolInfoCache] = useState({});
  const [loadingSymbolInfo, setLoadingSymbolInfo] = useState("");

  const selectedPreset = useMemo(() => {
    return form.mode === "template"
      ? BACKTEST_PRESETS.find((item) => item.id === form.presetId) || null
      : null;
  }, [form.mode, form.presetId]);

  const toNumber = (value, fallback = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  const parseWeight = (value) => {
    const trimmed = String(value).trim();
    if (!trimmed) return null;

    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed) || parsed < 0) {
      return "invalid";
    }

    return parsed;
  };

  const normalizeBasketRows = () => {
    const symbols = new Set();
    const rows = [];
    for (const row of basketRows) {
      const symbol = row.symbol.trim().toUpperCase();
      if (!symbol) {
        continue;
      }

      if (symbols.has(symbol)) {
        return {
          success: false,
          msg: `중복 종목입니다: ${symbol}`,
        };
      }
      symbols.add(symbol);

      const weight = parseWeight(row.weight);
      if (weight === "invalid") {
        return {
          success: false,
          msg: `${symbol} 비중을 0 이상의 숫자로 입력해 주세요.`,
        };
      }
      if (weight > 100) {
        return {
          success: false,
          msg: `${symbol} 비중은 100 이하의 숫자(또는 0~1 범위)를 입력해 주세요.`,
        };
      }

      rows.push({
        symbol,
        weight: weight === null ? null : weight,
      });
    }

    if (rows.length === 0) {
      return {
        success: false,
        msg: "장바구니에 1개 이상 종목을 넣어 주세요.",
      };
    }

    return {
      success: true,
      rows,
    };
  };

  const basketAllocationPreview = useMemo(() => {
    const normalized = normalizeBasketRows();
    if (!normalized.success) {
      return [];
    }

    let manualTotal = 0;
    let autoCount = 0;
    const parsed = normalized.rows.map((row) => {
      let weight = row.weight;
      if (weight !== null && weight > 1) {
        weight = weight / 100;
      }
      return {
        symbol: row.symbol,
        weight,
        rawWeight: weight,
      };
    });

    for (const row of parsed) {
      if (row.weight == null) {
        autoCount += 1;
      } else {
        manualTotal += row.weight;
      }
    }

    if (manualTotal > 1.000001) {
      return [];
    }

    const normalizedRows = parsed.map((row) => {
      if (row.weight == null) {
        return {
          ...row,
          allocatedWeight:
            autoCount > 0 ? (1 - manualTotal) / autoCount : 0,
        };
      }

      if (manualTotal === 0) {
        return { ...row, allocatedWeight: 0 };
      }

      return { ...row, allocatedWeight: row.weight / manualTotal };
    });

    const totalNormalized = normalizedRows.reduce(
      (acc, item) => acc + item.allocatedWeight,
      0
    );
    if (Math.abs(totalNormalized - 1) > 0.0001 && manualTotal > 0) {
      return [];
    }

    const initialCash = toNumber(form.initialCash, 0);
    return normalizedRows.map((item) => ({
      ...item,
      allocatedCash: item.allocatedWeight * initialCash,
    }));
  }, [basketRows, form.initialCash, toNumber]);

  const initialCashValue = useMemo(() => toNumber(form.initialCash, 0), [form.initialCash, toNumber]);
  const presetBasketPreview = useMemo(() => {
    if (!selectedPreset || initialCashValue <= 0) {
      return [];
    }

    return selectedPreset.positions.map((item) => ({
      ...item,
      allocatedCash: initialCashValue * item.weight,
    }));
  }, [selectedPreset, initialCashValue]);

  const formatMoney = (value) => {
    const parsed = toNumber(value, 0);
    return `$${parsed.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  const formatWeight = (weight, withSign = false) => {
    const pct = toNumber(weight, 0) * 100;
    return `${withSign ? (pct >= 0 ? "+" : "") : ""}${pct.toFixed(1)}%`;
  };

  const formatMarketCap = (value) => {
    if (!value || value <= 0) {
      return "-";
    }

    return `$${Number(value).toLocaleString(undefined, {
      maximumFractionDigits: 0,
    })}`;
  };

  const formatEmployees = (value) => {
    if (!value || value <= 0) {
      return "-";
    }

    return `${Number(value).toLocaleString()}명`;
  };

  const setPreset = (presetId) => {
    setError("");
    setResult(null);
    const active = form.presetId === presetId ? "" : presetId;

    setForm((prev) => ({
      ...prev,
      presetId: active,
      symbol: "",
      mode: active ? "template" : "single",
    }));
  };

  const setSymbol = (symbol) => {
    setError("");
    setResult(null);
    setForm((prev) => ({
      ...prev,
      presetId: "",
      symbol,
      mode: "single",
    }));
  };

  const applyMode = (mode) => {
    if (mode === "basket") {
      setBasketRows((prev) =>
        prev.length > 0 ? prev : [DEFAULT_BASKET_ROW]
      );
    }

    if (mode !== "template") {
      setForm((prev) => ({
        ...prev,
        mode,
        presetId: "",
      }));
    } else {
      setForm((prev) => ({
        ...prev,
        mode,
      }));
    }

    setError("");
    setResult(null);
  };

  const upsertBasketRow = (index, patch) => {
    setError("");
    setResult(null);
    setForm((prev) => ({
      ...prev,
      mode: "basket",
      presetId: "",
    }));
    setBasketRows((prev) =>
      prev.map((row, idx) =>
        idx === index ? { ...row, ...patch } : row
      )
    );
  };

  const addBasketRow = () => {
    setBasketRows((prev) => [...prev, { symbol: "", weight: "" }]);
  };

  const removeBasketRow = (index) => {
    setError("");
    setResult(null);
    setBasketRows((prev) => {
      if (prev.length <= 1) {
        return [DEFAULT_BASKET_ROW];
      }
      return prev.filter((_, idx) => idx !== index);
    });
  };

  const fillBasketSymbol = (symbol) => {
    const normalized = symbol.trim().toUpperCase();
    if (!normalized) {
      return;
    }

    setBasketRows((prev) => {
      const exists = prev.some((row) => row.symbol.trim().toUpperCase() === normalized);
      if (exists) {
        setError(`${normalized}는 이미 장바구니에 있습니다.`);
        return prev;
      }

      const emptyRowIndex = prev.findIndex((row) => !row.symbol.trim());
      if (emptyRowIndex >= 0) {
        const next = [...prev];
        next[emptyRowIndex] = {
          ...next[emptyRowIndex],
          symbol: normalized,
        };
        return next;
      }

      return [...prev, { symbol: normalized, weight: "" }];
    });

    applyMode("basket");
  };

  useEffect(() => {
    const fetchSymbolCatalog = async () => {
      try {
        const res = await api.get("/api/backtest/symbols", {
          params: {
            limit: 300,
          },
        });

        const symbols = Array.isArray(res.data?.items) ? res.data.items : [];
        if (symbols.length > 0) {
          setSymbolCatalog(
            symbols.map((item) => ({
              symbol: item.symbol || "",
              name: item.name || item.symbol || "",
            }))
          );
          return;
        }
      } catch (err) {
        console.error("백테스트 종목 목록 조회 실패", err);
      }

      setSymbolCatalog(
        QUICK_SYMBOLS.map((symbol) => ({
          symbol,
          name: symbol,
        }))
      );
    };

    fetchSymbolCatalog();
  }, []);

  const filteredSymbolCatalog = useMemo(() => {
    const query = symbolQuery.trim().toUpperCase();
    if (!query) {
      return symbolCatalog;
    }
    return symbolCatalog.filter((item) => {
      if (!item?.symbol) return false;
      const inSymbol = item.symbol.includes(query);
      const inName = (item.name || "").toUpperCase().includes(query);
      return inSymbol || inName;
    });
  }, [symbolCatalog, symbolQuery]);

  const hoveredSymbolMeta = useMemo(() => {
    if (!hoveredSymbol) {
      return null;
    }

    return symbolCatalog.find((item) => item.symbol === hoveredSymbol) || null;
  }, [hoveredSymbol, symbolCatalog]);

  const symbolInfoMeta = useMemo(() => {
    const target = selectedInfoSymbol || hoveredSymbol;
    if (!target) {
      return null;
    }

    if (symbolInfoCache[target]) {
      return symbolInfoCache[target];
    }

    return hoveredSymbolMeta || {
      symbol: target,
      name: target,
    };
  }, [selectedInfoSymbol, hoveredSymbol, symbolInfoCache, hoveredSymbolMeta]);

  const loadSymbolInfo = async (symbol) => {
    if (!symbol) {
      return;
    }

    const normalized = symbol.trim().toUpperCase();
    if (symbolInfoCache[normalized]?.cached) {
      return;
    }

    setLoadingSymbolInfo(normalized);
    try {
      const res = await api.get("/api/backtest/symbol-info", {
        params: { symbol: normalized },
      });

      if (res.data?.success && res.data?.item) {
        setSymbolInfoCache((prev) => ({
          ...prev,
          [normalized]: {
            ...res.data.item,
            cached: true,
          },
        }));
      }
    } catch (err) {
      console.error("종목 상세 조회 실패", err);
      setSymbolInfoCache((prev) => ({
        ...prev,
        [normalized]: {
          symbol: normalized,
          name: normalized,
          cached: true,
        },
      }));
    } finally {
      setLoadingSymbolInfo("");
    }
  };

  const openSymbolInfo = async (symbol) => {
    if (!symbol) {
      return;
    }

    const normalized = symbol.trim().toUpperCase();
    const nextSelected = selectedInfoSymbol === normalized ? "" : normalized;
    setSelectedInfoSymbol(nextSelected);
    if (nextSelected) {
      await loadSymbolInfo(nextSelected);
    }
  };

  const closeSymbolInfo = () => {
    setSelectedInfoSymbol("");
  };

  const symbolInfoButton = (symbol) => (
    <span
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        openSymbolInfo(symbol);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          openSymbolInfo(symbol);
        }
      }}
      className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-500/60 text-slate-300 hover:border-sky-400 hover:text-sky-300 cursor-pointer"
      aria-label={`종목 정보 보기 ${symbol}`}
      title={`${symbol} 정보 보기`}
    >
      <CircleHelp size={12} />
    </span>
  );

  const run = async () => {
    setError("");
    setResult(null);

    const symbol = form.symbol.trim().toUpperCase();
    const shortWindow = Math.floor(toNumber(form.shortWindow, 0));
    const longWindow = Math.floor(toNumber(form.longWindow, 0));
    const initialCash = toNumber(form.initialCash, 0);
    const feeRate = toNumber(form.feeRate, 0);

    const isTemplateMode = form.mode === "template" && Boolean(selectedPreset);

    if (form.mode === "basket") {
      const normalizedBasket = normalizeBasketRows();
      if (!normalizedBasket.success) {
        setError(normalizedBasket.msg);
        return;
      }

      if (toNumber(form.initialCash, 0) <= 0) {
        setError("초기 자금은 0보다 커야 합니다.");
        return;
      }
    } else if (!isTemplateMode && !symbol) {
      setError("티커를 입력해 주세요.");
      return;
    }

    if (initialCash <= 0) {
      setError("초기 자금은 0보다 커야 합니다.");
      return;
    }

    if (shortWindow < 2 || longWindow <= shortWindow) {
      setError("shortWindow는 2 이상, longWindow는 shortWindow보다 커야 합니다.");
      return;
    }

    if (form.startDate && form.endDate && form.startDate > form.endDate) {
      setError("시작일은 종료일보다 이전이어야 합니다.");
      return;
    }

    setLoading(true);
    setLoadingStep(0);

    const progressTimer = setInterval(() => {
      setLoadingStep((prev) => {
        if (prev >= BACKTEST_PHASES.length - 1) {
          return prev;
        }
        return prev + 1;
      });
    }, 900);

    try {
      const payload = {
        strategy: "ma_cross",
        start_date: form.startDate || null,
        end_date: form.endDate || null,
        initial_cash: initialCash,
        short_window: shortWindow,
        long_window: longWindow,
        fee_rate: feeRate,
      };

      if (selectedPreset) {
        payload.positions = selectedPreset.positions;
      } else if (form.mode === "basket") {
        const normalizedBasket = normalizeBasketRows();
        payload.positions = normalizedBasket.rows;
      } else {
        payload.symbol = symbol;
      }

      const res = await api.post("/api/backtest/run", payload);
      if (!res.data?.success) {
        setError(res.data?.msg || "백테스트 실행에 실패했습니다.");
        setLoading(false);
        clearInterval(progressTimer);
        return;
      }

      setResult(res.data);
    } catch (err) {
      console.error(err);
      setError("백엔드 연결 실패 또는 응답 형식 오류입니다.");
    } finally {
      setLoading(false);
      clearInterval(progressTimer);
      setLoadingStep(0);
    }
  };

  const equityChartData = useMemo(() => {
    if (!result?.equity_curve) {
      return [];
    }

    return result.equity_curve.map((point) => ({
      date: point.date,
      자산: point.equity,
    }));
  }, [result]);

  return (
    <section className="space-y-6">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <p className="text-white text-xl font-bold mb-1">백테스팅 실습</p>
        <p className="text-slate-400 text-sm">
          과거 가격 데이터로 전략(현재는 단기/장기 이동평균 교차) 성능을 미리 검증해봅니다.
        </p>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5">
        <h3 className="text-white text-lg font-bold">입력</h3>

        <div>
          <p className="text-xs text-slate-400 mb-3 uppercase">입력 방식 선택</p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3 mb-4">
            <button
              type="button"
              onClick={() => applyMode("single")}
              className={`rounded-xl border p-4 text-left transition ${
                form.mode === "single"
                  ? "border-sky-400 bg-sky-900/40"
                  : "border-slate-700 bg-slate-800 hover:bg-slate-700"
              }`}
            >
              <p className="text-sm font-semibold text-white">단일 종목</p>
              <p className="text-xs text-slate-300 mt-1">
                하나의 종목으로 MA 전략을 테스트합니다.
              </p>
            </button>
            <button
              type="button"
              onClick={() => applyMode("basket")}
              className={`rounded-xl border p-4 text-left transition ${
                form.mode === "basket"
                  ? "border-sky-400 bg-sky-900/40"
                  : "border-slate-700 bg-slate-800 hover:bg-slate-700"
              }`}
            >
              <p className="text-sm font-semibold text-white">장바구니</p>
              <p className="text-xs text-slate-300 mt-1">
                여러 종목을 넣고 비중을 조절해 포트폴리오를 구성합니다.
              </p>
            </button>
            <button
              type="button"
              onClick={() => applyMode("template")}
              className={`rounded-xl border p-4 text-left transition ${
                form.mode === "template"
                  ? "border-sky-400 bg-sky-900/40"
                  : "border-slate-700 bg-slate-800 hover:bg-slate-700"
              }`}
            >
              <p className="text-sm font-semibold text-white">템플릿</p>
              <p className="text-xs text-slate-300 mt-1">
                추천 조합으로 바로 실습할 수 있습니다.
              </p>
            </button>
          </div>

          <p className="text-xs text-slate-400 mb-3 uppercase">초보자용 포트폴리오 템플릿</p>
          <div className="grid gap-3 md:grid-cols-3">
            {BACKTEST_PRESETS.map((preset) => {
              const active = selectedPreset?.id === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => setPreset(active ? "" : preset.id)}
                  className={`text-left rounded-xl border p-4 transition ${
                    active
                      ? "border-sky-400 bg-sky-900/40"
                      : "border-slate-700 bg-slate-800 hover:bg-slate-700"
                  }`}
                >
                  <p className="text-sm font-semibold text-white">{preset.name}</p>
                  <p className="text-xs text-slate-300 mt-1">{preset.description}</p>
                  <p className="text-xs text-slate-400 mt-2">
                    {preset.positions.map((pos) => (
                      <span
                        key={`${preset.id}-${pos.symbol}`}
                        className="inline-flex items-center gap-1.5 mr-2"
                      >
                        <span>
                          {pos.symbol}
                          {" "}
                          {formatWeight(pos.weight)}
                        </span>
                        {symbolInfoButton(pos.symbol)}
                      </span>
                    ))}
                  </p>
                </button>
              );
            })}
          </div>
          {selectedPreset && (
            <p className="text-xs text-emerald-300 mt-2">
              선택됨: {selectedPreset.name} 비율로 각 종목에 자금을 배분해 백테스트합니다.
            </p>
          )}
        </div>

        {selectedPreset && presetBasketPreview.length > 0 && (
          <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-4">
            <p className="text-white text-sm font-semibold">템플릿 장바구니(예상)</p>
            <p className="text-slate-400 text-xs mt-1">
              초기 자금 {formatMoney(initialCashValue)} 기준으로 백테스트 전에 자동 배분되는 금액입니다.
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {presetBasketPreview.map((item) => (
                <div
                  key={item.symbol}
                  className="rounded-lg border border-slate-700/80 px-3 py-2 bg-slate-900/60 flex items-center justify-between"
                >
                  <span className="text-slate-200 flex items-center gap-1.5">
                    {item.symbol}
                    {symbolInfoButton(item.symbol)}
                  </span>
                  <span className="text-white font-semibold">
                    {formatWeight(item.weight)} · {formatMoney(item.allocatedCash)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="text-xs text-slate-400 mt-1">
          빠른 입력은 예시용입니다. 원하면 직접 입력창에 임의 티커를 넣어도 됩니다.
        </p>
        <div>
          <label className="block text-xs text-slate-400 mb-2 uppercase">종목 빠른 선택 (백엔드 목록 연동)</label>
          <input
            type="text"
            value={symbolQuery}
            onChange={(e) => setSymbolQuery(e.target.value.toUpperCase())}
            placeholder="예: AAPL, MSFT, SPY"
            className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700 mb-2"
          />
          <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto pr-1 pb-1">
            {filteredSymbolCatalog.slice(0, 120).map((item) => (
              <div key={item.symbol} className="inline-flex items-center gap-1">
                <button
                  type="button"
                  onMouseEnter={() => setHoveredSymbol(item.symbol)}
                  onMouseLeave={() => setHoveredSymbol("")}
                  onClick={() => {
                    if (form.mode === "basket") {
                      fillBasketSymbol(item.symbol);
                      return;
                    }
                    setSymbol(item.symbol);
                  }}
                  className="text-xs rounded-full border border-slate-700 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200"
                  title={`${item.symbol} · ${item.name || "종목 정보를 불러오지 못했습니다"}`}
                >
                  {item.symbol}
                </button>
                {symbolInfoButton(item.symbol)}
              </div>
            ))}
            {filteredSymbolCatalog.length === 0 && (
              <p className="text-slate-500 text-sm">검색한 종목이 없습니다.</p>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            총 {filteredSymbolCatalog.length}개 종목 (최대 120개만 화면 표시)
          </p>
        </div>

        {symbolInfoMeta && (
          <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-3 mt-2 text-xs text-slate-200">
            <p className="text-slate-400">선택 종목 정보</p>
            <p className="mt-1">
              <span className="font-semibold text-white">{symbolInfoMeta.symbol}</span>
              {symbolInfoMeta.name && symbolInfoMeta.name !== symbolInfoMeta.symbol && (
                <span className="text-slate-300"> · {symbolInfoMeta.name}</span>
              )}
            </p>
            {symbolInfoMeta.exchange && symbolInfoMeta.country && (
              <p className="text-slate-300 mt-1">
                {symbolInfoMeta.exchange} · {symbolInfoMeta.country}
              </p>
            )}
            {(symbolInfoMeta.sector || symbolInfoMeta.industry) && (
              <p className="text-slate-300 mt-1">
                {symbolInfoMeta.sector}
                {symbolInfoMeta.sector && symbolInfoMeta.industry ? " · " : ""}
                {symbolInfoMeta.industry}
              </p>
            )}
            {symbolInfoMeta.summary && (
              <p className="text-slate-200 mt-2 leading-relaxed">
                {symbolInfoMeta.summary.length > 240
                  ? `${symbolInfoMeta.summary.slice(0, 240)}...`
                  : symbolInfoMeta.summary}
              </p>
            )}
            {loadingSymbolInfo === symbolInfoMeta.symbol ? (
              <p className="text-slate-500 mt-1">상세 정보를 불러오는 중...</p>
            ) : (
              <p className="text-slate-400 mt-1">
                {`시가총액: ${formatMarketCap(symbolInfoMeta.market_cap)} · 직원 수: ${formatEmployees(symbolInfoMeta.employees)}`}
              </p>
            )}
            {symbolInfoMeta.website && (
              <p className="text-sky-300 mt-1 break-all">
                <a href={symbolInfoMeta.website} target="_blank" rel="noreferrer">
                  {symbolInfoMeta.website}
                </a>
              </p>
            )}
            <p className="text-slate-400 mt-1">
              {!symbolInfoMeta.summary
                ? "팝업을 닫지 않은 상태에서 다른 종목의 ? 를 누르면 바로 교체됩니다."
                : "초보자도 쉽게 볼 수 있도록 핵심 분류/요약을 함께 제공합니다."}
            </p>
            {selectedInfoSymbol && (
              <button
                type="button"
                onClick={closeSymbolInfo}
                className="mt-2 text-sky-300 text-[11px]"
              >
                닫기
              </button>
            )}
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          {form.mode === "basket" && (
            <div className="md:col-span-2 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-slate-400 uppercase">종목 장바구니</p>
                <button
                  type="button"
                  onClick={addBasketRow}
                  className="text-xs rounded-full border border-slate-700 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200"
                >
                  종목 추가
                </button>
              </div>
              {basketRows.map((row, index) => (
                <div key={`${row.symbol || "blank"}-${index}`} className="grid gap-2 md:grid-cols-[1.2fr_0.8fr_auto]">
                  <div>
                    <label className="block text-xs text-slate-500 mb-2">티커</label>
                    <input
                      type="text"
                      value={row.symbol}
                      aria-label={`장바구니 티커 ${index + 1}`}
                      onChange={(e) =>
                        upsertBasketRow(index, {
                          symbol: e.target.value.toUpperCase(),
                        })
                      }
                      className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-2">비중(%)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={row.weight}
                      aria-label={`장바구니 비중 ${index + 1}`}
                      onChange={(e) => upsertBasketRow(index, { weight: e.target.value })}
                      className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700"
                      placeholder="비워두면 자동 분배"
                    />
                  </div>
                  <div className="flex items-end">
                    <button
                      type="button"
                      onClick={() => removeBasketRow(index)}
                      className="px-3 py-3 rounded-xl border border-red-700 hover:bg-red-900/30 text-red-200"
                    >
                      삭제
                    </button>
                  </div>
                </div>
              ))}
              <p className="text-xs text-slate-500">
                비중은 100% 기준(25면 25%)입니다. 비워두면 남은 비중으로 자동 나눠집니다.
              </p>

              {basketAllocationPreview.length > 0 && (
                <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-4">
                  <p className="text-white text-sm font-semibold">현재 장바구니 배분 미리보기</p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    {basketAllocationPreview.map((item) => (
                      <div
                        key={item.symbol}
                        className="rounded-lg border border-slate-700/80 px-3 py-2 bg-slate-900/60 flex items-center justify-between"
                      >
                        <span className="text-slate-200 flex items-center gap-1.5">
                          {item.symbol}
                          {symbolInfoButton(item.symbol)}
                        </span>
                        <span className="text-white font-semibold">
                          {formatWeight(item.allocatedWeight)} · {formatMoney(item.allocatedCash)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <div>
            <label className="block text-xs text-slate-400 mb-2 uppercase">티커</label>
            <input
              type="text"
              value={form.symbol}
              onFocus={() => applyMode("single")}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="예: AAPL"
              disabled={Boolean(selectedPreset)}
              className={`w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700 ${
                selectedPreset ? "opacity-60 cursor-not-allowed" : ""
              }`}
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-2 uppercase">전략</label>
            <input
              readOnly
              value="ma_cross (단기/장기 이동평균 교차)"
              className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-2 uppercase">시작일 (선택)</label>
            <input
              type="date"
              value={form.startDate}
              onChange={(e) => setForm((prev) => ({ ...prev, startDate: e.target.value }))}
              className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-2 uppercase">종료일 (선택)</label>
            <input
              type="date"
              value={form.endDate}
              onChange={(e) => setForm((prev) => ({ ...prev, endDate: e.target.value }))}
              className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-2 uppercase">초기 자금</label>
            <input
              type="number"
              value={form.initialCash}
              onChange={(e) => setForm((prev) => ({ ...prev, initialCash: e.target.value }))}
              className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700"
            />
            <div className="flex flex-wrap gap-2 mt-2">
              {INITIAL_CASH_PRESETS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setForm((prev) => ({ ...prev, initialCash: String(value) }))}
                  className="text-xs rounded-full border border-slate-700 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200"
                >
                  {formatMoney(value).replace("$", "")}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-2 uppercase">단기 MA</label>
              <input
                type="number"
                min={2}
                value={form.shortWindow}
                onChange={(e) => setForm((prev) => ({ ...prev, shortWindow: e.target.value }))}
                className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-2 uppercase">장기 MA</label>
              <input
                type="number"
                min={3}
                value={form.longWindow}
                onChange={(e) => setForm((prev) => ({ ...prev, longWindow: e.target.value }))}
                className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-2 uppercase">수수료율</label>
            <input
              type="number"
              step="0.0001"
              value={form.feeRate}
              onChange={(e) => setForm((prev) => ({ ...prev, feeRate: e.target.value }))}
              className="w-full bg-slate-800 text-white rounded-xl px-4 py-3 border border-slate-700"
            />
          </div>
        </div>

        <button
          type="button"
          onClick={run}
          disabled={loading}
          className="w-full md:w-auto px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold disabled:opacity-50"
        >
          {loading ? "백테스트 실행중..." : "백테스트 실행"}
        </button>
        {loading && (
          <div className="rounded-xl border border-slate-700 bg-slate-800/50 px-4 py-3 text-sm text-slate-200">
            <p>{BACKTEST_PHASES[loadingStep]}</p>
            <div className="h-2 bg-slate-900 rounded-full mt-2 overflow-hidden">
              <span
                className="block h-full bg-sky-500 transition-all duration-300"
                style={{ width: `${((loadingStep + 1) / BACKTEST_PHASES.length) * 100}%` }}
              />
            </div>
          </div>
        )}

        {error && (
          <p className="rounded-lg border border-red-800 bg-red-900/30 px-4 py-2 text-sm text-red-300">
            {error}
          </p>
        )}
      </div>

      {result && (
        <>
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
              <p className="text-slate-400 text-sm">기간</p>
              <p className="text-white font-semibold mt-1">
                {result.period.from} ~ {result.period.to}
              </p>
            </div>
            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
              <p className="text-slate-400 text-sm">최종 자산</p>
              <p className="text-white font-semibold mt-1">{formatMoney(result.metrics.final_equity)}</p>
            </div>
            {result.composition?.length > 0 && (
              <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
                <p className="text-slate-400 text-sm">구성 종목</p>
                <div className="text-white font-semibold mt-1 space-y-1 text-sm">
                  {result.composition.map((item) => (
                    <div key={item.symbol} className="flex items-center gap-2">
                      <div className="inline-flex items-center gap-1.5">
                        {item.symbol}
                        {symbolInfoButton(item.symbol)}
                      </div>
                      <span>
                        · {formatWeight(item.weight)} · {formatMoney(item.allocated_cash)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
              <p className="text-slate-400 text-sm">총 수익률</p>
              <p className={`font-bold mt-1 ${result.metrics.total_return >= 0 ? "text-emerald-300" : "text-red-300"}`}>
                {result.metrics.total_return >= 0 ? "+" : ""}
                {result.metrics.total_return_percent.toFixed(2)}% ({formatMoney(result.metrics.total_return)})
              </p>
            </div>
            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
              <p className="text-slate-400 text-sm">최대 낙폭 (MDD)</p>
              <p className="text-white font-semibold mt-1">
                -{result.metrics.max_drawdown_percent.toFixed(2)}%
              </p>
            </div>
            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
              <p className="text-slate-400 text-sm">완료 거래</p>
              <p className="text-white font-semibold mt-1">
                {result.metrics.trade_count}회
              </p>
            </div>
            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
              <p className="text-slate-400 text-sm">승률</p>
              <p className="text-white font-semibold mt-1">
                {result.metrics.win_rate.toFixed(2)}% ({result.metrics.wins}/{result.metrics.trade_count})
              </p>
            </div>
            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
              <p className="text-slate-400 text-sm">현재 보유</p>
              <p className="text-white font-semibold mt-1">
                {result.metrics.remaining_shares}주
              </p>
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
            <h3 className="text-white text-lg font-bold mb-4">자산 곡선</h3>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={equityChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="date" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" tickFormatter={(value) => `$${Number(value).toLocaleString()}`} />
                  <Tooltip
                    formatter={(value) => `$${Number(value).toFixed(2)}`}
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#334155",
                      color: "#f8fafc",
                      borderRadius: "12px"
                    }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="자산"
                    stroke="#38bdf8"
                    strokeWidth={2}
                    dot={false}
                    name="총자산"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
            <h3 className="text-white text-lg font-bold mb-4">체결 내역</h3>
            {result.trades.length === 0 ? (
              <p className="text-slate-500 text-sm">조건이 성립하지 않아 거래가 발생하지 않았습니다.</p>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto custom-scrollbar">
                {result.trades.slice().reverse().map((trade, idx) => (
                  <div
                    key={`${trade.side}-${trade.date}-${idx}`}
                    className="bg-slate-800/50 border border-slate-700 rounded-xl p-3"
                  >
                    <div className="flex items-center justify-between">
                    <p className="text-white font-semibold">
                        {trade.side === "buy" ? "매수" : "매도"} · {trade.date}
                      </p>
                      <p className={`font-bold ${trade.side === "buy" ? "text-sky-300" : "text-emerald-300"}`}>
                        {trade.side === "buy" ? "진입" : "청산"}
                      </p>
                    </div>
                    <p className="text-slate-400 text-sm mt-1">
                      종목 {trade.symbol} · {trade.shares}주 · 단가 {formatMoney(trade.price)} · 수수료 {formatMoney(trade.fee)}
                    </p>
                    {trade.side === "sell" && (
                      <p className={`mt-1 text-sm ${trade.pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                        실현 수익 {trade.pnl >= 0 ? "+" : ""}{formatMoney(trade.pnl)} ({trade.pnl_percent}%)
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
