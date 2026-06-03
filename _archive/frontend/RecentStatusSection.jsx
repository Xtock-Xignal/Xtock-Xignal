"use client";
import { useState, useEffect, useMemo } from "react";
import api from "../../frontend/utils/api";
import { 
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine 
} from 'recharts';
import { SP500_LIST } from "../../frontend/data/sp500_list"; 

export default function RecentStatusSection({ user }) {
  const [query, setQuery] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showList, setShowList] = useState(false);
  
  const [portfolio, setPortfolio] = useState([]);
  const [myStockInfo, setMyStockInfo] = useState(null);

  useEffect(() => {
    if (user?.email) {
      api.post("/api/portfolio/list", { email: user.email })
         .then(res => {
           if(res.data.success) setPortfolio(res.data.portfolio);
         })
         .catch(err => console.error(err));
    }
  }, [user]);

  // [수정] 차트 Y축 범위 계산 (내 평단가를 무조건 포함하도록)
  const yAxisDomain = useMemo(() => {
    if (!data?.stock_data || data.stock_data.length === 0) return ['auto', 'auto'];

    const prices = data.stock_data.map(d => d.close);
    let minVal = Math.min(...prices);
    let maxVal = Math.max(...prices);

    // 내 평단가가 있으면 범위 확장
    if (myStockInfo) {
      minVal = Math.min(minVal, myStockInfo.buyPrice);
      maxVal = Math.max(maxVal, myStockInfo.buyPrice);
    }

    // 위아래 여백 10% 추가 (그래프가 꽉 차지 않게)
    const padding = (maxVal - minVal) * 0.1 || minVal * 0.1; 
    return [Math.floor(minVal - padding), Math.ceil(maxVal + padding)];
  }, [data, myStockInfo]);

  const filteredList = useMemo(() => {
    if (!query) return SP500_LIST;
    return SP500_LIST.filter(item => 
      item.name.toLowerCase().includes(query.toLowerCase()) || 
      item.symbol.toLowerCase().includes(query.toLowerCase())
    );
  }, [query]);

  const handleSearch = async (searchTerm) => {
    const finalQuery = searchTerm || query;
    if (!finalQuery) return;

    setLoading(true);
    setShowList(false);
    if (searchTerm) setQuery(searchTerm);

    try {
      const res = await api.post("/api/recent-status", { text: finalQuery });
      if (res.data.found) {
        const resultData = res.data;
        setData(resultData);

        const myItem = portfolio.find(p => p.symbol === resultData.symbol);
        
        if (myItem) {
          const currentPrice = resultData.stock_data[resultData.stock_data.length - 1]?.close || 0;
          const profitRate = ((currentPrice - myItem.price) / myItem.price) * 100;
          
          setMyStockInfo({
            buyPrice: myItem.price,
            profitRate: profitRate,
            isProfit: profitRate >= 0
          });
        } else {
          setMyStockInfo(null);
        }

      } else {
        alert(res.data.msg || "데이터를 찾을 수 없습니다.");
      }
    } catch (e) {
      console.error(e);
      alert("서버 통신 오류");
    }
    setLoading(false);
  };

  const handleTweetClick = (tweet) => {
    let url = "";
    if (tweet.id) {
      url = `https://twitter.com/${tweet.username}/status/${tweet.id}`;
    } else {
      url = `https://twitter.com/search?q=${encodeURIComponent(tweet.text)}`;
    }
    window.open(url, "_blank");
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload;
      return (
        <div className="bg-slate-800 border border-slate-600 p-3 rounded-lg shadow-xl text-sm">
          <p className="font-bold text-slate-200 mb-2">{label}</p>
          <div className="space-y-1">
            <p className="text-blue-400">종가: ${d.close.toLocaleString()}</p>
            <p className="text-green-400">시가: ${d.open.toLocaleString()}</p>
            <p className="text-red-400">고가: ${d.high.toLocaleString()}</p>
            <p className="text-slate-400">저가: ${d.low.toLocaleString()}</p>
            <p className="text-yellow-400">거래량: {d.volume.toLocaleString()}</p>
            {myStockInfo && (
               <p className="text-emerald-400 pt-1 border-t border-slate-600 mt-1 font-bold">
                 내 평단가: ${myStockInfo.buyPrice.toLocaleString()}
               </p>
            )}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-8 animate-fade-in pb-10">
      {/* 1. 검색 영역 (기존 유지) */}
      <div className="relative flex flex-col gap-2 z-20">
        <div className="flex gap-3">
          <input 
            className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:ring-2 focus:ring-blue-600 outline-none transition-all"
            placeholder="S&P 500 기업명 또는 티커 검색 (예: Apple, NVDA)"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setShowList(true); 
            }}
            onFocus={() => setShowList(true)} 
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button 
            onClick={() => handleSearch()} 
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-bold transition-colors disabled:opacity-50"
          >
            {loading ? "..." : "조회"}
          </button>
        </div>

        {showList && (
          <div className="absolute top-16 left-0 right-0 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl max-h-60 overflow-y-auto custom-scrollbar">
            {filteredList.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-1 p-2">
                {filteredList.map((stock) => (
                  <button
                    key={stock.symbol}
                    onClick={() => handleSearch(stock.symbol)}
                    className="flex items-center justify-between px-4 py-3 text-left hover:bg-slate-800 rounded-lg group transition-colors"
                  >
                    <span className="font-bold text-slate-200 group-hover:text-blue-400">
                      {stock.symbol}
                    </span>
                    <span className="text-sm text-slate-400 truncate ml-2">
                      {stock.name}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="p-4 text-slate-500 text-center">검색 결과가 없습니다.</div>
            )}
          </div>
        )}
        
        {showList && (
          <div className="fixed inset-0 z-[-1]" onClick={() => setShowList(false)} />
        )}
      </div>

      {data && (
        <div className="space-y-6 z-10">
          
          {myStockInfo && (
            <div className={`p-4 rounded-xl border flex justify-between items-center animate-slide-up ${
              myStockInfo.isProfit 
                ? "bg-red-500/10 border-red-500/50 text-red-400" 
                : "bg-blue-500/10 border-blue-500/50 text-blue-400"
            }`}>
              <div className="flex items-center gap-3">
                <span className="text-2xl">💼</span>
                <div>
                  <p className="text-sm font-medium opacity-80">내 보유 종목</p>
                  <p className="font-bold text-lg">평단가: ${myStockInfo.buyPrice.toLocaleString()}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium opacity-80">수익률</p>
                <p className="text-3xl font-black tracking-tight">
                  {myStockInfo.isProfit ? "+" : ""}{myStockInfo.profitRate.toFixed(2)}%
                </p>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            {/* 왼쪽: 최신 트윗 */}
            <div className="lg:col-span-4 bg-slate-900 border border-slate-800 rounded-2xl p-6 h-[500px] flex flex-col">
              <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                📢 {data.symbol} 최신 소식
                <span className="text-xs bg-red-500 text-white px-2 py-0.5 rounded-full animate-pulse">LIVE</span>
              </h3>
              
              <div className="flex-1 overflow-y-auto pr-2 space-y-4 custom-scrollbar">
                {data.tweets.length === 0 ? (
                  <div className="text-center text-slate-500 py-10">최근 소식이 없습니다.</div>
                ) : (
                  data.tweets.map((t, i) => (
                    <div 
                      key={i} 
                      onClick={() => handleTweetClick(t)} 
                      className="bg-slate-800 p-4 rounded-xl border border-slate-700 hover:border-blue-500 hover:bg-slate-700/80 transition-all cursor-pointer group"
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold text-white">
                            {t.author ? t.author.charAt(0) : "?"}
                          </div>
                          <div>
                            <span className="font-bold text-white block text-sm group-hover:underline">{t.author}</span>
                            <span className="text-xs text-slate-500">@{t.username}</span>
                          </div>
                        </div>
                        <span className="text-xs text-slate-400 whitespace-nowrap">{t.date}</span>
                      </div>
                      <p className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap">
                        {t.text}
                      </p>
                      <div className="mt-2 text-right opacity-0 group-hover:opacity-100 transition-opacity">
                         <span className="text-xs text-blue-400 flex items-center justify-end gap-1">
                           트윗 보러가기 ↗
                         </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 오른쪽: 주가 차트 */}
            <div className="lg:col-span-8 bg-slate-900 border border-slate-800 rounded-2xl p-6 h-[500px] flex flex-col">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold text-white">📈 {data.symbol} 주가 흐름 (최근 20일)</h3>
              </div>
              <div className="flex-1 w-full bg-slate-800/30 rounded-xl p-4">
                {data.stock_data && data.stock_data.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data.stock_data}>
                      <defs>
                        <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                      <XAxis 
                        dataKey="date" 
                        stroke="#94a3b8" 
                        tick={{fontSize: 12}} 
                        tickFormatter={(val) => val.substring(5)} 
                        minTickGap={30}
                      />
                      {/* [핵심] 계산된 도메인 적용 */}
                      <YAxis 
                        domain={yAxisDomain} 
                        stroke="#94a3b8" 
                        width={60}
                        tickFormatter={(val) => `$${Math.round(val)}`}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      
                      {myStockInfo && (
                        <ReferenceLine 
                          y={myStockInfo.buyPrice} 
                          stroke="#10b981" 
                          strokeDasharray="5 5" 
                          strokeWidth={2}
                          ifOverflow="extendDomain" // [추가] 차트 범위 밖이면 도메인 확장
                          label={{ position: 'right', value: 'My Price', fill: '#10b981', fontSize: 12, fontWeight: 'bold' }} 
                        />
                      )}

                      <Area 
                        type="monotone" 
                        dataKey="close" 
                        stroke="#3b82f6" 
                        strokeWidth={3}
                        fillOpacity={1} 
                        fill="url(#colorPrice)" 
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-slate-500">
                    데이터가 부족합니다.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 하단: OHLCV 상세 테이블 (기존 동일) */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 overflow-hidden">
            <h3 className="text-lg font-bold text-white mb-4">📊 일별 상세 데이터 (OHLCV)</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left text-slate-300">
                <thead className="text-xs text-slate-400 uppercase bg-slate-800 border-b border-slate-700">
                  <tr>
                    <th className="px-6 py-4">날짜</th>
                    <th className="px-6 py-4 text-right text-blue-400">종가 (Close)</th>
                    <th className="px-6 py-4 text-right">시가 (Open)</th>
                    <th className="px-6 py-4 text-right text-red-400">고가 (High)</th>
                    <th className="px-6 py-4 text-right text-blue-400">저가 (Low)</th>
                    <th className="px-6 py-4 text-right text-yellow-400">거래량 (Vol)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {data.stock_data.slice().reverse().map((row, i) => (
                    <tr key={i} className="hover:bg-slate-800/50 transition-colors">
                      <td className="px-6 py-4 font-medium text-white">{row.date}</td>
                      <td className="px-6 py-4 text-right font-bold">${row.close.toLocaleString()}</td>
                      <td className="px-6 py-4 text-right">${row.open.toLocaleString()}</td>
                      <td className="px-6 py-4 text-right">${row.high.toLocaleString()}</td>
                      <td className="px-6 py-4 text-right">${row.low.toLocaleString()}</td>
                      <td className="px-6 py-4 text-right">{row.volume.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}