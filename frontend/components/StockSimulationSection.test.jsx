import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import StockSimulationSection from "./StockSimulationSection";
import api from "../utils/api";

vi.mock("../utils/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

class FakeWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.close = vi.fn();
    FakeWebSocket.instances.push(this);
  }
}

describe("StockSimulationSection", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    global.WebSocket = FakeWebSocket;
    api.get.mockReset();
    api.post.mockReset();
  });

  afterEach(() => {
    delete global.WebSocket;
  });

  it("renders the prototype stock simulation screen", () => {
    render(<StockSimulationSection />);

    expect(screen.getByRole("heading", { name: "주식 시뮬레이션" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "시뮬레이션 시작" })).toBeInTheDocument();
  });

  it("starts the demo account simulation locally", async () => {
    render(<StockSimulationSection />);

    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션 시작" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "계좌 초기화" })).toBeInTheDocument();
      expect(screen.getAllByText("$5,000").length).toBeGreaterThan(0);
    });
  });

  it("loads chart history without applying realtime ticks to period results", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        rows: [
          {
            date: "2026-05-24",
            open: 90,
            high: 91,
            low: 89,
            close: 90,
            volume: 900,
          },
          {
            date: "2026-05-25",
            open: 100,
            high: 101,
            low: 99,
            close: 100,
            volume: 1000,
          },
        ],
      },
    });

    render(<StockSimulationSection />);

    fireEvent.click(screen.getByRole("button", { name: "과거 차트" }));
    fireEvent.click(screen.getByRole("button", { name: "TSLA" }));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/chart/history/TSLA", {
        params: expect.objectContaining({
          interval: "1d",
        }),
      });
      expect(FakeWebSocket.instances).toHaveLength(0);
    });

    expect(screen.queryByText("$110")).not.toBeInTheDocument();
    expect(screen.getAllByText("과거").length).toBeGreaterThan(0);
  });

  it("keeps realtime chart length fixed while applying websocket ticks", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        rows: [
          {
            date: "2026-05-23",
            open: 85,
            high: 91,
            low: 84,
            close: 90,
            volume: 900,
          },
          {
            date: "2026-05-24",
            open: 90,
            high: 96,
            low: 89,
            close: 95,
            volume: 950,
          },
          {
            date: "2026-05-25",
            open: 95,
            high: 101,
            low: 94,
            close: 100,
            volume: 1000,
          },
        ],
      },
    });

    render(<StockSimulationSection />);

    fireEvent.change(screen.getByPlaceholderText("예: TSLA, AAPL"), {
      target: { value: "TSLA" },
    });
    fireEvent.click(screen.getByRole("button", { name: "실시간" }));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/chart/history/TSLA", {
        params: expect.objectContaining({
          period: "100d",
          interval: "1d",
        }),
      });
      expect(FakeWebSocket.instances).toHaveLength(1);
      expect(screen.getByText("실시간 반영")).toBeInTheDocument();
      expect(screen.getByText("데이터: 3개")).toBeInTheDocument();
    });

    act(() => {
      FakeWebSocket.instances[0].onmessage({
        data: JSON.stringify({
          type: "tick",
          symbol: "TSLA",
          price: 100,
          time: "2026-05-25T15:29:30Z",
          row: {
            date: "2026-05-25",
            time: "2026-05-25T15:29:30Z",
            open: 100,
            high: 100,
            low: 100,
            close: 100,
            volume: 0,
          },
        }),
      });
    });

    expect(screen.getByText("데이터: 3개")).toBeInTheDocument();

    act(() => {
      FakeWebSocket.instances[0].onmessage({
        data: JSON.stringify({
          type: "tick",
          symbol: "TSLA",
          price: 110,
          time: "1780402337",
        }),
      });
    });

    await waitFor(() => {
      expect(screen.getAllByText("$110").length).toBeGreaterThan(0);
      expect(screen.getByText("데이터: 3개")).toBeInTheDocument();
      expect(screen.getByText(/선택 시간/)).toBeInTheDocument();
      expect(screen.getByText("2026-06-02 12:12:17")).toBeInTheDocument();
      expect(screen.queryByText(/1780402337/)).not.toBeInTheDocument();
      expect(screen.getByText("실시간 거래량: 제공 안 됨")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "캔들" }));

    act(() => {
      FakeWebSocket.instances[0].onmessage({
        data: JSON.stringify({
          type: "tick",
          symbol: "TSLA",
          price: 120,
          time: "2026-05-27T15:31:00Z",
          row: {
            date: "2026-05-27",
            time: "2026-05-27T15:31:00Z",
            open: 120,
            high: 120,
            low: 120,
            close: 120,
            volume: 0,
          },
        }),
      });
    });

    await waitFor(() => {
      expect(screen.getAllByText("$120").length).toBeGreaterThan(0);
      expect(screen.getByText("데이터: 3개")).toBeInTheDocument();
      expect(screen.getByText("2026-05-27 15:31:00")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "이평선" }));

    act(() => {
      FakeWebSocket.instances[0].onmessage({
        data: JSON.stringify({
          type: "tick",
          symbol: "TSLA",
          price: 130,
          time: "2026-05-28T15:32:00Z",
          row: {
            date: "2026-05-28",
            time: "2026-05-28T15:32:00Z",
            open: 130,
            high: 130,
            low: 130,
            close: 130,
            volume: 0,
          },
        }),
      });
    });

    await waitFor(() => {
      expect(screen.getAllByText("$130").length).toBeGreaterThan(0);
      expect(screen.getByText("데이터: 3개")).toBeInTheDocument();
      expect(screen.getByText("2026-05-28 15:32:00")).toBeInTheDocument();
    });
  });

  it("shows the loaded current price for simulation orders", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        rows: [
          {
            date: "2026-05-25",
            open: 100,
            high: 101,
            low: 99,
            close: 100,
            volume: 1000,
          },
        ],
      },
    });

    render(<StockSimulationSection />);

    fireEvent.click(screen.getByRole("button", { name: "TSLA" }));
    await waitFor(() => expect(screen.getAllByText("$100").length).toBeGreaterThan(0));
    expect(screen.getByText((content) => content.includes("현재가:"))).toBeInTheDocument();
  });
});
