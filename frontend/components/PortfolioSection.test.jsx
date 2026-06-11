import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PortfolioSection from "./PortfolioSection";
import api from "../utils/api";

vi.mock("../utils/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe("PortfolioSection", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
  });

  it("로그인하지 않은 사용자는 안내 문구를 본다", () => {
    render(<PortfolioSection />);

    expect(screen.getByText("로그인 후 시뮬레이션 포트폴리오를 확인할 수 있습니다.")).toBeInTheDocument();
  });

  it("시뮬레이션이 없으면 시작 안내를 보여준다", async () => {
    api.post.mockResolvedValueOnce({
      data: {
        success: true,
        exists: false,
      },
    });

    render(<PortfolioSection user={{ email: "tester@example.com" }} />);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/simulation/state/get", {
        email: "tester@example.com",
      });
      expect(
        screen.getByText("아직 시작한 시뮬레이션이 없습니다. 주식 시뮬레이션 메뉴에서 계좌를 시작해 보세요.")
      ).toBeInTheDocument();
    });
  });

  it("저장된 시뮬레이션 포트폴리오와 거래 내역을 보여준다", async () => {
    api.post.mockResolvedValueOnce({
      data: {
        success: true,
        exists: true,
        state: {
          cash: 4800,
          simulation_started: true,
          holdings: {
            AAPL: { shares: 2, avgCost: 100, realizedPnl: 0 },
          },
          trades: [
            {
              id: "trade-1",
              type: "BUY",
              symbol: "AAPL",
              date: "2026-05-25",
              price: 100,
              shares: 2,
              realizedPnl: 0,
            },
          ],
        },
      },
    });
    api.get.mockResolvedValueOnce({
      data: {
        rows: [{ close: 110 }],
      },
    });

    render(<PortfolioSection user={{ email: "tester@example.com" }} />);

    await waitFor(() => {
      expect(screen.getByText("보유 종목")).toBeInTheDocument();
      expect(screen.getAllByText("AAPL").length).toBeGreaterThan(0);
      expect(screen.getByText("2주")).toBeInTheDocument();
      expect(screen.getByText("거래 내역")).toBeInTheDocument();
      expect(screen.getByText("매수")).toBeInTheDocument();
    });
  });
});
