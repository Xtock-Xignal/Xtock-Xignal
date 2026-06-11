import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../app/page.jsx";
import api from "../utils/api";

vi.mock("../utils/api", () => ({
  default: {
    post: vi.fn(),
  },
}));

vi.mock("@/components/LoginPage", () => ({
  default: ({ onLogin }) => (
    <button onClick={() => onLogin({ username: "tester", email: "test@example.com" })}>
      LOGIN_SCREEN
    </button>
  ),
}));

vi.mock("@/components/DashboardSection", () => ({
  default: () => <div>DashboardSection</div>,
}));

vi.mock("@/components/SearchSection", () => ({
  default: () => <div>SearchSection</div>,
}));

vi.mock("@/features/simulator/NewsSimulatorSection", () => ({
  default: () => <div>NewsSimulatorSection</div>,
}));

vi.mock("@/components/LearningCenter", () => ({
  default: ({ onQuizCorrect }) => (
    <button onClick={() => onQuizCorrect()}>LearningCenter</button>
  ),
}));

vi.mock("@/components/PortfolioSection", () => ({
  default: () => <div>PortfolioSection</div>,
}));

vi.mock("@/components/StockSimulationSection", () => ({
  default: ({ rewardCash }) => <div>StockSimulationSection reward:{rewardCash}</div>,
}));

vi.mock("@/components/BacktestSection", () => ({
  default: () => <div>BacktestSection</div>,
}));

vi.mock("@/components/SettingsSection", () => ({
  default: () => <div>SettingsSection</div>,
}));

describe("Home (page)", () => {
  const loginAndWaitForDashboard = async () => {
    fireEvent.click(screen.getByText("LOGIN_SCREEN"));

    await screen.findByText("DashboardSection");
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/user/attendance/check", {
        email: "test@example.com",
        date: expect.any(String),
        amount: 30,
      });
    });
  };

  beforeEach(() => {
    localStorage.clear();
    api.post.mockReset();
    api.post.mockImplementation((url) => {
      if (url === "/api/user/rewards/get") {
        return Promise.resolve({
          data: {
            success: true,
            rewards: {
              quiz_reward_cash: 0,
              attendance_reward_cash: 0,
              attendance_last_date: null,
            },
          },
        });
      }
      if (url === "/api/user/attendance/check") {
        return Promise.resolve({
          data: {
            success: true,
            checked: true,
            rewards: {
              quiz_reward_cash: 0,
              attendance_reward_cash: 30,
              attendance_last_date: "2026-06-01",
            },
          },
        });
      }
      if (url === "/api/user/rewards/quiz") {
        return Promise.resolve({
          data: {
            success: true,
            rewards: {
              quiz_reward_cash: 50,
              attendance_reward_cash: 30,
              attendance_last_date: "2026-06-01",
            },
          },
        });
      }
      return Promise.resolve({ data: { success: true } });
    });
    vi.spyOn(window, "alert").mockImplementation(() => {});
  });

  it("shows the login screen before login", () => {
    render(<Home />);

    expect(screen.getByText("LOGIN_SCREEN")).toBeInTheDocument();
  });

  it("shows the dashboard first after login", async () => {
    render(<Home />);

    await loginAndWaitForDashboard();

    expect(screen.getByText("DashboardSection")).toBeInTheDocument();
    expect(screen.queryByText("SearchSection")).not.toBeInTheDocument();
    expect(screen.queryByText("NewsSimulatorSection")).not.toBeInTheDocument();
  });

  it("switches between stock analysis and news simulation tabs", async () => {
    render(<Home />);

    await loginAndWaitForDashboard();
    fireEvent.click(await screen.findByRole("button", { name: /종목 분석/ }));
    expect(screen.getByText("SearchSection")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /뉴스 시뮬레이터/ }));
    expect(screen.getByText("NewsSimulatorSection")).toBeInTheDocument();
  });

  it("opens the stock simulation tab", async () => {
    render(<Home />);

    await loginAndWaitForDashboard();
    fireEvent.click(await screen.findByRole("button", { name: /주식 시뮬레이션/ }));

    expect(screen.getByText(/StockSimulationSection/)).toBeInTheDocument();
  });

  it("opens the backtest tab", async () => {
    render(<Home />);

    await loginAndWaitForDashboard();
    fireEvent.click(await screen.findByRole("button", { name: /백테스팅/ }));

    expect(screen.getByText("BacktestSection")).toBeInTheDocument();
  });

  it("loads attendance and quiz rewards from the backend for simulation cash", async () => {
    render(<Home />);

    await loginAndWaitForDashboard();
    fireEvent.click(await screen.findByText("학습 센터"));
    fireEvent.click(await screen.findByRole("button", { name: "LearningCenter" }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/user/rewards/quiz", {
        email: "test@example.com",
        amount: 50,
      });
    });

    fireEvent.click(screen.getByRole("button", { name: /주식 시뮬레이션/ }));

    await waitFor(() => {
      expect(screen.getByText("StockSimulationSection reward:80")).toBeInTheDocument();
    });
  });
});
