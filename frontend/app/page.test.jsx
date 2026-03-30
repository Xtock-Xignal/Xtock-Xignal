import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { waitFor } from "@testing-library/react";

import Home from "./page";

const AUTH_STORAGE_KEY = "xtock-auth-user-v1";

vi.mock("@/features/auth/LoginPage", () => ({
  default: () => <div>LOGIN_SCREEN</div>,
}));

vi.mock("@/features/dashboard/DashboardSection", () => ({
  default: () => <div>DashboardSection</div>,
}));

vi.mock("@/features/recent/RecentStatusSection", () => ({
  default: () => <div>RecentStatusSection</div>,
}));

vi.mock("@/features/historical/HistoricalImpactSection", () => ({
  default: () => <div>HistoricalImpactSection</div>,
}));

vi.mock("@/features/learn/LearningCenter", () => ({
  default: () => <div>LearningCenter</div>,
}));

vi.mock("@/features/backtest/BacktestSection", () => ({
  default: () => <div>BacktestSection</div>,
}));

vi.mock("@/features/portfolio/PortfolioSection", () => ({
  default: () => <div>PortfolioSection</div>,
}));

vi.mock("@/features/settings/SettingsSection", () => ({
  default: () => <div>SettingsSection</div>,
}));

describe("Home (page)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("로그인 정보가 없으면 로그인 화면을 보여준다", () => {
    render(<Home />);

    return waitFor(() => {
      expect(screen.getByText("LOGIN_SCREEN")).toBeInTheDocument();
    });
  });

  it("유효한 인증 정보가 있으면 기본 메뉴가 보인다", async () => {
    const validAuth = {
      user: { username: "tester", email: "test@example.com" },
      expiresAt: Date.now() + 1000 * 60 * 60,
    };
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(validAuth));

    render(<Home />);

    await waitFor(() => {
      expect(screen.queryByText("LOGIN_SCREEN")).not.toBeInTheDocument();
      expect(screen.getByText("대시보드")).toBeInTheDocument();
      expect(screen.getByText("DashboardSection")).toBeInTheDocument();
    });
  });
});
