"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  BookOpen,
  Coins,
  LayoutDashboard,
  LogOut,
  Menu,
  Newspaper,
  Settings,
  User,
  X,
} from "lucide-react";

import BacktestSection from "@/components/BacktestSection";
import DashboardSection from "@/components/DashboardSection";
import LearningCenter from "@/components/LearningCenter";
import LoginPage from "@/components/LoginPage";
import PortfolioSection from "@/components/PortfolioSection";
import SettingsSection from "@/components/SettingsSection";
import StockSimulationSection from "@/components/StockSimulationSection";
import NewsSimulatorSection from "@/features/simulator/NewsSimulatorSection";
import api from "../utils/api";

const MENU_ITEMS = [
  { id: "dashboard", icon: LayoutDashboard, label: "시장 현황" },
  { id: "learn", icon: BookOpen, label: "학습 센터" },
  { id: "simulator", icon: Newspaper, label: "뉴스 시뮬레이터" },
  { id: "simulation", icon: Coins, label: "주식 시뮬레이션" },
  { id: "portfolio", icon: User, label: "포트폴리오" },
  { id: "backtest", icon: BarChart3, label: "백테스팅" },
  { id: "settings", icon: Settings, label: "설정" },
];

const MENU_TITLES = {
  dashboard: "시장 현황",
  learn: "학습 센터",
  simulator: "뉴스 시뮬레이터",
  simulation: "주식 시뮬레이션",
  portfolio: "포트폴리오",
  backtest: "백테스팅",
  settings: "설정",
};

const MENU_DESCRIPTIONS = {
  dashboard: "오늘의 시장 흐름과 주요 뉴스를 한눈에 확인합니다.",
  learn: "주식 기초 개념을 학습하고 퀴즈 보상으로 시뮬레이션 자금을 늘립니다.",
  simulator: "최신 금융 뉴스를 읽고, 번역·요약·용어 설명으로 문맥을 이해합니다.",
  simulation: "가상 현금으로 매수·매도 흐름을 연습합니다.",
  portfolio: "시뮬레이션 보유 종목과 최근 거래 내역을 확인합니다.",
  backtest: "과거에 특정 주식을 샀다면 지금 얼마가 되었을지 시뮬레이션합니다.",
  settings: "프로필, 거래 PIN, 시뮬레이션 계좌 상태를 관리합니다.",
};

export default function Home() {
  const [user, setUser] = useState(null);
  const [activeMenu, setActiveMenu] = useState("dashboard");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [todayDate, setTodayDate] = useState("");
  const [simulationInitialTicker, setSimulationInitialTicker] = useState(null);

  const [quizRewardCash, setQuizRewardCash] = useState(0);
  const [attendanceRewardCash, setAttendanceRewardCash] = useState(0);
  const [rewardHydrated, setRewardHydrated] = useState(false);
  const totalRewardCash = quizRewardCash + attendanceRewardCash;

  const applyRewardState = useCallback((rewards = {}) => {
    setQuizRewardCash(Number(rewards.quiz_reward_cash) || 0);
    setAttendanceRewardCash(Number(rewards.attendance_reward_cash) || 0);
  }, []);

  const handleQuizCorrect = async () => {
    const email = user?.email?.trim();
    if (!email) {
      setQuizRewardCash((prev) => prev + 50);
      return;
    }

    try {
      const res = await api.post("/api/user/rewards/quiz", { email, amount: 50 });
      if (res?.data?.success) {
        applyRewardState(res.data.rewards);
      } else {
        setQuizRewardCash((prev) => prev + 50);
      }
    } catch (error) {
      console.error("Failed to save quiz reward", error);
      setQuizRewardCash((prev) => prev + 50);
    }
  };

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setTodayDate(
        new Date().toLocaleDateString("ko-KR", {
          year: "numeric",
          month: "long",
          day: "numeric",
          weekday: "long",
        })
      );
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      const email = user?.email?.trim();
      if (!email) {
        setQuizRewardCash(0);
        setAttendanceRewardCash(0);
        setRewardHydrated(false);
        return;
      }

      (async () => {
        try {
          const res = await api.post("/api/user/rewards/get", { email });
          if (res?.data?.success) {
            applyRewardState(res.data.rewards);
          } else {
            setQuizRewardCash(0);
            setAttendanceRewardCash(0);
          }
        } catch (error) {
          console.error("Failed to load rewards", error);
          setQuizRewardCash(0);
          setAttendanceRewardCash(0);
        } finally {
          setRewardHydrated(true);
        }
      })();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [user, applyRewardState]);

  useEffect(() => {
    const email = user?.email?.trim();
    if (!email || !rewardHydrated) return;
    const todayKey = new Date().toISOString().slice(0, 10);

    (async () => {
      try {
        const res = await api.post("/api/user/attendance/check", {
          email,
          date: todayKey,
          amount: 30,
        });
        if (res?.data?.success) {
          applyRewardState(res.data.rewards);
          if (res.data.checked) {
            alert("출석 체크 완료! 보상으로 $30가 지급되었습니다.");
          }
        }
      } catch (error) {
        console.error("Failed to check attendance", error);
      }
    })();
  }, [user, rewardHydrated, applyRewardState]);

  if (!user) {
    return <LoginPage onLogin={(userData) => {
      setUser(userData);
      // 로그인 성공 시 퀴즈 DB 생성을 백그라운드로 트리거 (결과 무시)
      api.post("/api/quiz/generate").catch(() => {});
    }} />;
  }

  const handleLogout = () => {
    setUser(null);
    setRewardHydrated(false);
    setQuizRewardCash(0);
    setAttendanceRewardCash(0);
  };

  const handleNewsTickerClick = (ticker) => {
    setSimulationInitialTicker(ticker);
    setActiveMenu("simulation");
    setIsMobileMenuOpen(false);
  };

  return (
    <div className="flex h-[100dvh] min-h-0 bg-slate-950 text-slate-100">
      <button
        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        className="fixed left-4 top-4 z-50 rounded-lg border border-slate-700 bg-slate-800 p-2 lg:hidden"
        aria-label="메뉴 열기"
      >
        {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex min-h-0 w-64 shrink-0 flex-col overflow-y-auto border-r border-slate-800 bg-slate-900 transition-transform duration-300 lg:static ${
          isMobileMenuOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        <div className="border-t border-slate-800 px-4 pb-4 pt-6">
          <div className="flex items-center gap-3 rounded-lg bg-slate-800 px-4 py-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 text-white">
              <span className="text-sm font-bold">{user.username.charAt(0).toUpperCase()}</span>
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{user.username}</p>
              <p className="truncate text-xs text-slate-400">{user.email}</p>
            </div>
          </div>
        </div>

        <nav className="flex flex-1 flex-col justify-between p-4">
          <ul className="space-y-2">
            {MENU_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.id}>
                  <button
                    onClick={() => {
                      setActiveMenu(item.id);
                      setIsMobileMenuOpen(false);
                    }}
                    className={`flex w-full items-center gap-3 rounded-lg px-4 py-3 transition-colors ${
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

          <div className="mt-4 border-t border-slate-800 pt-4">
            <button
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-lg px-4 py-3 text-slate-400 transition-colors hover:bg-red-900/20 hover:text-red-400"
            >
              <LogOut size={20} />
              <span className="font-medium">로그아웃</span>
            </button>
          </div>
        </nav>
      </aside>

      <main className="min-h-0 min-w-0 flex-1 overflow-y-auto custom-scrollbar">
        <div className="mt-6 w-full text-center">
          <h1 className="inline-flex select-none items-center gap-2 font-extrabold">
            <span className="bg-gradient-to-br from-blue-500 to-purple-600 bg-clip-text text-8xl leading-none text-transparent">
              X
            </span>
            <div className="flex flex-col text-left leading-tight">
              <span className="text-4xl text-white">tock</span>
              <span className="text-4xl text-slate-500">ignal</span>
            </div>
          </h1>
        </div>

        <div className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
          <header className="mb-8">
            <div className="mb-2 flex items-center justify-between gap-4">
              <h1 className="text-3xl font-extrabold text-white md:text-4xl">
                {MENU_TITLES[activeMenu]}
              </h1>
              <p className="text-sm font-medium text-slate-400">{todayDate}</p>
            </div>
            <p className="text-sm text-slate-400 md:text-base">
              {MENU_DESCRIPTIONS[activeMenu]}
            </p>
          </header>

          <div className="animate-fade-in">
            {activeMenu === "dashboard" && <DashboardSection />}
            {activeMenu === "learn" && <LearningCenter onQuizCorrect={handleQuizCorrect} />}
            {activeMenu === "simulator" && (
              <NewsSimulatorSection onTickerClick={handleNewsTickerClick} />
            )}
            {activeMenu === "simulation" && (
              <StockSimulationSection
                rewardCash={totalRewardCash}
                user={user}
                initialTicker={simulationInitialTicker}
              />
            )}
            {activeMenu === "portfolio" && (
              <PortfolioSection user={user} isActive={activeMenu === "portfolio"} />
            )}
            {activeMenu === "backtest" && <BacktestSection />}
            {activeMenu === "settings" && (
              <SettingsSection
                user={user}
                onUserUpdate={(updated) => setUser(updated)}
                onLogout={handleLogout}
              />
            )}
          </div>
        </div>
      </main>

      {isMobileMenuOpen && (
        <div
          onClick={() => setIsMobileMenuOpen(false)}
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
        />
      )}
    </div>
  );
}
