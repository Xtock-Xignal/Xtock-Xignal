"use client";

import { usePathname } from "next/navigation";
import TweetCard from "@/components/TweetCard";
import api from "@/utils/api";
import { useEffect, useState } from "react";


export default function AnalysisPage() {
  const pathname = usePathname(); // 예: "/analysis/TSLA"
  let target = "";

  if (typeof pathname === "string") {
    const parts = pathname.split("/").filter(Boolean); // ["analysis", "TSLA"]
    if (parts.length >= 2) {
      target = decodeURIComponent(parts[parts.length - 1]);
    }
  }

 // 실제 데이터 상태
const [tweets, setTweets] = useState([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);

// API 요청 실행
useEffect(() => {
  if (!target) return;

  async function fetchData() {
    try {
      setLoading(true);
      const res = await api.get(`/analysis?target=${target}`);
      setTweets(res.data);
    } catch (err) {
      console.error(err);
      setError("데이터 로딩 실패");
    } finally {
      setLoading(false);
    }
  }

  fetchData();
}, [target]);


  return (
    <main className="min-h-screen px-4 py-8 bg-slate-950 text-slate-100">
      {/* 상단 헤더 */}
      <header className="max-w-5xl mx-auto mb-6">
        <h1 className="text-2xl font-bold mb-2">
          분석 페이지:{" "}
          <span className="text-blue-400">{target || "(대상 없음)"}</span>
        </h1>

        <p className="text-slate-300">
          여기에서 {target || "선택된 대상"} 관련 트윗, 감성 분석, 주가 차트,
          워드클라우드, 익일 수익률 등을 단계적으로 추가할 예정입니다.
        </p>
      </header>

      {/* 트윗 리스트 섹션 */}
      <section className="max-w-5xl mx-auto mt-6">
         <h2 className="text-lg font-semibold mb-3">트윗 & 감성 분석</h2>

         {loading && (
            <p className="text-slate-400 text-sm">⏳ 데이터를 불러오는 중...</p>
         )}

        {error && (
           <p className="text-red-400 text-sm">❌ {error}</p>
        )}

          {!loading && !error && tweets.length === 0 && (
            <p className="text-slate-400 text-sm">⚠ 관련 트윗을 찾지 못했습니다.</p>
          )}

         <div className="grid gap-4 mt-4">
           {!loading &&
            tweets.map((tweet) => (
             <TweetCard key={tweet.id} tweet={tweet} />
            ))}
         </div>
        </section>

    </main>
  );
}
