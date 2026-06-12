"use client";

import { useState } from "react";

function SearchBar({ onSearch, isLoading }) {
  const [query, setQuery] = useState("");

  const handleSearch = () => {
    const trimmed = query.trim();
    if (!trimmed || isLoading) return;
    onSearch(trimmed);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <div className="flex flex-col sm:flex-row gap-3 w-full">
      <input
        type="text"
        placeholder="기업명이나 티커를 입력하세요 (예: Tesla, NVIDIA, AAPL)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        className="flex-1 rounded-xl border border-slate-700 bg-slate-800 px-4 py-3 text-base outline-none focus:ring-2 focus:ring-blue-500 text-white placeholder-slate-500 disabled:opacity-50"
      />
      <button
        onClick={handleSearch}
        disabled={isLoading}
        className="rounded-xl bg-blue-600 hover:bg-blue-500 px-6 py-3 text-base font-semibold transition-colors whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? "검색 중..." : "검색"}
      </button>
    </div>
  );
}

export default function SearchSection() {
  const [isLoading, setIsLoading] = useState(false);
  const [query, setQuery] = useState("");

  const handleSearch = (q) => {
    setQuery(q);
    setIsLoading(false);
  };

  return (
    <section className="w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 space-y-8">
      <div>
        <SearchBar onSearch={handleSearch} isLoading={isLoading} />
      </div>

      {!query && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full">
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-4 border border-slate-700">
            <div className="text-blue-400 text-2xl mb-2">🏢</div>
            <h3 className="text-white font-semibold mb-1">기업 분석</h3>
            <p className="text-slate-400 text-sm">재무 정보와 시장 동향 파악</p>
          </div>
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-4 border border-slate-700">
            <div className="text-blue-400 text-2xl mb-2">📈</div>
            <h3 className="text-white font-semibold mb-1">주가 조회</h3>
            <p className="text-slate-400 text-sm">최근 주가 흐름 확인</p>
          </div>
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-4 border border-slate-700">
            <div className="text-blue-400 text-2xl mb-2">📊</div>
            <h3 className="text-white font-semibold mb-1">실시간 데이터</h3>
            <p className="text-slate-400 text-sm">최신 시장 정보 제공</p>
          </div>
        </div>
      )}

      {query && (
        <div className="text-slate-400 text-sm py-4 text-center">
          <span className="text-slate-200 font-semibold">{query}</span> 검색 완료.
          더 자세한 분석은 대시보드 또는 백테스팅 메뉴를 이용해주세요.
        </div>
      )}
    </section>
  );
}
