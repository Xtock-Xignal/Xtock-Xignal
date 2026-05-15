"use client";
import React, { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import api from "../utils/api";
import { SP500_LIST } from "../data/sp500_list";
import { 
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid 
} from 'recharts';
import { TrendingUp, TrendingDown, ChevronDown, ChevronUp, Search, Activity, DollarSign, BarChart3 } from 'lucide-react';

export default function DashboardSection() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [marketData, setMarketData] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // 리스트 관련 상태
  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [expandedSymbol, setExpandedSymbol] = useState(null); 
  const [expandedStockData, setExpandedStockData] = useState(null); 
  const [loadingDetail, setLoadingDetail] = useState(false);

  const ITEMS_PER_PAGE = 10;

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const res = await api.get("/api/dashboard/summary");
        setMarketData(res.data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, []);

  const fetchStockDetail = async (symbol) => {
    setExpandedSymbol(symbol);
    setLoadingDetail(true);
    setExpandedStockData(null);

    try {
      const res = await api.post("/api/recent-status", { text: symbol });
      if (res.data.found) {
        setExpandedStockData(res.data.stock_data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDetail(false);
    }
  };

  // 기존 클릭 핸들러는 분리한 함수를 가져다 쓰도록 수정
  const handleRowClick = (symbol) => {
    if (expandedSymbol === symbol) {
      setExpandedSymbol(null); 
      return;
    }
    fetchStockDetail(symbol);
  };

  // [신규] 뉴스에서 넘어온 URL 파라미터(ticker) 감지 및 자동 실행
  useEffect(() => {
    const ticker = searchParams.get("ticker");
    if (ticker) {
      const targetSymbol = ticker.toUpperCase();
      
      // 1. 검색창에 티커를 입력하여 리스트 최상단에 해당 종목만 남김
      setSearchTerm(targetSymbol);
      setCurrentPage(1);
      
      // 2. 해당 종목의 차트 및 볼륨 데이터를 백엔드에 요청하고 아코디언 오픈
      fetchStockDetail(targetSymbol);

      router.replace("/?tab=dashboard", { scroll: false });
    }
  }, [searchParams, router]);

  // 필터링 및 페이징 로직
  const filteredList = SP500_LIST.filter(item => 
    item.symbol.includes(searchTerm.toUpperCase()) || 
    item.name.toLowerCase().includes(searchTerm.toLowerCase())
  );
  
  const totalPages = Math.ceil(filteredList.length / ITEMS_PER_PAGE) || 1;
  const currentList = filteredList.slice(
    (currentPage - 1) * ITEMS_PER_PAGE, 
    currentPage * ITEMS_PER_PAGE
  );

  const formatNumber = (num) => num?.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
  
  // 시가총액 포맷팅 (조 단위 변환)
  const formatMarketCap = (cap) => {
    if (!cap) return "-";
    if (cap > 1e12) return `$${(cap / 1e12).toFixed(2)}T`; // Trillion (조 달러)
    if (cap > 1e9) return `$${(cap / 1e9).toFixed(2)}B`;  // Billion (십억 달러)
    return `$${cap.toLocaleString()}`;
  };

  // 20일 최저/최고가 계산 (범위 바 표시용)
  const getPriceRange = () => {
    if (!marketData?.topStock?.chartData) return { min: 0, max: 0, percent: 0 };
    const prices = marketData.topStock.chartData.map(d => d.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const current = marketData.topStock.price;
    // 현재 위치 퍼센트 (0~100)
    const percent = ((current - min) / (max - min)) * 100;
    return { min, max, percent: Math.max(0, Math.min(100, percent)) };
  };

  const priceRange = getPriceRange();

  if (loading) return <div className="p-10 text-center text-slate-500 animate-pulse">시장 데이터를 분석 중입니다...</div>;

  return (
    <div className="space-y-8 animate-fade-in pb-10">
      
      {/* 상단 섹션: 대장주 & 지수 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Market Leader (시총 1위) - 디자인 변경: 차트 제거 -> 데이터 강조 */}
        <div className="lg:col-span-2 bg-gradient-to-br from-slate-900 to-slate-900 border border-slate-800 rounded-2xl p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <Activity size={100} />
          </div>
          
          <div className="relative z-10 grid grid-cols-1 md:grid-cols-2 gap-8 items-center h-full">
            {/* 왼쪽: 가격 정보 */}
            <div>
              <span className="bg-blue-600 text-white text-xs font-bold px-2 py-1 rounded-full mb-3 inline-block">
                MARKET LEADER
              </span>
              <h2 className="text-4xl font-black text-white mb-1 tracking-tight">{marketData?.topStock?.symbol}</h2>
              <p className="text-slate-400 text-sm mb-6 font-medium">Most Valuable Company</p>
              
              <div className="flex items-baseline gap-4">
                <span className="text-5xl font-bold text-white tracking-tighter">${formatNumber(marketData?.topStock?.price)}</span>
                <span className={`text-xl font-bold flex items-center px-3 py-1 rounded-lg ${marketData?.topStock?.change >= 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                  {marketData?.topStock?.change >= 0 ? <TrendingUp size={24} className="mr-2"/> : <TrendingDown size={24} className="mr-2"/>}
                  {formatNumber(marketData?.topStock?.changePercent)}%
                </span>
              </div>
            </div>

            {/* 오른쪽: 주요 통계 (Market Cap & Range Bar) */}
            <div className="bg-black/20 rounded-xl p-5 border border-white/5 backdrop-blur-sm">
              <div className="mb-6">
                <p className="text-slate-400 text-xs font-bold uppercase mb-1 flex items-center gap-2">
                  <DollarSign size={14} /> Market Cap (시가총액)
                </p>
                <p className="text-3xl font-bold text-white tracking-tight">
                  {formatMarketCap(marketData?.topStock?.marketCap)}
                </p>
              </div>

              <div>
                <div className="flex justify-between text-xs text-slate-400 mb-2 font-medium">
                  <span>20 Day Low</span>
                  <span>20 Day High</span>
                </div>
                {/* Range Bar */}
                <div className="h-3 bg-slate-700/50 rounded-full relative overflow-hidden">
                  <div 
                    className={`absolute top-0 left-0 h-full rounded-full transition-all duration-1000 ${marketData?.topStock?.change >= 0 ? 'bg-gradient-to-r from-emerald-600 to-emerald-400' : 'bg-gradient-to-r from-rose-600 to-rose-400'}`}
                    style={{ width: `${priceRange.percent}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-slate-300 mt-1.5 font-mono">
                  <span>${formatNumber(priceRange.min)}</span>
                  <span className={marketData?.topStock?.change >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>Current</span>
                  <span>${formatNumber(priceRange.max)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Market Indices */}
        <div className="space-y-4">
          {marketData?.indices?.map((idx, i) => (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 flex justify-between items-center hover:border-slate-700 transition-colors">
              <div>
                <p className="text-slate-400 text-xs font-bold uppercase tracking-wider flex items-center gap-2">
                  <BarChart3 size={14} /> {idx.name}
                </p>
                <p className="text-white text-xl font-bold mt-2 tracking-tight">{formatNumber(idx.price)}</p>
              </div>
              <div className={`text-right ${idx.change >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                <p className="text-sm font-bold flex items-center justify-end gap-1">
                  {idx.change >= 0 ? "+" : ""}{formatNumber(idx.change)}
                </p>
                <p className={`text-xs px-2 py-1 rounded-md mt-1 inline-block font-bold ${idx.change >= 0 ? 'bg-emerald-500/10' : 'bg-rose-500/10'}`}>
                  {idx.changePercent >= 0 ? "+" : ""}{formatNumber(idx.changePercent)}%
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 하단 섹션: S&P 500 리스트 */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        
        <div className="p-6 border-b border-slate-800 flex flex-col md:flex-row justify-between items-center gap-4">
          <h3 className="text-xl font-bold text-white flex items-center gap-2">
            🇺🇸 S&P 500 기업 리스트
            <span className="text-xs font-normal text-slate-500 bg-slate-800 px-2 py-1 rounded-full">Top 500</span>
          </h3>
          <div className="relative w-full md:w-64">
            <Search className="absolute left-3 top-3 text-slate-500" size={18} />
            <input 
              className="w-full bg-black/30 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500 transition-all"
              placeholder="기업명 또는 티커 검색..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1); 
              }}
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left text-slate-300">
            <thead className="text-xs text-slate-500 uppercase bg-slate-800/50">
              <tr>
                <th className="px-6 py-4 w-24">Symbol</th>
                <th className="px-6 py-4">Company Name</th>
                <th className="px-6 py-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {currentList.map((stock) => (
                <React.Fragment key={stock.symbol}>
                  <tr 
                    onClick={() => handleRowClick(stock.symbol)}
                    className={`cursor-pointer transition-colors ${
                      expandedSymbol === stock.symbol ? "bg-slate-800/80" : "hover:bg-slate-800/40"
                    }`}
                  >
                    <td className="px-6 py-4 font-bold text-white">{stock.symbol}</td>
                    <td className="px-6 py-4 font-medium">{stock.name}</td>
                    <td className="px-6 py-4 text-right">
                      {expandedSymbol === stock.symbol ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </td>
                  </tr>
                  
                  {expandedSymbol === stock.symbol && (
                    <tr>
                      <td colSpan="3" className="p-0 bg-slate-900/50 border-b border-slate-800 animate-slide-down">
                        <div className="p-6">
                          {loadingDetail ? (
                            <div className="py-10 text-center text-blue-400 animate-pulse">데이터 불러오는 중...</div>
                          ) : expandedStockData ? (
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                              <div className="h-[300px] bg-black/20 rounded-xl p-4 border border-slate-700/50">
                                <h4 className="text-sm font-bold text-slate-400 mb-4">{stock.symbol} Price Chart (20D)</h4>
                                <ResponsiveContainer width="100%" height="100%">
                                  <AreaChart data={expandedStockData}>
                                    <defs>
                                      <linearGradient id="chartColor" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                                      </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                                    <XAxis dataKey="date" stroke="#64748b" tick={{fontSize: 10}} tickFormatter={(val) => val.substring(5)} />
                                    <YAxis domain={['auto', 'auto']} stroke="#64748b" width={40} tick={{fontSize: 10}} />
                                    <Tooltip contentStyle={{backgroundColor: '#0f172a', borderColor: '#334155', color: '#fff'}} />
                                    <Area type="monotone" dataKey="close" stroke="#3b82f6" fillOpacity={1} fill="url(#chartColor)" />
                                  </AreaChart>
                                </ResponsiveContainer>
                              </div>

                              <div className="overflow-y-auto h-[300px] custom-scrollbar border border-slate-700/50 rounded-xl">
                                <table className="w-full text-xs text-right">
                                  <thead className="bg-slate-800 text-slate-400 sticky top-0">
                                    <tr>
                                      <th className="px-4 py-2 text-left">Date</th>
                                      <th className="px-4 py-2 text-blue-400">Close</th>
                                      <th className="px-4 py-2">Vol</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-800">
                                    {expandedStockData.slice().reverse().map((d, i) => (
                                      <tr key={i} className="hover:bg-white/5">
                                        <td className="px-4 py-2 text-left text-slate-300">{d.date}</td>
                                        <td className="px-4 py-2 font-bold">${d.close.toLocaleString()}</td>
                                        <td className="px-4 py-2 text-slate-500">{d.volume.toLocaleString()}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          ) : (
                            <div className="text-center text-red-400 py-4">데이터를 불러올 수 없습니다.</div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>

        <div className="p-4 border-t border-slate-800 flex justify-center items-center gap-4">
          <button 
            onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
            disabled={currentPage === 1}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            이전
          </button>
          <span className="text-sm text-slate-400">
            Page <span className="text-white font-bold">{currentPage}</span> of {totalPages}
          </span>
          <button 
            onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
            disabled={currentPage === totalPages}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            다음
          </button>
        </div>

      </div>
    </div>
  );
}