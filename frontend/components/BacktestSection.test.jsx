import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import BacktestSection from "./BacktestSection";

vi.mock("../utils/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import api from "../utils/api";

describe("BacktestSection", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
  });

  it("백엔드 심볼 목록을 받아와 팝업 텍스트를 표시한다", async () => {
    api.get.mockResolvedValue({
      data: {
        items: [
          { symbol: "AAPL", name: "Apple Inc." },
          { symbol: "MSFT", name: "Microsoft Corp." },
        ],
      },
    });

    render(<BacktestSection />);
    const symbolBtn = await screen.findByTitle("AAPL · Apple Inc.");

    expect(symbolBtn).toBeInTheDocument();
    expect(symbolBtn).toHaveAttribute("title", "AAPL · Apple Inc.");
  });

  it("종목 옆 ? 버튼을 누르면 상세 정보 API가 호출되고 요약이 표시된다", async () => {
    api.get
      .mockResolvedValueOnce({
        data: {
          items: [
            { symbol: "AAPL", name: "Apple Inc." },
            { symbol: "MSFT", name: "Microsoft Corp." },
          ],
        },
      })
      .mockResolvedValueOnce({
        data: {
          success: true,
          item: {
            symbol: "AAPL",
            name: "Apple Inc.",
            exchange: "NMS",
            country: "USA",
            sector: "Technology",
            industry: "Consumer Electronics",
            summary: "Apple provides consumer tech products and services.",
            market_cap: 3000000000000,
            employees: 150000,
          },
        },
      });

    render(<BacktestSection />);

    const symbolBtn = await screen.findByTitle("AAPL · Apple Inc.");
    const infoBtn = screen.getAllByTitle("AAPL 정보 보기")[0];
    fireEvent.click(infoBtn);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith(
        "/api/backtest/symbol-info",
        expect.objectContaining({
          params: { symbol: "AAPL" },
        })
      );
    });

    expect(screen.getByText("Apple provides consumer tech products and services.")).toBeInTheDocument();
  });

  it("종목 버튼을 클릭하면 티커 입력창에 반영되고 백테스트 요청이 발생한다", async () => {
    api.get.mockResolvedValue({
      data: {
        items: [
          { symbol: "AAPL", name: "Apple Inc." },
          { symbol: "MSFT", name: "Microsoft Corp." },
        ],
      },
    });
    api.post.mockResolvedValue({
      data: {
        success: true,
        symbol: "AAPL",
        period: { from: "2024-01-01", to: "2024-01-10" },
        metrics: {
          trade_count: 0,
          wins: 0,
          win_rate: 0,
          remaining_shares: 0,
          final_equity: 100000,
          total_return: 0,
          total_return_percent: 0,
          max_drawdown_percent: 0,
        },
        composition: [{ symbol: "AAPL", weight: 1, allocated_cash: 100000 }],
        trades: [],
        equity_curve: [
          { date: "2024-01-01", 자산: 100000 },
        ],
      },
    });

    render(<BacktestSection />);

    const aaplButton = await screen.findByTitle("AAPL · Apple Inc.");
    const executeButton = screen.getByRole("button", { name: "백테스트 실행" });
    const symbolInput = screen.getByPlaceholderText("예: AAPL");

    fireEvent.click(aaplButton);
    fireEvent.click(executeButton);

    expect(symbolInput).toHaveValue("AAPL");

    await waitFor(() => {
      expect(api.post).toHaveBeenCalled();
    });

    expect(api.post).toHaveBeenCalledWith(
      "/api/backtest/run",
      expect.objectContaining({
        symbol: "AAPL",
      })
    );
  });

  it("템플릿 선택 시 positions로 백테스트 요청이 발생한다", async () => {
    api.get.mockResolvedValue({
      data: {
        items: [
          { symbol: "AAPL", name: "Apple Inc." },
          { symbol: "MSFT", name: "Microsoft Corp." },
        ],
      },
    });
    api.post.mockResolvedValue({
      data: {
        success: true,
        symbol: "SPY",
        period: { from: "2024-01-01", to: "2024-01-10" },
        metrics: {
          trade_count: 0,
          wins: 0,
          win_rate: 0,
          remaining_shares: 0,
          final_equity: 100000,
          total_return: 0,
          total_return_percent: 0,
          max_drawdown_percent: 0,
        },
        composition: [{ symbol: "SPY", weight: 0.4 }, { symbol: "TLT", weight: 0.3 }],
        trades: [],
        equity_curve: [
          { date: "2024-01-01", 자산: 100000 },
        ],
      },
    });

    render(<BacktestSection />);

    const allWeatherPreset = screen.getByRole("button", { name: /올웨더/ });
    fireEvent.click(allWeatherPreset);
    const executeButton = screen.getByRole("button", { name: "백테스트 실행" });
    fireEvent.click(executeButton);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalled();
    });

    expect(api.post).toHaveBeenCalledWith(
      "/api/backtest/run",
      expect.objectContaining({
        positions: [
          { symbol: "SPY", weight: 0.4 },
          { symbol: "TLT", weight: 0.3 },
          { symbol: "GLD", weight: 0.2 },
          { symbol: "BND", weight: 0.1 },
        ],
      })
    );
  });

  it("장바구니 모드에서 여러 종목을 넣고 비중을 지정하면 positions로 요청된다", async () => {
    api.get.mockResolvedValue({
      data: {
        items: [
          { symbol: "AAPL", name: "Apple Inc." },
          { symbol: "MSFT", name: "Microsoft Corp." },
        ],
      },
    });
    api.post.mockResolvedValue({
      data: {
        success: true,
        period: { from: "2024-01-01", to: "2024-01-10" },
        metrics: {
          trade_count: 0,
          wins: 0,
          win_rate: 0,
          remaining_shares: 0,
          final_equity: 100000,
          total_return: 0,
          total_return_percent: 0,
          max_drawdown_percent: 0,
        },
        symbol: "AAPL·MSFT",
        composition: [
          { symbol: "AAPL", weight: 0.5, allocated_cash: 50000 },
          { symbol: "MSFT", weight: 0.5, allocated_cash: 50000 },
        ],
        trades: [],
        equity_curve: [
          { date: "2024-01-01", 자산: 100000 },
        ],
      },
    });

    render(<BacktestSection />);

    const basketButton = screen.getByRole("button", { name: /장바구니/ });
    fireEvent.click(basketButton);

    const symbolInput1 = screen.getByLabelText("장바구니 티커 1");
    const weightInput1 = screen.getByLabelText("장바구니 비중 1");
    fireEvent.change(symbolInput1, { target: { value: "AAPL" } });
    fireEvent.change(weightInput1, { target: { value: "60" } });

    fireEvent.click(screen.getByRole("button", { name: "종목 추가" }));
    const symbolInput2 = screen.getByLabelText("장바구니 티커 2");
    const weightInput2 = screen.getByLabelText("장바구니 비중 2");
    fireEvent.change(symbolInput2, { target: { value: "MSFT" } });
    fireEvent.change(weightInput2, { target: { value: "40" } });

    const executeButton = screen.getByRole("button", { name: "백테스트 실행" });
    fireEvent.click(executeButton);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalled();
    });

    expect(api.post).toHaveBeenCalledWith(
      "/api/backtest/run",
      expect.objectContaining({
        positions: expect.arrayContaining([
          expect.objectContaining({ symbol: "AAPL" }),
          expect.objectContaining({ symbol: "MSFT" }),
        ]),
      })
    );

    const lastCall = api.post.mock.calls.at(-1);
    expect(lastCall[1].positions).toHaveLength(2);
  });
});
