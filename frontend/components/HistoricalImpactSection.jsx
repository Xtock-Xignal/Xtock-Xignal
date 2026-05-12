"use client";
import { useState } from "react";
import api from "../utils/api"; 
import { 
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid 
} from 'recharts';

export default function HistoricalImpactSection() {
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState([]); 
  const [selectedEvent, setSelectedEvent] = useState(null); 
  const [chartData, setChartData] = useState(null); 
  
  const [loadingList, setLoadingList] = useState(false);
  const [loadingChart, setLoadingChart] = useState(false);

  // 텍스트 내의 URL을 감지해서 클릭 가능한 링크로 변환
  const formatTextWithLinks = (text) => {
    if (!text) return "";
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    
    return text.split(urlRegex).map((part, index) => {
      if (part.match(urlRegex)) {
        return (
          <a
            key={index}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400 hover:text-blue-300 hover:underline z-20 relative break-all"
            onClick={(e) => e.stopPropagation()} 
          >
            {part}
          </a>
        );
      }
      return part;
    });
  };

  // 1. 목록 검색
  const handleSearch = async () => {
    if(!query) return;
    setLoadingList(true);
    setCandidates([]);
    setSelectedEvent(null);
    setChartData(null);
    
    try {
      const res = await api.post("/api/historical-impact", { text: query });
      if(res.data.found) {
        setCandidates(res.data.candidates);
      } else {
        alert(res.data.msg || "결과가 없습니다.");
      }
    } catch(e) {
      console.error(e);
      alert("검색 중 오류 발생");
    }
    setLoadingList(false);
  };

  // 2. 특정 트윗 클릭 시 차트 조회
  const handleSelectEvent = async (event) => {
    setSelectedEvent(event);
    setLoadingChart(true);
    setChartData(null); 

    try {
      const res = await api.post("/api/historical-chart", { 
        symbol: event.symbol, 
        date: event.created_at 
      });
      setChartData(res.data);
    } catch(e) {
      console.error(e);
      alert("차트 데이터를 불러오는데 실패했습니다.");
    }
    setLoadingChart(false);
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-900 border border-slate-700 p-3 rounded shadow-xl text-sm text-white">
          <p className="font-bold mb-1 text-slate-400">{label}</p>
          <p className="text-emerald-400 font-bold text-lg">
            ${Number(payload[0].value).toFixed(2)}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6 animate-fade-in flex flex-col h-[850px]">
      {/* 상단: 검색바 */}
      <div className="flex gap-3 w-full max-w-2xl mx-auto shrink-0">
        <input 
          className="flex-1 bg-slate-900 border border-slate-700 rounded-full px-6 py-3 text-white outline-none focus:ring-2 focus:ring-blue-500 placeholder-slate-500 transition-all"
          placeholder="주제나 기업명 검색 (예: Elon Musk, Twitter, Interest Rate)"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key==='Enter' && handleSearch()}
        />
        <button 
          onClick={handleSearch} 
          disabled={loadingList}
          className="bg-blue-500 hover:bg-blue-400 text-white px-8 py-3 rounded-full font-bold transition-colors disabled:opacity-50"
        >
          {loadingList ? "..." : "검색"}
        </button>
      </div>

      {/* 메인 컨텐츠 (2단 분할) */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0">
        
        {/* 왼쪽: 트윗 리스트 (X 스타일 적용) */}
        <div className="lg:col-span-5 bg-black border border-slate-800 rounded-2xl flex flex-col overflow-hidden shadow-2xl">
          <div className="p-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur shrink-0">
            <h3 className="font-bold text-slate-200 text-lg">
              🔍 검색 결과 ({candidates.length})
            </h3>
          </div>
          
          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {candidates.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-600">
                <span className="text-4xl mb-2">🐦</span>
                <p>관련된 트윗이 없습니다.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800">
                {candidates.map((item, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSelectEvent(item)}
                    className={`w-full text-left p-4 hover:bg-slate-900/50 transition-colors flex gap-3 ${
                      selectedEvent?.id === item.id ? "bg-slate-900 border-l-4 border-blue-500" : ""
                    }`}
                  >
                    {/* 프로필 이미지 (가짜) */}
                    <div className="w-10 h-10 rounded-full bg-slate-700 flex-shrink-0 flex items-center justify-center text-white font-bold overflow-hidden">
                      {item.symbol ? item.symbol.charAt(0) : "?"}
                    </div>

                    {/* 트윗 내용 */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-1 mb-0.5">
                        <span className="font-bold text-white truncate text-sm hover:underline">
                          {item.author_id === "Unknown" ? item.symbol : item.author_id}
                        </span>
                        <span className="text-slate-500 text-xs truncate">@{item.symbol}</span>
                        <span className="text-slate-500 text-xs">·</span>
                        <span className="text-slate-500 text-xs">{item.created_at.substring(0, 10)}</span>
                      </div>
                      
                      <div className="text-slate-300 text-sm leading-snug break-words mb-2">
                        {formatTextWithLinks(item.text)}
                      </div>

                      {/* 하단 아이콘 (장식용) */}
                      <div className="flex justify-between text-slate-500 max-w-[80%]">
                        <div className="flex items-center gap-1 hover:text-blue-400 group">
                          <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current"><g><path d="M1.751 10c0-4.42 3.584-8 8.005-8h4.366c4.49 0 8.129 3.64 8.129 8.13 0 2.96-1.607 5.68-4.196 7.11l-8.054 4.46v-3.69h-.067c-4.49.1-8.183-3.51-8.183-8.01zm8.005-6c-3.317 0-6.005 2.69-6.005 6 0 3.37 2.77 6.08 6.138 6.01l.351-.01h1.761v2.3l5.087-2.81c1.951-1.08 3.163-3.13 3.163-5.36 0-3.39-2.744-6.13-6.129-6.13H9.756z"></path></g></svg>
                          <span className="text-xs group-hover:text-blue-400">24</span>
                        </div>
                        <div className="flex items-center gap-1 hover:text-green-400 group">
                          <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current"><g><path d="M4.5 3.88l4.432 4.14-1.364 1.46L5.5 7.55V16c0 1.1.896 2 2 2H13v2H7.5c-2.209 0-4-1.79-4-4V7.55L1.432 9.48.068 8.02 4.5 3.88zM16.5 6H11V4h5.5c2.209 0 4 1.79 4 4v8.45l2.068-1.93 1.364 1.46-4.432 4.14-4.432-4.14 1.364-1.46 2.068 1.93V8c0-1.1-.896-2-2-2z"></path></g></svg>
                          <span className="text-xs group-hover:text-green-400">12</span>
                        </div>
                        <div className="flex items-center gap-1 hover:text-pink-600 group">
                          <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current"><g><path d="M16.697 5.5c-1.222-.06-2.679.51-3.89 2.16l-.805 1.09-.806-1.09C9.984 6.01 8.526 5.44 7.304 5.5c-1.243.07-2.349.78-2.91 1.91-.552 1.12-.633 2.78.479 4.82 1.074 1.97 3.257 4.27 7.129 6.61 3.87-2.34 6.052-4.64 7.126-6.61 1.111-2.04 1.03-3.7.477-4.82-.561-1.13-1.666-1.84-2.908-1.91zm4.187 7.69c-1.351 2.48-4.001 5.12-8.379 7.67l-.503.3-.504-.3c-4.379-2.55-7.029-5.19-8.382-7.67-1.36-2.5-1.41-4.86-.514-6.67.887-1.79 2.647-2.91 4.601-3.01 1.651-.09 3.368.56 4.798 2.01 1.429-1.45 3.146-2.1 4.796-2.01 1.954.1 3.714 1.22 4.601 3.01.896 1.81.846 4.17-.514 6.67z"></path></g></svg>
                          <span className="text-xs group-hover:text-pink-600">105</span>
                        </div>
                        <div className="flex items-center gap-1 hover:text-blue-400">
                          <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current"><g><path d="M12 2.59l5.7 5.7-1.41 1.42L13 6.41V16h-2V6.41l-3.3 3.3-1.41-1.42L12 2.59zM21 15l-.02 3.51c0 1.38-1.12 2.49-2.5 2.49H5.5C4.12 21 3 19.88 3 18.5V15h2v3.5c0 .28.22.5.5.5h12.98c.28 0 .5-.22.5-.5L19 15h2z"></path></g></svg>
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 오른쪽: 상세 차트 (텍스트 제거 및 차트 확장) */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col h-full shadow-xl">
          {selectedEvent ? (
            <>
              {/* 차트 헤더 */}
              <div className="flex justify-between items-center mb-4 shrink-0">
                <div>
                  <h3 className="text-2xl font-bold text-white flex items-center gap-2">
                    📉 {selectedEvent.symbol} 주가 흐름
                  </h3>
                  <p className="text-slate-400 text-sm mt-1">
                    Event Date: <span className="text-blue-400 font-bold">{selectedEvent.created_at.substring(0, 10)}</span>
                  </p>
                </div>
                {chartData && (
                  <div className={`px-5 py-3 rounded-xl border ${
                    chartData.impact_return >= 0 
                      ? "bg-red-500/10 border-red-500/50 text-red-400" 
                      : "bg-blue-500/10 border-blue-500/50 text-blue-400"
                  }`}>
                    <span className="text-xs font-bold block opacity-75">Impact (T+5)</span>
                    <span className="text-2xl font-extrabold tracking-tight">
                      {chartData.impact_return > 0 ? "+" : ""}
                      {chartData.impact_return.toFixed(2)}%
                    </span>
                  </div>
                )}
              </div>

              {/* 차트 영역 (확장됨) */}
              <div className="flex-1 w-full bg-black/20 rounded-2xl border border-slate-800 p-4 relative">
                {loadingChart ? (
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-3"></div>
                    <span className="text-slate-400 font-medium">데이터 분석 중...</span>
                  </div>
                ) : chartData && chartData.stock_data && chartData.stock_data.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData.stock_data}>
                      <defs>
                        <linearGradient id="lineColor" x1="0" y1="0" x2="1" y2="0">
                          <stop offset="0%" stopColor="#3b82f6" />
                          <stop offset="100%" stopColor="#8b5cf6" />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                      <XAxis 
                        dataKey="date" 
                        stroke="#94a3b8" 
                        tick={{fontSize: 12}}
                        tickFormatter={(val) => val.substring(5)} 
                        interval="preserveStartEnd"
                        minTickGap={30}
                        dy={10}
                      />
                      <YAxis 
                        domain={['auto', 'auto']} 
                        stroke="#94a3b8" 
                        width={50} 
                        tickFormatter={(val) => `$${Math.round(val)}`}
                        tick={{fontSize: 12}}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      
                      {/* 이벤트 발생일 표시선 */}
                      {chartData.post_index >= 0 && chartData.stock_data[chartData.post_index] && (
                        <ReferenceLine 
                          x={chartData.stock_data[chartData.post_index].date} 
                          stroke="#fbbf24" 
                          strokeWidth={2}
                          strokeDasharray="4 4"
                          label={{ position: 'top', value: 'EVENT', fill: '#fbbf24', fontSize: 12, fontWeight: 'bold' }} 
                        />
                      )}

                      <Line 
                        type="monotone" 
                        dataKey="price" 
                        stroke="url(#lineColor)" 
                        strokeWidth={3} 
                        dot={false}
                        activeDot={{r: 6, strokeWidth: 0, fill: '#fff'}}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-slate-500">
                    <p>표시할 차트 데이터가 없습니다.</p>
                    <p className="text-xs mt-2">(API 제한 또는 휴장일 가능성)</p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 opacity-60">
              <span className="text-6xl mb-6">👈</span>
              <p className="text-lg font-medium">왼쪽 목록에서 트윗을 선택해주세요.</p>
              <p className="text-sm mt-2">해당 시점의 주가 영향력을 분석해드립니다.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}