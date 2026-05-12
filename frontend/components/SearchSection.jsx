import { useEffect, useRef, useState } from "react";

function TweetCard({ tweet }) {
  return (
    <div className="bg-slate-800 rounded-xl pt-8 pb-6 px-4 border border-slate-700">
      <div className="flex items-start gap-3">
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold">
          {tweet.author_id}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className="font-semibold text-white">{tweet.author}</span>
            <span className="text-slate-400">@{tweet.handle}</span>
            <span className="text-slate-500">·</span>
            <span className="text-slate-400">{tweet.time}</span>
          </div>
          <p className="text-slate-200 leading-relaxed mb-4">{tweet.text}</p>
        </div>
      </div>
    </div>
  );
}

// 감성 분석 부분 제외

function StockChart({ data, postIndex }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data || data.length === 0) return;

    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const width = rect.width;
    const height = rect.height;
    const padding = { top: 40, right: 40, bottom: 50, left: 60 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // 배경
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(0, 0, width, height);

    // 데이터 범위
    const prices = data.map((d) => d.price);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const priceRange = maxPrice - minPrice || 1;

    // Y축 눈금
    const yTicks = 5;
    const yStep = priceRange / (yTicks - 1);

    // 격자
    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);

    for (let i = 0; i < yTicks; i++) {
      const y = padding.top + (chartHeight / (yTicks - 1)) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left + chartWidth, y);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    // X축, Y축
    ctx.strokeStyle = "#475569";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, padding.top + chartHeight);
    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
    ctx.stroke();

    // Y축 레이블
    ctx.fillStyle = "#94a3b8";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";

    for (let i = 0; i < yTicks; i++) {
      const price = maxPrice - yStep * i;
      const y = padding.top + (chartHeight / (yTicks - 1)) * i;
      ctx.fillText(`₩${Math.round(price).toLocaleString()}`, padding.left - 10, y);
    }

    // X축 레이블
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const xStep = Math.max(1, Math.floor(data.length / 7));

    data.forEach((d, i) => {
      if (i % xStep === 0 || i === data.length - 1) {
        const x = padding.left + (chartWidth / (data.length - 1)) * i;
        ctx.fillText(d.date, x, padding.top + chartHeight + 10);
      }
    });

    // 게시물 발행 시점
    const postX = padding.left + (chartWidth / (data.length - 1)) * postIndex;
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(postX, padding.top);
    ctx.lineTo(postX, padding.top + chartHeight);
    ctx.stroke();
    ctx.setLineDash([]);

    // 게시물 발행 레이블
    ctx.fillStyle = "#f59e0b";
    ctx.font = "bold 12px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText("게시물 발행", postX, padding.top - 5);

    // 선 그래프
    ctx.strokeStyle = "#22c55e";
    ctx.lineWidth = 3;
    ctx.beginPath();

    data.forEach((d, i) => {
      const x = padding.left + (chartWidth / (data.length - 1)) * i;
      const y =
        padding.top +
        chartHeight -
        ((d.price - minPrice) / priceRange) * chartHeight;

      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.stroke();

    // 포인트
    data.forEach((d, i) => {
      const x = padding.left + (chartWidth / (data.length - 1)) * i;
      const y =
        padding.top +
        chartHeight -
        ((d.price - minPrice) / priceRange) * chartHeight;

      ctx.fillStyle = "#22c55e";
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
    });
  }, [data, postIndex]);

  return (
    <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
      <h3 className="text-xl font-semibold text-white">주가 변동 추이</h3>
      <div className="relative">
        <canvas ref={canvasRef} className="w-full" style={{ height: "320px" }} />
      </div>
      <div className="mt-4 flex gap-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-green-500 rounded-full" />
          <span className="text-slate-300">주가</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-0.5 bg-amber-500" />
          <span className="text-slate-300">게시물 발행 시점</span>
        </div>
      </div>
    </div>
  );
}

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
        placeholder="기업명이나 인물명을 입력하세요 (예: Tesla, NVIDIA, Elon Musk)"
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
        {isLoading ? "분석 중..." : "분석 시작"}
      </button>
    </div>
  );
}

export default function SearchSection({
  searchQuery,
  isLoading,
  analysisResult,
  onSearch,
}) {
  return (
    <section className="w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 space-y-8">
      <div>
        <SearchBar onSearch={onSearch} isLoading={isLoading} />
      </div>

      {!searchQuery && !isLoading && !analysisResult && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full">
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-4 border border-slate-700">
            <div className="text-blue-400 text-2xl mb-2">🏢</div>
            <h3 className="text-white font-semibold mb-1">기업 분석</h3>
            <p className="text-slate-400 text-sm">재무 정보와 시장 동향 파악</p>
          </div>
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-4 border border-slate-700">
            <div className="text-blue-400 text-2xl mb-2">👤</div>
            <h3 className="text-white font-semibold mb-1">인물 분석</h3>
            <p className="text-slate-400 text-sm">주요 인물의 영향력 분석</p>
          </div>
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-4 border border-slate-700">
            <div className="text-blue-400 text-2xl mb-2">📊</div>
            <h3 className="text-white font-semibold mb-1">실시간 데이터</h3>
            <p className="text-slate-400 text-sm">최신 시장 정보 제공</p>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="flex flex-col justify-center items-center py-12 gap-4">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <div className="text-white text-lg">분석 중입니다...</div>
        </div>
      )}

      {!isLoading && analysisResult && (
        <div className="w-full animate-fade-in">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h2 className="text-2xl font-bold text-white">
                 {analysisResult.companyInfo ? analysisResult.companyInfo.name : searchQuery} 분석 결과
              </h2>
              {analysisResult.companyInfo && (
                  <p className="text-slate-400 text-sm mt-1">{analysisResult.companyInfo.financial_summary}</p>
              )}
            </div>
          </div>

          {/* 감성 분석 제거 후 2열 레이아웃: 트윗(4) vs 차트(8) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
            <div className="lg:col-span-5">
              <TweetCard tweet={analysisResult.tweet} />
            </div>

            <div className="lg:col-span-7">
              <StockChart
                data={analysisResult.stockData}
                postIndex={analysisResult.postIndex}
              />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}