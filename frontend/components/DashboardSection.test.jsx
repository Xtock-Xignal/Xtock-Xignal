import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardSection from "./DashboardSection";

vi.mock("../utils/api", () => ({
  default: { get: vi.fn() },
}));

vi.mock("../data/sp500_list", () => ({
  SP500_LIST: [
    { symbol: "AAPL", name: "Apple Inc." },
    { symbol: "MSFT", name: "Microsoft" },
    { symbol: "NVDA", name: "NVIDIA" },
  ],
}));

import api from "../utils/api";

const MOCK_SUMMARY = {
  indices: [
    { symbol: "^GSPC",    name: "S&P 500",     price: 5500.25,  change: 12.5,  changePercent: 0.23 },
    { symbol: "^IXIC",    name: "NASDAQ",       price: 17800.1,  change: -45.2, changePercent: -0.25 },
    { symbol: "^DJI",     name: "다우존스",      price: 39200.5,  change: 80.1,  changePercent: 0.2 },
    { symbol: "^VIX",     name: "VIX 공포지수",  price: 17.5,     change: -1.2,  changePercent: -6.4 },
    { symbol: "^TNX",     name: "10년 국채금리",  price: 4.32,     change: 0.03,  changePercent: 0.7 },
    { symbol: "DX-Y.NYB", name: "달러 인덱스",   price: 104.1,    change: -0.3,  changePercent: -0.29 },
  ],
  topStock: {
    symbol: "AAPL",
    name: "Market Leader",
    price: 220.5,
    change: 3.2,
    changePercent: 1.47,
    marketCap: 3.4e12,
    chartData: [
      { date: "2026-05-01", price: 210 },
      { date: "2026-05-02", price: 215 },
      { date: "2026-05-03", price: 220.5 },
    ],
  },
};

const MOCK_CHART_ROWS = [
  { date: "2026-05-01", open: 200, high: 205, low: 198, close: 202.5, volume: 50000000 },
  { date: "2026-05-02", open: 202.5, high: 210, low: 201, close: 208.0, volume: 55000000 },
];

describe("DashboardSection", () => {
  beforeEach(() => {
    api.get.mockReset();
  });

  it("로딩 중 메시지를 표시한다", () => {
    api.get.mockReturnValue(new Promise(() => {}));
    render(<DashboardSection />);
    expect(screen.getByText(/시장 데이터를 불러오는 중/)).toBeInTheDocument();
  });

  it("시총 1위 기업 주가 정보를 표시한다", async () => {
    api.get.mockResolvedValueOnce({ data: MOCK_SUMMARY });
    render(<DashboardSection />);

    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    expect(screen.getByText("시총 1위")).toBeInTheDocument();
    expect(screen.getByText("$3.40T")).toBeInTheDocument();
  });

  it("VIX 지수와 공포 수준을 표시한다", async () => {
    api.get.mockResolvedValueOnce({ data: MOCK_SUMMARY });
    render(<DashboardSection />);

    await waitFor(() => {
      expect(screen.getByText("VIX 공포지수")).toBeInTheDocument();
    });
    expect(screen.getByText("17.50")).toBeInTheDocument();
    expect(screen.getByText("안정")).toBeInTheDocument();
  });

  it("주요 시장 지표를 표시한다", async () => {
    api.get.mockResolvedValueOnce({ data: MOCK_SUMMARY });
    render(<DashboardSection />);

    await waitFor(() => {
      expect(screen.getByText("S&P 500")).toBeInTheDocument();
    });
    expect(screen.getByText("NASDAQ")).toBeInTheDocument();
    expect(screen.getByText("다우존스")).toBeInTheDocument();
    expect(screen.getByText("10년 국채금리")).toBeInTheDocument();
  });

  it("S&P 500 종목 목록을 표시한다", async () => {
    api.get.mockResolvedValueOnce({ data: MOCK_SUMMARY });
    render(<DashboardSection />);

    await waitFor(() => {
      expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    });
    expect(screen.getByText("Microsoft")).toBeInTheDocument();
    expect(screen.getByText("NVIDIA")).toBeInTheDocument();
  });

  it("종목 클릭 시 차트 데이터를 요청하고 표시한다", async () => {
    api.get
      .mockResolvedValueOnce({ data: MOCK_SUMMARY })
      .mockResolvedValueOnce({ data: { rows: MOCK_CHART_ROWS } });

    render(<DashboardSection />);

    await waitFor(() => {
      expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Apple Inc."));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith(
        "/api/chart/history/AAPL",
        expect.objectContaining({ params: { period: "1mo", interval: "1d" } })
      );
    });

    await waitFor(() => {
      expect(screen.getByText("$208.00")).toBeInTheDocument();
    });
  });

  it("검색어로 종목을 필터링한다", async () => {
    api.get.mockResolvedValueOnce({ data: MOCK_SUMMARY });
    render(<DashboardSection />);

    await waitFor(() => {
      expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("티커 또는 기업명 검색..."), {
      target: { value: "MSFT" },
    });

    expect(screen.getByText("Microsoft")).toBeInTheDocument();
    expect(screen.queryByText("Apple Inc.")).not.toBeInTheDocument();
  });

  it("API 실패 시 빈 화면을 렌더링한다", async () => {
    api.get.mockRejectedValueOnce(new Error("network error"));
    render(<DashboardSection />);

    await waitFor(() => {
      expect(screen.queryByText(/시장 데이터를 불러오는 중/)).not.toBeInTheDocument();
    });
    expect(screen.queryByText("시총 1위")).not.toBeInTheDocument();
  });
});
