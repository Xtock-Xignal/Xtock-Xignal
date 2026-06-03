"use client";

export default function TweetCard({ tweet }) {
  const author = tweet?.author || tweet?.user || tweet?.username || "Unknown";
  const content = tweet?.content || tweet?.text || tweet?.summary || "";
  const sentiment = tweet?.sentiment || tweet?.label || "neutral";
  const score = tweet?.score ?? tweet?.sentiment_score ?? tweet?.confidence;

  return (
    <article className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-slate-100">{author}</p>
        <span className="rounded-full bg-slate-800 px-2 py-1 text-xs text-slate-300">
          {sentiment}
        </span>
      </div>
      <p className="text-sm leading-6 text-slate-300">
        {content || "표시할 분석 내용이 없습니다."}
      </p>
      {score !== undefined && score !== null && (
        <p className="mt-3 text-xs text-slate-500">score: {score}</p>
      )}
    </article>
  );
}
