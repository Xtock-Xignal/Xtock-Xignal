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
  Coins,
  LogOut // [추가] 로그아웃 아이콘
} from "lucide-react";

import LoginPage from "@/components/LoginPage";
import DashboardSection from "@/components/DashboardSection";
import RecentStatusSection from "@/components/RecentStatusSection";
import HistoricalImpactSection from "@/components/HistoricalImpactSection";
import LearningCenter from "@/components/LearningCenter";
import PortfolioSection from "@/components/PortfolioSection";
import SettingsSection from "@/components/SettingsSection";
import StockSimulationSection from "@/components/StockSimulationSection";

// API 유틸리티 import
import api from "../utils/api";

export default function Home() {
  // [수정] 로그인 상태 관리 (기본값 null)
  const [user, setUser] = useState(null); 
  
  const [activeMenu, setActiveMenu] = useState("dashboard");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [todayDate, setTodayDate] = useState("");

  // [추가] 검색 관련 상태 (handleSearch에서 사용됨)
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [quizRewardCash, setQuizRewardCash] = useState(0);
  const [attendanceRewardCash, setAttendanceRewardCash] = useState(0);
  const [rewardHydrated, setRewardHydrated] = useState(false);
  const totalRewardCash = quizRewardCash + attendanceRewardCash;

  const handleQuizCorrect = () => {
    setQuizRewardCash((prev) => prev + 50);
  };

  useEffect(() => {
    setTodayDate(new Date().toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "long",
    }));
  }, []);

  useEffect(() => {
    if (!user?.username) {
      setQuizRewardCash(0);
      setAttendanceRewardCash(0);
      setRewardHydrated(false);
      return;
    }

    const quizRewardKey = `quiz_reward_total_${user.username}`;
    const attendanceRewardKey = `attendance_reward_total_${user.username}`;
    const storedQuizReward = Number(localStorage.getItem(quizRewardKey) ?? "0");
    const storedAttendanceReward = Number(localStorage.getItem(attendanceRewardKey) ?? "0");
    setQuizRewardCash(Number.isFinite(storedQuizReward) ? storedQuizReward : 0);
    setAttendanceRewardCash(Number.isFinite(storedAttendanceReward) ? storedAttendanceReward : 0);
    setRewardHydrated(true);
  }, [user]);

  useEffect(() => {
    if (!user?.username || !rewardHydrated) return;
    const quizRewardKey = `quiz_reward_total_${user.username}`;
    localStorage.setItem(quizRewardKey, String(quizRewardCash));
  }, [user, quizRewardCash, rewardHydrated]);

  useEffect(() => {
    if (!user?.username || !rewardHydrated) return;
    const attendanceRewardKey = `attendance_reward_total_${user.username}`;
    localStorage.setItem(attendanceRewardKey, String(attendanceRewardCash));
  }, [user, attendanceRewardCash, rewardHydrated]);

  useEffect(() => {
    if (!user?.username || !rewardHydrated) return;
    const todayKey = new Date().toISOString().slice(0, 10);
    const attendanceDateKey = `attendance_last_date_${user.username}`;
    const hasChecked = localStorage.getItem(attendanceDateKey) === todayKey;
    if (hasChecked) {
      alert("오늘은 이미 출석 보상이 지급되었습니다.");
      return;
    }

    localStorage.setItem(attendanceDateKey, todayKey);
    setAttendanceRewardCash((prev) => prev + 30);
    alert("출석 체크 완료! 보상으로 $30가 지급되었습니다.");
  }, [user, rewardHydrated]);

  // [추가] 로그인이 안 되어 있으면 로그인 페이지를 먼저 보여줌
  if (!user) {
    return <LoginPage onLogin={(userData) => setUser(userData)} />;
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
    { id: "recent", icon: Activity, label: "최근 기업 근황" },
    { id: "historical", icon: History, label: "과거 영향 분석" },
    { id: "learn", icon: BookOpen, label: "학습 센터" },
    { id: "portfolio", icon: User, label: "내 포트폴리오" },
    { id: "simulation", icon: Coins, label: "주식 시뮬레이션" },
    { id: "settings", icon: Settings, label: "설정" },
  ];

  return (
    <div className="flex h-[100dvh] min-h-0 bg-slate-950 text-slate-100">

      {/* 모바일 메뉴 버튼 */}
      <button
        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-slate-800 rounded-lg border border-slate-700"
      >
        {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* 사이드바 */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-40 w-64 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col min-h-0 overflow-y-auto transition-transform duration-300 ${
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
              onClick={() => setUser(null)} // 유저 상태 초기화 -> 로그인 페이지로 이동
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-slate-400 hover:bg-red-900/20 hover:text-red-400 transition-colors"
            >
              <LogOut size={20} />
              <span className="font-medium">로그아웃</span>
            </button>
          </div>
        </nav>
      </aside>

      {/* 메인 컨텐츠 */}
      <main className="flex-1 min-h-0 min-w-0 overflow-y-auto custom-scrollbar">
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
                {activeMenu === "recent" && "최근 기업 근황"}
                {activeMenu === "historical" && "과거 영향 분석"}
                {activeMenu === "learn" && "학습 센터"}
                {activeMenu === "portfolio" && "내 포트폴리오"}
                {activeMenu === "simulation" && "주식 시뮬레이션"}
                {activeMenu === "settings" && "설정"}
              </h1>
              <p className="text-sm text-slate-400 font-medium">
                {todayDate}
              </p>
            </div>
            <p className="text-sm md:text-base text-slate-400">
              {activeMenu === "dashboard" && "오늘의 시장 동향 및 예측 요약"}
              {activeMenu === "recent" && "관심 기업의 실시간 공식 트윗과 주가 흐름 모니터링"}
              {activeMenu === "historical" && "과거 주가에 영향을 미쳤던 결정적 트윗 학습"}
              {activeMenu === "learn" && "주식 기초, 기술적·기본적 분석, AI 기반 투자 학습"}
              {activeMenu === "portfolio" && "시뮬레이션 보유 종목 및 거래 내역"}
              {activeMenu === "simulation" && "가상 현금으로 매수/매도 경험 시뮬레이션"}
              {activeMenu === "settings"}
            </p>
          </header>

          {/* 메뉴별 컨텐츠 */}
          <div className="animate-fade-in">
            {activeMenu === "dashboard" && <DashboardSection />}
            {activeMenu === "recent" && <RecentStatusSection />}
            {activeMenu === "historical" && <HistoricalImpactSection />}
            {activeMenu === "learn" && <LearningCenter onQuizCorrect={handleQuizCorrect} />}
            {activeMenu === "portfolio" && (
              <PortfolioSection user={user} isActive={activeMenu === "portfolio"} />
            )}
            {activeMenu === "simulation" && (
              <StockSimulationSection rewardCash={totalRewardCash} user={user} />
            )}
            {activeMenu === "settings" && (
              <SettingsSection
                user={user}
                onUserUpdate={(updated) => setUser(updated)}
                onLogout={() => setUser(null)}
              />
            )}
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