"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Database,
  Languages,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import api from "../../utils/api";

const DEFAULT_SYMBOLS = "SPY,QQQ,AAPL,MSFT,NVDA,TSLA,AMZN,GOOGL,META,JPM,XOM,LLY";
const ITEMS_PER_PAGE = 5;

const FALLBACK_NEWS = [
  {
    id: "fallback",
    source: "XTock System",
    date: new Date().toISOString(),
    title: "뉴스 서버에 연결할 수 없습니다",
    original:
      "The live news server is currently unreachable. Please check the backend connection or Finnhub API key.",
    translated:
      "실시간 뉴스 서버에 연결할 수 없습니다. 백엔드 연결 상태 또는 Finnhub API 키를 확인해주세요.",
  },
];

const formatDate = (dateVal) => {
  if (!dateVal) return "방금 전";
  try {
    const d = typeof dateVal === "number" ? new Date(dateVal * 1000) : new Date(dateVal);
    return d.toLocaleString("ko-KR", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "최근";
  }
};

export default function NewsSimulatorSection() {
  const router = useRouter();
  const articleRef = useRef(null);

  const [newsList, setNewsList] = useState([]);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoadingNews, setIsLoadingNews] = useState(true);
  const [symbolInput, setSymbolInput] = useState("");

  const [isTranslated, setIsTranslated] = useState(false);
  const [translatedText, setTranslatedText] = useState("");
  const [isTranslating, setIsTranslating] = useState(false);

  const [summaryData, setSummaryData] = useState({});
  const [isSummarizing, setIsSummarizing] = useState(false);

  const [tooltip, setTooltip] = useState({ show: false, x: 0, y: 0, text: "" });
  const [dictModal, setDictModal] = useState({
    isOpen: false,
    isLoading: false,
    term: "",
    data: null,
    error: false,
  });

  const totalPages = Math.max(1, Math.ceil(newsList.length / ITEMS_PER_PAGE));
  const currentNews = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return newsList.slice(start, start + ITEMS_PER_PAGE);
  }, [currentPage, newsList]);

  const openArticle = (article) => {
    setIsTranslated(false);
    setTranslatedText("");
    setTooltip({ show: false, x: 0, y: 0, text: "" });
    setSelectedArticle(article);
  };

  const closeArticle = () => {
    setIsTranslated(false);
    setTranslatedText("");
    setTooltip({ show: false, x: 0, y: 0, text: "" });
    setSelectedArticle(null);
  };

  const fetchLiveNews = async (forceRefresh = false, overrideSymbols = symbolInput) => {
    setIsLoadingNews(true);
    try {
      const latestUrl = newsList.length > 0 ? newsList[0].link : null;
      const params = new URLSearchParams({
        force_refresh: String(Boolean(forceRefresh)),
        symbols: overrideSymbols || DEFAULT_SYMBOLS,
      });
      if (latestUrl && !forceRefresh) {
        params.set("latest_url", latestUrl);
      }

      const res = await api.get(`/api/news/live?${params.toString()}`);
      if (res.data?.news) {
        setNewsList(res.data.news);
        if (res.data.has_new) setCurrentPage(1);
      }
    } catch (error) {
      console.error("뉴스 로딩 실패:", error);
      setNewsList(FALLBACK_NEWS);
    } finally {
      setIsLoadingNews(false);
    }
  };

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void fetchLiveNews(false, DEFAULT_SYMBOLS);
    }, 0);
    return () => window.clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (!e.target.closest("#ai-tooltip-btn")) {
        setTooltip({ show: false, x: 0, y: 0, text: "" });
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleTranslateToggle = async () => {
    if (!selectedArticle) return;
    if (isTranslated) {
      setIsTranslated(false);
      return;
    }
    if (translatedText) {
      setIsTranslated(true);
      return;
    }

    setIsTranslating(true);
    try {
      const res = await api.post("/api/news/translate", {
        text: selectedArticle.original,
        url: selectedArticle.link,
      });
      setTranslatedText(res.data?.translated_text || "");
      setIsTranslated(true);
    } catch (error) {
      console.error("번역 실패:", error);
      alert("번역 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setIsTranslating(false);
    }
  };

  const handleRequestSummary = async (article) => {
    if (!article || summaryData[article.link]) return;
    setIsSummarizing(true);
    try {
      const res = await api.post("/api/news/summary", {
        text: article.original,
        url: article.link,
      });
      setSummaryData((prev) => ({
        ...prev,
        [article.link]: res.data?.summary || "요약을 만들 수 없습니다.",
      }));
    } catch (error) {
      console.error("요약 실패:", error);
      setSummaryData((prev) => ({
        ...prev,
        [article.link]: "요약을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.",
      }));
    } finally {
      setIsSummarizing(false);
    }
  };

  const handleMouseUp = () => {
    const selection = window.getSelection();
    const selectedText = selection?.toString().trim() || "";

    if (selectedText.length < 2 || selectedText.length > 300 || !selection.rangeCount) {
      setTooltip({ show: false, x: 0, y: 0, text: "" });
      return;
    }

    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    setTooltip({
      show: true,
      x: rect.left + rect.width / 2,
      y: Math.max(12, rect.top - 48),
      text: selectedText,
    });
  };

  const handleSearchDictionary = async (clickedWord = null) => {
    const termToSearch = typeof clickedWord === "string" ? clickedWord : tooltip.text;
    if (!termToSearch) return;
    setTooltip({ show: false, x: 0, y: 0, text: "" });
    setDictModal({ isOpen: true, isLoading: true, term: termToSearch, data: null, error: false });

    try {
      const res = await api.get(`/api/terms/search?keyword=${encodeURIComponent(termToSearch)}`);
      const responseData = res.data;
      setDictModal({
        isOpen: true,
        isLoading: false,
        term: termToSearch,
        data: responseData,
        error: false,
      });

    } catch (error) {
      console.error("용어 검색 실패:", error);
      setDictModal({ isOpen: true, isLoading: false, term: termToSearch, data: null, error: true });
    }
  };

  const renderIndustryBadge = (classification) => {
    if (!classification || classification.sector === "Unclassified") return null;
    return (
      <span
        className="rounded border border-amber-500/30 bg-amber-500/15 px-2 py-1 text-xs font-bold text-amber-300"
        title={classification.explanation || "산업 분류"}
      >
        {classification.sector} · {classification.industry_group}
      </span>
    );
  };

  const handleTagClick = (ticker) => {
    router.push(`/?tab=dashboard&ticker=${ticker}`);
  };

  const articleBody = isTranslated ? translatedText : selectedArticle?.original || "";

  return (
    <div className="relative flex min-h-[600px] flex-col rounded-xl border border-slate-800 bg-slate-900 p-6">
      {!selectedArticle ? (
        <div className="flex h-full flex-col">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-2xl font-bold text-white">
                <BookOpen className="text-blue-400" />
                최신 금융 뉴스
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                Yahoo Finance와 Finnhub에서 최신 시장/종목 뉴스를 가져옵니다.
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") fetchLiveNews(true); }}
                className="min-w-0 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white outline-none focus:ring-2 focus:ring-blue-500 sm:w-[24rem]"
                placeholder="예: AAPL,NVDA,TSLA"
                aria-label="뉴스 조회 티커"
              />
              <button
                onClick={() => fetchLiveNews(true)}
                disabled={isLoadingNews}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-700 disabled:opacity-50"
              >
                <RefreshCw size={16} className={isLoadingNews ? "animate-spin" : ""} />
                새로고침
              </button>
            </div>
          </div>

          <div className="grid flex-1 gap-4">
            {isLoadingNews ? (
              <div className="flex flex-col items-center justify-center gap-4 py-20">
                <Loader2 className="animate-spin text-blue-500" size={40} />
                <p className="text-slate-400">최신 뉴스를 불러오는 중입니다.</p>
              </div>
            ) : newsList.length === 0 ? (
              <div className="flex items-center justify-center py-20 text-slate-500">
                저장된 뉴스가 없습니다. 새로고침을 눌러주세요.
              </div>
            ) : (
              currentNews.map((news, index) => (
                <button
                  key={news.link || news.id || index}
                  onClick={() => openArticle(news)}
                  className="group rounded-lg border border-slate-700 bg-slate-800/50 p-5 text-left transition-all hover:border-blue-500 hover:bg-slate-800"
                >
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-slate-700 px-2 py-1 text-xs font-bold text-slate-300">
                        {news.source || "News"}
                      </span>
                      {renderIndustryBadge(news.industry_classification)}
                    </div>
                    <span className="text-sm text-slate-400">{formatDate(news.date)}</span>
                  </div>
                  <div className="line-clamp-2 text-lg font-semibold text-slate-200 transition-colors group-hover:text-blue-400">
                    {news.title}
                  </div>
                </button>
              ))
            )}
          </div>

          {!isLoadingNews && newsList.length > 0 && (
            <div className="mt-8 flex items-center justify-center gap-4">
              <button
                onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
                className="rounded bg-slate-800 p-2 text-slate-300 transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-30"
                aria-label="이전 페이지"
              >
                <ChevronLeft size={20} />
              </button>
              <span className="text-sm font-medium text-slate-400">
                <strong className="text-white">{currentPage}</strong> / {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
                className="rounded bg-slate-800 p-2 text-slate-300 transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-30"
                aria-label="다음 페이지"
              >
                <ChevronRight size={20} />
              </button>
            </div>
          )}
        </div>
      ) : (
        <div ref={articleRef}>
          <button
            onClick={closeArticle}
            className="mb-6 flex items-center gap-2 text-slate-400 transition-colors hover:text-white"
          >
            <ChevronLeft size={20} />
            목록으로 돌아가기
          </button>

          <div onMouseUp={handleMouseUp}>
            <div className="mb-2 flex items-start justify-between gap-3">
              <h2 className="text-2xl font-bold leading-tight text-white">{selectedArticle.title}</h2>
            </div>
            <div className="mb-8 flex flex-wrap items-center gap-3 text-sm text-slate-500">
              <span className="rounded border border-slate-700 bg-slate-800 px-2 py-0.5 text-slate-300">
                {selectedArticle.source}
              </span>
              {renderIndustryBadge(selectedArticle.industry_classification)}
              {(selectedArticle.related_tags || []).map((tag) => (
                <button
                  key={tag}
                  onClick={() => handleTagClick(tag)}
                  className="rounded border border-emerald-500/30 bg-emerald-500/20 px-2 py-0.5 font-bold text-emerald-400 transition-colors hover:bg-emerald-500/40"
                >
                  #{tag}
                </button>
              ))}
              <span>{formatDate(selectedArticle.date)}</span>
            </div>

            <div className="mb-6 grid gap-6 md:grid-cols-2">
              <div className="flex flex-col rounded-lg border border-slate-700 bg-slate-800/50 p-6">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <h3 className="mt-1 text-sm font-semibold tracking-wider text-blue-400">
                    {isTranslated ? "한글 번역" : "원문 기사"}
                  </h3>
                  <button
                    onClick={handleTranslateToggle}
                    disabled={isTranslating}
                    className="inline-flex items-center gap-2 rounded bg-slate-700 px-3 py-1 text-xs font-bold text-white transition-colors hover:bg-slate-600 disabled:opacity-50"
                  >
                    {isTranslating ? <Loader2 size={14} className="animate-spin" /> : <Languages size={14} />}
                    {isTranslating ? "번역 중" : isTranslated ? "원문 보기" : "한글로 보기"}
                  </button>
                </div>
                <div className="max-h-[440px] flex-1 overflow-y-auto pr-2 custom-scrollbar">
                  <p className="whitespace-pre-wrap break-keep font-serif text-lg leading-relaxed text-slate-300">
                    {articleBody}
                  </p>
                </div>
              </div>

              <div className="flex flex-col rounded-lg border border-slate-700 bg-slate-800/50 p-6">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold tracking-wider text-purple-400">AI 3줄 요약</h3>
                  {!summaryData[selectedArticle.link] && (
                    <button
                      onClick={() => handleRequestSummary(selectedArticle)}
                      disabled={isSummarizing}
                      className="inline-flex items-center gap-2 rounded bg-purple-600 px-3 py-1 text-xs font-bold text-white transition-colors hover:bg-purple-700 disabled:opacity-50"
                    >
                      {isSummarizing ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                      요약 생성
                    </button>
                  )}
                </div>
                <div className="max-h-[440px] flex-1 overflow-y-auto pr-2 custom-scrollbar">
                  {!summaryData[selectedArticle.link] ? (
                    <div className="flex h-full flex-col items-center justify-center py-10 text-center text-slate-500">
                      <p>기사의 핵심 내용을 3줄로 요약할 수 있습니다.</p>
                      <p className="mt-2 text-sm">요약 생성 버튼을 눌러주세요.</p>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap break-keep rounded-lg border border-slate-700 bg-slate-900/50 p-4 text-lg leading-relaxed text-slate-200">
                      {summaryData[selectedArticle.link]}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {selectedArticle.link && (
              <div className="mb-6 flex justify-end">
                <a
                  href={selectedArticle.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-700"
                >
                  원문 기사 열기
                </a>
              </div>
            )}
          </div>

          <div className="mt-8 flex items-start gap-3 rounded-lg border border-blue-900/50 bg-blue-900/20 p-4 select-none">
            <span className="text-xl text-blue-400">💡</span>
            <p className="text-sm text-slate-400">
              모르는 단어를 마우스로{" "}
              <strong className="text-slate-200">드래그</strong>해보세요.
              AI 금융 사전이 즉시 뜻을 알려드립니다. 검색된 용어는 DB에 저장되어 다음 검색은 더 빠릅니다.
            </p>
          </div>
        </div>
      )}

      {tooltip.show && (
        <button
          id="ai-tooltip-btn"
          onClick={() => handleSearchDictionary()}
          style={{
            position: "fixed",
            left: `${tooltip.x}px`,
            top: `${tooltip.y}px`,
            transform: "translateX(-50%)",
          }}
          className="z-50 inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-blue-600 to-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-black/50 hover:from-blue-500 hover:to-purple-500"
        >
          <Search size={16} />
          &quot;{tooltip.text}&quot; 뜻 보기
        </button>
      )}

      {dictModal.isOpen && (
        <Modal onClose={() => setDictModal((prev) => ({ ...prev, isOpen: false }))}>
          <h3 className="mb-4 pr-8 text-xl font-bold text-white">&quot;{dictModal.term}&quot;</h3>
          {dictModal.isLoading ? (
            <LoadingText text="용어를 분석하는 중입니다." />
          ) : dictModal.error ? (
            <p className="py-6 text-center text-red-400">용어 설명을 불러오지 못했습니다.</p>
          ) : (
            <div className="space-y-4">
              <div className="rounded-xl bg-slate-800 p-4 leading-relaxed text-slate-200">
                {dictModal.data?.definition || "해당 용어 설명을 찾을 수 없습니다."}
              </div>
              <div className="flex justify-end text-xs font-medium text-slate-400">
                {dictModal.data?.source === "DB" ? (
                  <span className="flex items-center gap-1">
                    <Database size={14} className="text-emerald-400" /> XTock DB
                  </span>
                ) : (
                  <span className="flex items-center gap-1">
                    <Sparkles size={14} className="text-purple-400" /> AI 분석
                  </span>
                )}
              </div>
            </div>
          )}
        </Modal>
      )}

    </div>
  );
}

function Modal({ children, onClose }) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-slate-400 hover:text-white"
          aria-label="닫기"
        >
          <X size={24} />
        </button>
        {children}
      </div>
    </div>
  );
}

function LoadingText({ text }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10">
      <Loader2 className="animate-spin text-blue-500" size={32} />
      <p className="text-sm text-slate-400">{text}</p>
    </div>
  );
}
