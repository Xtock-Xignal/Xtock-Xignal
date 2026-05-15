"use client";

import { useState, useEffect } from "react";
import {
  Search as SearchIcon,
  Settings,
  LayoutDashboard,
  User,
  Menu,
  X,
  BookOpen,
  Activity,
  History,
  BarChart3,
  LogOut,
  Newspaper
} from "lucide-react";

import { useSearchParams } from "next/navigation";

import LoginPage from "@/features/auth/LoginPage";
import DashboardSection from "@/features/dashboard/DashboardSection";
import LearningCenter from "@/features/learn/LearningCenter";
import BacktestSection from "@/features/backtest/BacktestSection";
import PortfolioSection from "@/features/portfolio/PortfolioSection";
import SettingsSection from "@/features/settings/SettingsSection";
import NewsSimulatorSection from "@/features/simulator/NewsSimulatorSection";

// API 유틸리티 import
import api from "../utils/api";

const AUTH_STORAGE_KEY = "xtock-auth-user-v1";
const AUTH_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30일

const isAuthValid = (raw) => {
  try {
    const parsed = JSON.parse(raw);

    // legacy: old schema was directly user object
    if (parsed && parsed.email && parsed.username) {
      return {
        user: parsed,
        expiresAt: Date.now() + AUTH_TTL_MS,
      };
    }

    if (!parsed || typeof parsed !== "object") {
      return null;
    }

    const expiresAt = Number(parsed.expiresAt);
    const nestedUser = parsed.user;
    if (!nestedUser || !nestedUser.email || !nestedUser.username || !Number.isFinite(expiresAt)) {
      return null;
    }

    if (Date.now() > expiresAt) {
      return null;
    }

    return {
      user: nestedUser,
      expiresAt,
    };
  } catch {
    return null;
  }
};

export default function Home() {

  const searchParams = useSearchParams();

  // [수정] 로그인 상태 관리 (기본값 null)
  const [user, setUser] = useState(null); 
  const [isAuthChecking, setIsAuthChecking] = useState(true);
  
  const [activeMenu, setActiveMenu] = useState("dashboard");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [todayDate, setTodayDate] = useState("");

  // [추가] 검색 관련 상태 (handleSearch에서 사용됨)
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);

  useEffect(() => {
    const tabFromUrl = searchParams.get("tab");
    if (tabFromUrl) {
      // url에 ?tab=dashboard 등이 들어오면 해당 화면으로 즉시 전환
      setActiveMenu(tabFromUrl); 
    }
  }, [searchParams]);

  useEffect(() => {
    setTodayDate(new Date().toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "long",
    }));
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(AUTH_STORAGE_KEY);
      if (!raw) {
        setIsAuthChecking(false);
        return;
      }

      const restored = isAuthValid(raw);
      if (!restored) {
        localStorage.removeItem(AUTH_STORAGE_KEY);
        setIsAuthChecking(false);
        return;
      }

      setUser(restored.user);
      localStorage.setItem(
        AUTH_STORAGE_KEY,
        JSON.stringify({
          user: restored.user,
          savedAt: Date.now(),
          expiresAt: Date.now() + AUTH_TTL_MS,
        })
      );
      setIsAuthChecking(false);
    } catch {
      // 손상된 저장값은 무시하고 로그인 화면으로 이동
      localStorage.removeItem(AUTH_STORAGE_KEY);
      setIsAuthChecking(false);
    }
  }, []);

  if (isAuthChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100">
        <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900 px-6 py-4 text-sm text-slate-300">
          <span className="inline-block h-5 w-5 rounded-full border-2 border-blue-400/60 border-t-transparent animate-spin" />
          인증을 확인하고 있어요...
        </div>
      </div>
    );
  }

  // [추가] 로그인이 안 되어 있으면 로그인 페이지를 먼저 보여줌
  if (!user) {
    return (
      <LoginPage
        onLogin={(userData) => {
          const authPayload = {
            user: userData,
            savedAt: Date.now(),
            expiresAt: Date.now() + AUTH_TTL_MS,
          };
          localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authPayload));
          setUser(userData);
        }}
      />
    );
  }

  const handleSearch = async (query) => {
    setSearchQuery(query);
    setIsLoading(true);
    setAnalysisResult(null);
    
    try {
      console.log(`Searching for: ${query}`);
      
      const res = await api.post("/api/match-company", { text: query });
      
      if (!res.data.matches || res.data.matches.length === 0) {
        alert("관련된 과거 분석 사례를 찾을 수 없습니다.");
        setIsLoading(false);
        return;
      }

      const data = res.data.matches[0]; 
      console.log("Received Data:", data);

      setAnalysisResult({
        tweet: data.tweet,
        stockData: data.stockData,
        postIndex: data.postIndex,
        companyInfo: {
            name: data.name,
            financial_summary: data.financial_summary
        }
      });

    } catch (error) {
      console.error("Connection Error:", error);
      alert("서버 연결 실패. 백엔드 확인");
    } finally {
      setIsLoading(false);
    }
  };

  const menuItems = [
    { id: "dashboard", icon: LayoutDashboard, label: "대시보드" },
    { id: "simulator", icon: Newspaper, label: "뉴스 시뮬레이터" },
    { id: "learn", icon: BookOpen, label: "학습 센터" },
    { id: "backtest", icon: BarChart3, label: "백테스팅" },
    { id: "portfolio", icon: User, label: "모의 투자(포트폴리오)" },
    { id: "settings", icon: Settings, label: "설정" },
  ];

  const goToPortfolio = () => {
    setActiveMenu("portfolio");
    setIsMobileMenuOpen(false);
  };

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">

      {/* 모바일 메뉴 버튼 */}
      <button
        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-slate-800 rounded-lg border border-slate-700"
      >
        {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* 사이드바 */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-40 w-64 bg-slate-900 border-r border-slate-800 flex flex-col transition-transform duration-300 ${
          isMobileMenuOpen
            ? "translate-x-0"
            : "-translate-x-full lg:translate-x-0"
        }`}
      >
        
        {/* 사용자 정보 (로그인 정보 연동) */}
        <div className="pt-6 px-4 pb-4 border-t border-slate-800">
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-slate-800">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white">
               {/* 유저 이름의 첫 글자 표시 */}
              <span className="text-sm font-bold">{user.username.charAt(0).toUpperCase()}</span>
            </div>
            <div className="flex-1 min-w-0">
              {/* [수정] 실제 로그인한 유저 정보 표시 */}
              <p className="text-sm font-semibold truncate">{user.username}</p>
              <p className="text-xs text-slate-400 truncate">{user.email}</p>
            </div>
          </div>
        </div>

        {/* 메뉴 */}
        <nav className="flex-1 p-4 flex flex-col justify-between">
          <ul className="space-y-2">
            {menuItems.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.id}>
                  <button
                    onClick={() => {
                      setActiveMenu(item.id);
                      setIsMobileMenuOpen(false);
                    }}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                      activeMenu === item.id
                        ? "bg-blue-600 text-white"
                        : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
                    }`}
                  >
                    <Icon size={20} />
                    <span className="font-medium">{item.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>

          {/* [추가] 로그아웃 버튼 (사이드바 하단) */}
          <div className="pt-4 border-t border-slate-800 mt-4">
            <button
              onClick={() => {
                localStorage.removeItem(AUTH_STORAGE_KEY);
                setUser(null);
              }} // 유저 상태 초기화 -> 로그인 페이지로 이동
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-slate-400 hover:bg-red-900/20 hover:text-red-400 transition-colors"
            >
              <LogOut size={20} />
              <span className="font-medium">로그아웃</span>
            </button>
          </div>
        </nav>
      </aside>

      {/* 메인 컨텐츠 */}
      <main className="flex-1 overflow-auto custom-scrollbar">
        {/* 상단 서비스 타이틀 (XtockXignal 로고) */}
        <div className="w-full text-center mt-6">
          <h1 className="inline-flex items-center gap-2 font-extrabold select-none">
            <span className="text-8xl leading-none bg-clip-text text-transparent bg-gradient-to-br from-blue-500 to-purple-600">X</span>
            <div className="flex flex-col text-left leading-tight">
              <span className="text-4xl text-white">tock</span>
              <span className="text-4xl text-slate-500">ignal</span>
            </div>
          </h1>
        </div>

        <div className="max-w-7xl mx-auto px-4 py-10 lg:px-8">
          {/* 헤더 */}
          <header className="mb-8">
            <div className="flex items-center justify-between mb-2">
              <h1 className="text-3xl md:text-4xl font-extrabold text-white">
                {activeMenu === "dashboard" && "메인 대시보드"}
                {activeMenu === "simulator" && "뉴스 시뮬레이터"}
                {activeMenu === "learn" && "학습 센터"}
                {activeMenu === "backtest" && "백테스팅"}
                {activeMenu === "portfolio" && "내 포트폴리오"}
                {activeMenu === "settings" && "설정"}
              </h1>
              <p className="text-sm text-slate-400 font-medium">
                {todayDate}
              </p>
            </div>
            <p className="text-sm md:text-base text-slate-400">
              {activeMenu === "dashboard" && "오늘의 시장 동향 및 예측 요약"}
              {activeMenu === "simulator" && "과거 경제 뉴스를 통한 시장 반응 학습 및 AI 금융 사전"}
              {activeMenu === "learn" && "주식 기초, 기술적·기본적 분석, AI 기반 투자 학습"}
              {activeMenu === "backtest" && "과거 데이터를 활용한 전략 검증"}
              {activeMenu === "portfolio" && "나의 관심 종목 및 포트폴리오 관리"}
              {activeMenu === "settings" && "앱 설정 및 개인화"}
            </p>
          </header>

          {/* 메뉴별 컨텐츠 */}
          <div className="animate-fade-in">
            {activeMenu === "dashboard" && (
              <section className="mb-6 rounded-2xl bg-slate-900 border border-slate-800 p-5 flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
                <div>
                  <p className="text-white font-bold text-lg">처음이라면 여기부터 시작하세요.</p>
                  <p className="text-slate-400 text-sm mt-1">
                    예시 종목 카드(예: AAPL, MSFT, TSLA)가 있는 모의 투자 화면은 왼쪽 메뉴에서
                    <span className="text-slate-200 font-semibold"> &quot;모의 투자(포트폴리오)&quot;</span> 입니다.
                  </p>
                </div>
                <button
                  onClick={goToPortfolio}
                  className="self-start px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold transition-colors"
                >
                  모의 투자 화면으로 이동
                </button>
              </section>
            )}
            {activeMenu === "dashboard" && <DashboardSection />}
            {activeMenu === "simulator" && <NewsSimulatorSection />}
            {activeMenu === "learn" && <LearningCenter />}
            {activeMenu === "backtest" && <BacktestSection />}
            {activeMenu === "portfolio" && <PortfolioSection user={user} />}
            {activeMenu === "settings" && <SettingsSection user={user} />}
          </div>
        </div>
      </main>

      {/* 모바일 오버레이 */}
      {isMobileMenuOpen && (
        <div
          onClick={() => setIsMobileMenuOpen(false)}
          className="lg:hidden fixed inset-0 bg-black/50 z-30"
        />
      )}
    </div>
  );
}
