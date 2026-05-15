"use client";

import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from "next/navigation";
import { Search, ChevronLeft, ChevronRight, BookOpen, X, Loader2, Sparkles, Database, RefreshCw } from 'lucide-react';
import api from "../../utils/api";

const DUMMY_NEWS = [
  {
    id: 1,
    source: "XTock System",
    date: new Date().toISOString(),
    title: "서버 점검 중: 오프라인 모드로 실행됩니다.",
    original: "The live news server is currently unreachable. Please check your backend connection or Finnhub API key.",
    translated: "실시간 뉴스 서버에 연결할 수 없습니다. 백엔드 연결 상태나 Finnhub API 키를 확인해주세요."
  }
];

export default function NewsSimulatorSection() {
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [tooltip, setTooltip] = useState({ show: false, x: 0, y: 0, text: "" });

  const [matchedTerms, setMatchedTerms] = useState([]);
  const [isScanning, setIsScanning] = useState(false);

  const [newsList, setNewsList] = useState([]);
  const [isLoadingNews, setIsLoadingNews] = useState(true);

  const [summaryData, setSummaryData] = useState({}); 
  const [isSummarizing, setIsSummarizing] = useState(false);

  const [isTranslated, setIsTranslated] = useState(false);
  const [translatedText, setTranslatedText] = useState("");
  const [isTranslating, setIsTranslating] = useState(false);

  const router = useRouter();

  useEffect(() => {
    setIsTranslated(false);
    setTranslatedText("");
  }, [selectedArticle]);

  const handleTranslateToggle = async () => {
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
        url: selectedArticle.link
      });
      if (res.data && res.data.translated_text) {
        setTranslatedText(res.data.translated_text);
        setIsTranslated(true);
      }
    } catch (error) {
      console.error("Translation Error:", error);
      alert("번역 처리 중 문제가 발생했습니다.");
    } finally {
      setIsTranslating(false);
    }
  };
  
  const handleRequestSummary = async (article) => {
    if (summaryData[article.link]) return;
    setIsSummarizing(true);
    try {
      const res = await api.post("/api/news/summary", { text: article.original, url: article.link });
      setSummaryData(prev => ({ ...prev, [article.link]: res.data.summary }));
    } catch (error) {
      console.error("Summary request failed", error);
      setSummaryData(prev => ({ ...prev, [article.link]: "요약을 불러오는 데 실패했습니다." }));
    } finally {
      setIsSummarizing(false);
    }
  };

  // 페이지네이션 상태 관리 (한 페이지당 5개씩)
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  const [dictModal, setDictModal] = useState({
    isOpen: false,
    isLoading: false,
    term: "",
    data: null,
    error: false
  });

  const articleRef = useRef(null);

  // 1. 수동 '새로고침' 버튼을 눌렀을 때 실행되는 함수
  const fetchLiveNews = async (forceRefresh = false) => {
    setIsLoadingNews(true);
    try {
      // 현재 화면에 띄워진 가장 최신 뉴스 링크 찾기
      const latestUrl = newsList.length > 0 ? newsList[0].link : null;
      
      let url = `/api/news/live?force_refresh=${forceRefresh}`;
      // 강제 크롤링이 아닐 때만 latest_url을 보내서 빠른 판별을 요청
      if (latestUrl && !forceRefresh) {
        url += `&latest_url=${encodeURIComponent(latestUrl)}`;
      }

      const res = await api.get(url);
      
      if (res.data) {
        // 백엔드에서 새 뉴스가 없다고 판별하면 상태를 업데이트하지 않음 
        if (res.data.has_new === false) {
          console.log("[Info] 새로운 뉴스가 없습니다. 기존 화면을 유지합니다.");
        } else if (res.data.news) {
          // 새 뉴스가 있으면 화면 업데이트
          setNewsList(res.data.news);
          setCurrentPage(1); 
        }
      }
    } catch (error) {
      console.error("실시간 뉴스 로딩 실패:", error);
    } finally {
      setIsLoadingNews(false);
    }
  };

  // 2. 사용자가 뉴스 탭에 처음 진입했을 때 (초기 마운트)
  useEffect(() => {
    const loadInitialNews = async () => {
      setIsLoadingNews(true);
      try {
        // 1단계: DB에 저장된 뉴스를 0.1초 만에 가져와 화면에 먼저 뿌림 (로딩 최소화)
        const initialRes = await api.get('/api/news/live');
        let currentNews = [];

        if (initialRes.data && initialRes.data.news) {
          currentNews = initialRes.data.news;
          setNewsList(currentNews);
        }

        // 2단계: 화면 렌더링이 끝난 뒤, 백그라운드에서 새 뉴스가 있는지 확인
        const latestUrl = currentNews.length > 0 ? currentNews[0].link : null;
        
        if (latestUrl) {
          const updateRes = await api.get(`/api/news/live?latest_url=${encodeURIComponent(latestUrl)}`);
          
          // 새 뉴스가 발견되면 리스트의 맨 위에 밀어넣음
          if (updateRes.data && updateRes.data.has_new && updateRes.data.news) {
            setNewsList(updateRes.data.news);
            setCurrentPage(1);
          }
        }
      } catch (error) {
        console.error("초기 뉴스 로딩 실패:", error);
        setNewsList(DUMMY_NEWS); // 에러 시 더미 데이터 폴백 유지
      } finally {
        setIsLoadingNews(false);
      }
    };

    loadInitialNews();
  }, []); // 컴포넌트 마운트 시 1회만 실행

  const formatDate = (dateVal) => {
    if (!dateVal) return "방금 전";
    try {
      const d = typeof dateVal === 'number' ? new Date(dateVal * 1000) : new Date(dateVal);
      return d.toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return "최근";
    }
  };

  useEffect(() => {
    if (selectedArticle) {
      const scanArticle = async () => {
        setIsScanning(true);
        try {
          const fullText = `${selectedArticle.original} ${selectedArticle.translated}`;
          const res = await api.post("/api/terms/scan", { text: fullText });
          
          if (res.data && res.data.matched_terms) {
            setMatchedTerms(res.data.matched_terms);
          }
        } catch (error) {
          console.error("Scan Error:", error);
        } finally {
          setIsScanning(false);
        }
      };
      scanArticle();
    } else {
      setMatchedTerms([]); 
    }
  }, [selectedArticle]);

  const handleMouseUp = () => {
    const selection = window.getSelection();
    const selectedText = selection.toString().trim();

    if (selectedText.length < 2 || selectedText.length > 30) {
      setTooltip({ show: false, x: 0, y: 0, text: "" });
      return;
    }

    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();

    setTooltip({
      show: true,
      x: rect.left + rect.width / 2,
      y: rect.top - 40,
      text: selectedText
    });
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (!e.target.closest('#ai-tooltip-btn')) {
        setTooltip({ show: false, x: 0, y: 0, text: "" });
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearchDictionary = async (clickedWord = null) => {
    const termToSearch = typeof clickedWord === 'string' ? clickedWord : tooltip.text;
    setTooltip({ show: false, x: 0, y: 0, text: "" });
    
    setDictModal({ isOpen: true, isLoading: true, term: termToSearch, data: null, error: false });

    try {
      const res = await api.get(`/api/terms/search?keyword=${encodeURIComponent(termToSearch)}`);
      const responseData = res.data;
      
      setDictModal({
        isOpen: true,
        isLoading: false,
        term: termToSearch,
        data: res.data,
        error: false
      });

      if (responseData && responseData.found) {
        setMatchedTerms(prev => {
          const enMatch = responseData.en_term || termToSearch;
          const koMatch = responseData.ko_term || "";
          const existingIndex = prev.findIndex(t => t.en_term && t.en_term.toLowerCase() === enMatch.toLowerCase());

          if (existingIndex !== -1) {
            if (!prev[existingIndex].ko_term && koMatch) {
              const newArray = [...prev];
              newArray[existingIndex] = { ...newArray[existingIndex], ko_term: koMatch };
              return newArray;
            }
            return prev;
          }
          return [...prev, { en_term: enMatch, ko_term: koMatch }];
        });
      }
    } catch (error) {
      console.error("Dictionary Search Error:", error);
      setDictModal({ isOpen: true, isLoading: false, term: termToSearch, data: null, error: true });
    }
  };

  const renderHighlightedText = (text) => {
    if (!matchedTerms || matchedTerms.length === 0) return text;

    const wordsToHighlight = matchedTerms
      .flatMap(t => [t.en_term?.trim(), t.ko_term?.trim()])
      .filter(Boolean);
      
    if (wordsToHighlight.length === 0) return text;

    const escapedWords = wordsToHighlight.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const regexPattern = new RegExp(`(${escapedWords.join('|')}(?:\\s*\\([^)]{1,20}\\))?)`, 'gi');

    const parts = text.split(regexPattern);

    return parts.map((part, i) => {
      const trimmedPart = part.trim();
      const baseWord = trimmedPart.replace(/\s*\(.*\)/, '').trim();

      if (trimmedPart && wordsToHighlight.find(w => w.toLowerCase() === baseWord.toLowerCase())) {
        const leadingSpace = part.match(/^\s*/)[0];
        const trailingSpace = part.match(/\s*$/)[0];

        return (
          <React.Fragment key={i}>{leadingSpace}<span
            onClick={() => handleSearchDictionary(baseWord)}
            className="bg-blue-500/20 text-blue-300 font-semibold rounded cursor-pointer hover:bg-blue-500/40 transition-colors border-b border-blue-500/50"
            title="클릭해서 뜻 보기"
          >{trimmedPart}</span>{trailingSpace}</React.Fragment>
        );
      }
      return part;
    });
  };

  // [신규] 현재 페이지에 보여줄 기사 배열 계산

  const totalPages = Math.ceil(newsList.length / itemsPerPage) || 1;
  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentNews = newsList.slice(indexOfFirstItem, indexOfLastItem);

  const handleTagClick = (ticker) => {
        router.push(`/?tab=dashboard&ticker=${ticker}`);
    };

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 p-6 min-h-[600px] relative flex flex-col">
      
      {!selectedArticle ? (
        <div className="animate-fade-in flex flex-col h-full">
          <div className="flex items-center justify-between mb-6 shrink-0">
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <BookOpen className="text-blue-400" />
              글로벌 경제 속보
            </h2>
            <button 
              onClick={() => fetchLiveNews(true)}
              disabled={isLoadingNews}
              className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-sm text-slate-300 transition-colors disabled:opacity-50"
            >
              <RefreshCw size={16} className={isLoadingNews ? "animate-spin" : ""} />
              새로고침
            </button>
          </div>

          <div className="grid gap-4 flex-1">
            {isLoadingNews ? (
              <div className="py-20 flex flex-col items-center justify-center space-y-4">
                <Loader2 className="animate-spin text-blue-500" size={40} />
                <p className="text-slate-400">전 세계의 최신 뉴스를 수집하고 AI 번역 중입니다...</p>
              </div>
            ) : newsList.length === 0 ? (
              <div className="py-20 flex flex-col items-center justify-center text-slate-500">
                저장된 뉴스가 없습니다. 새로고침을 눌러주세요.
              </div>
            ) : (
              // 전체 newsList 대신 잘라낸 currentNews 맵핑
              currentNews.map((news, idx) => (
                <div 
                  key={news.id || idx} 
                  onClick={() => setSelectedArticle(news)}
                  className="p-5 bg-slate-800/50 hover:bg-slate-800 border border-slate-700 hover:border-blue-500 rounded-lg cursor-pointer transition-all group"
                >
                  <div className="flex justify-between items-center mb-2">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-1 text-xs font-bold rounded bg-slate-700 text-slate-300">
                        {news.source || "News"}
                      </span>
                      {/* 백엔드에서 판별한 S&P 500 핵심 기사인 경우 뱃지 노출 */}
                      {news.is_vip && (
                        <span className="px-2 py-1 text-xs font-bold rounded bg-blue-600 text-white shadow-[0_0_8px_rgba(37,99,235,0.4)]">
                          S&P 500 핵심
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-slate-400">{formatDate(news.date)}</div>
                  </div>
                  <div className="text-lg font-semibold text-slate-200 group-hover:text-blue-400 transition-colors line-clamp-2">
                    {news.title}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* [신규] 페이지네이션 컨트롤러 영역 */}
          {!isLoadingNews && newsList.length > 0 && (
            <div className="flex justify-center items-center gap-4 mt-8 shrink-0">
              <button 
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
                className="p-2 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft size={20} />
              </button>
              <span className="text-slate-400 font-medium text-sm">
                <strong className="text-white">{currentPage}</strong> / {totalPages}
              </span>
              <button 
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
                className="p-2 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight size={20} />
              </button>
            </div>
          )}
        </div>
      ) : (
        /* 상세 기사 뷰  */
        <div className="animate-fade-in relative" ref={articleRef}>
          <button 
            onClick={() => setSelectedArticle(null)}
            className="flex items-center gap-2 text-slate-400 hover:text-white mb-6 transition-colors"
          >
            <ChevronLeft size={20} />
            목록으로 돌아가기
          </button>

          <div onMouseUp={handleMouseUp}>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-2xl font-bold text-white pr-4 leading-tight">{selectedArticle.title}</h2>
              {isScanning && <Loader2 className="animate-spin text-blue-500 shrink-0" size={20} />}
            </div>
            <div className="flex items-center gap-3 text-sm text-slate-500 mb-8 flex-wrap">
              <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">
                {selectedArticle.source}
              </span>
              {selectedArticle.is_vip && (
                <span className="px-2 py-0.5 rounded bg-blue-600 text-white font-bold">
                  S&P 500 핵심
                </span>
              )}
              {selectedArticle.related_tags && selectedArticle.related_tags.map(tag => (
                <span 
                key={tag} 
                onClick={() => handleTagClick(tag)}
                className="cursor-pointer px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-bold hover:bg-emerald-500/40 hover:text-emerald-300 transition-colors"
            >
                #{tag}
                </span>
              ))}
              <span>{formatDate(selectedArticle.date)}</span>
            </div>

            <div className="grid md:grid-cols-2 gap-6 mb-6">
              {/* 1. ORIGINAL 박스*/}
              <div className="bg-slate-800/50 p-6 rounded-lg border border-slate-700 flex flex-col">
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-sm font-semibold text-blue-400 tracking-wider mt-1">
                    {isTranslated ? "KOREAN TRANSLATION" : "ORIGINAL"}
                  </h3>
                  
                  <div className="flex flex-col items-end">
                    <button 
                      onClick={handleTranslateToggle}
                      disabled={isTranslating}
                      className="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold rounded flex items-center gap-2 transition-colors disabled:opacity-50"
                    >
                      {isTranslating ? <Loader2 size={14} className="animate-spin" /> : null}
                      {isTranslating ? "번역 중..." : isTranslated ? "원문 보기 (EN)" : "한글로 보기 (KO)"}
                    </button>
                    {isTranslated && (
                      <span className="text-[10px] text-slate-500 mt-1">
                        * 기계 번역이므로 금융 용어 해석에 오차가 있을 수 있습니다.
                      </span>
                    )}
                  </div>
                </div>

                <div className="max-h-[400px] overflow-y-auto custom-scrollbar pr-2 flex-1">
                  <p className="text-slate-300 leading-relaxed text-lg font-serif whitespace-pre-wrap break-keep">
                    {isTranslated 
                      ? renderHighlightedText(translatedText) 
                      : renderHighlightedText(selectedArticle.original)}
                  </p>
                </div>
              </div>

              {/* 2. AI 요약 박스 */}
              <div className="bg-slate-800/50 p-6 rounded-lg border border-slate-700 flex flex-col">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-sm font-semibold text-purple-400 tracking-wider">AI SUMMARY</h3>
                  {!summaryData[selectedArticle.link] && (
                    <button 
                      onClick={() => handleRequestSummary(selectedArticle)}
                      disabled={isSummarizing}
                      className="px-3 py-1 bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold rounded flex items-center gap-2 transition-colors disabled:opacity-50"
                    >
                      {isSummarizing ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                      AI 3줄 요약 생성
                    </button>
                  )}
                </div>
                
                <div className="max-h-[400px] overflow-y-auto custom-scrollbar pr-2 flex-1">
                  {!summaryData[selectedArticle.link] ? (
                    <div className="flex flex-col items-center justify-center h-full text-slate-500 py-10">
                      <p>전체 해석 대신 핵심 내용만 빠르게 파악하세요.</p>
                      <p className="text-sm mt-2">상단의 버튼을 눌러 AI 요약을 요청할 수 있습니다.</p>
                    </div>
                  ) : (
                    <p className="text-slate-200 leading-relaxed text-lg break-keep whitespace-pre-wrap bg-slate-900/50 p-4 rounded-lg border border-slate-700">
                      {summaryData[selectedArticle.link]}
                    </p>
                  )}
                </div>
              </div>
            </div>
            <div className="flex justify-end mb-6">
              <a 
                href={selectedArticle.link} 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-lg transition-colors border border-slate-700 text-sm font-medium"
              >
                🔗 공식 기사 원문 보러가기
              </a>
            </div>
          </div>

          <div className="mt-8 p-4 bg-blue-900/20 border border-blue-900/50 rounded-lg flex items-start gap-3 select-none">
            <span className="text-blue-400 text-xl">💡</span>
            <p className="text-sm text-slate-400">
              파란색으로 <strong className="text-blue-300 bg-blue-500/20 px-1 rounded">강조된 단어</strong>를 클릭하거나, 모르는 단어를 마우스로 <strong className="text-slate-200">드래그</strong> 해보세요. AI 금융 사전이 즉시 뜻을 알려줍니다.
            </p>
          </div>
        </div>
      )}

      {tooltip.show && (
        <button
          id="ai-tooltip-btn"
          onClick={handleSearchDictionary}
          style={{ 
            position: 'fixed', 
            left: `${tooltip.x}px`, 
            top: `${tooltip.y}px`,
            transform: 'translateX(-50%)'
          }}
          className="z-50 flex items-center gap-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white px-4 py-2 rounded-full shadow-lg shadow-black/50 text-sm font-semibold animate-bounce"
        >
          <Search size={16} />
          &quot;{tooltip.text}&quot; 뜻 보기
        </button>
      )}

      {dictModal.isOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-md w-full shadow-2xl relative">
            <button 
              onClick={() => setDictModal({ ...dictModal, isOpen: false })}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X size={24} />
            </button>

            <h3 className="text-xl font-bold text-white mb-4 pr-8">
              &quot;{dictModal.term}&quot;
            </h3>

            {dictModal.isLoading ? (
              <div className="flex flex-col items-center justify-center py-10 gap-3">
                <Loader2 className="animate-spin text-blue-500" size={32} />
                <p className="text-slate-400 text-sm">XTock-Xignal AI가 분석 중입니다...</p>
              </div>
            ) : dictModal.error ? (
              <div className="py-6 text-center text-red-400">
                <p>사전 데이터를 불러오는 데 실패했습니다.</p>
                <p className="text-sm mt-2 text-slate-500">백엔드 연결을 확인해주세요.</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="bg-slate-800 p-4 rounded-xl text-slate-200 leading-relaxed break-keep">
                  {dictModal.data?.definition || "해당 단어에 대한 설명을 찾을 수 없습니다."}
                </div>
                
                <div className="flex items-center gap-2 text-xs font-medium justify-end text-slate-400">
                  {dictModal.data?.source === 'DB' ? (
                    <span className="flex items-center gap-1"><Database size={14} className="text-emerald-400"/> XTock 자체 DB 검증 완료</span>
                  ) : (
                    <span className="flex items-center gap-1"><Sparkles size={14} className="text-purple-400"/> AI 실시간 분석 결과</span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}