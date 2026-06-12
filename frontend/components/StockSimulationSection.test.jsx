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

const clickFirstButton = (name) => {
  fireEvent.click(screen.getAllByRole("button", { name })[0]);
};

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

  it("loads historical chart data without applying realtime ticks", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        rows: [
          { date: "2026-05-24", open: 90, high: 91, low: 89, close: 90, volume: 900 },
          { date: "2026-05-25", open: 100, high: 101, low: 99, close: 100, volume: 1000 },
        ],
      },
    });

    render(<StockSimulationSection />);

    clickFirstButton("historical chart");
    fireEvent.click(screen.getByRole("button", { name: "TSLA" }));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/chart/history/TSLA", {
        params: expect.objectContaining({ interval: "1d" }),
      });
      expect(FakeWebSocket.instances).toHaveLength(0);
      expect(screen.getByRole("button", { name: "ma chart mode" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "candle chart mode" })).toBeInTheDocument();
    });

    expect(screen.queryByText("$110")).not.toBeInTheDocument();
  });

  it("keeps realtime history while hiding chart mode buttons in realtime", async () => {
    render(<StockSimulationSection />);

    fireEvent.change(screen.getByPlaceholderText(/TSLA/), {
      target: { value: "TSLA" },
    });
    clickFirstButton("realtime chart");

    await waitFor(() => {
      expect(api.get).not.toHaveBeenCalled();
      expect(FakeWebSocket.instances).toHaveLength(1);
      expect(screen.getByTestId("simulation-chart-data-count")).toHaveTextContent("0/100");
      expect(screen.queryByRole("button", { name: "ma chart mode" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "candle chart mode" })).not.toBeInTheDocument();
    });

    act(() => {
      FakeWebSocket.instances[0].onmessage({
        data: JSON.stringify({
          type: "tick",
          symbol: "TSLA",
          price: 100,
          time: "2026-05-25T15:29:30Z",
          row: { date: "2026-05-25", time: "2026-05-25T15:29:30Z", open: 100, high: 100, low: 100, close: 100, volume: 0 },
        }),
      });
    });

    expect(screen.getByTestId("simulation-chart-data-count")).toHaveTextContent("1/100");

    act(() => {
      FakeWebSocket.instances[0].onmessage({
        data: JSON.stringify({ type: "tick", symbol: "TSLA", price: 110, time: "1780402337" }),
      });
    });

    await waitFor(() => {
      expect(screen.getAllByText("$110").length).toBeGreaterThan(0);
      expect(screen.getByTestId("simulation-chart-data-count")).toHaveTextContent("2/100");
      expect(screen.getByText("2026-06-02 12:12:17")).toBeInTheDocument();
      expect(screen.queryByText(/1780402337/)).not.toBeInTheDocument();
    });

    api.get.mockResolvedValueOnce({
      data: {
        rows: [{ date: "2026-05-24", open: 80, high: 81, low: 79, close: 80, volume: 800 }],
      },
    });

    clickFirstButton("historical chart");

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/chart/history/TSLA", {
        params: expect.objectContaining({ interval: "1d" }),
      });
      expect(screen.getByTestId("simulation-chart-data-count")).toHaveTextContent("1");
      expect(screen.getByRole("button", { name: "ma chart mode" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "candle chart mode" })).toBeInTheDocument();
    });

    clickFirstButton("candle chart mode");
    clickFirstButton("realtime chart");

    await waitFor(() => {
      expect(FakeWebSocket.instances).toHaveLength(2);
      expect(screen.getAllByText("$110").length).toBeGreaterThan(0);
      expect(screen.getByTestId("simulation-chart-data-count")).toHaveTextContent("2/100");
      expect(screen.queryByRole("button", { name: "ma chart mode" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "candle chart mode" })).not.toBeInTheDocument();
    });

    act(() => {
      for (let i = 0; i < 101; i += 1) {
        FakeWebSocket.instances[1].onmessage({
          data: JSON.stringify({
            type: "tick",
            symbol: "TSLA",
            price: 200 + i,
            time: `2026-06-${String((i % 28) + 1).padStart(2, "0")}T15:${String(i % 60).padStart(2, "0")}:00Z`,
          }),
        });
      }
    });

    await waitFor(() => {
      expect(screen.getAllByText("$300").length).toBeGreaterThan(0);
      expect(screen.getByTestId("simulation-chart-data-count")).toHaveTextContent("100/100");
      expect(screen.getByTestId("simulation-chart-data-count")).not.toHaveTextContent("101");
    });
  });

  it("shows the loaded historical current price for simulation orders", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        rows: [{ date: "2026-05-25", open: 100, high: 101, low: 99, close: 100, volume: 1000 }],
      },
    });

    render(<StockSimulationSection />);

    clickFirstButton("historical chart");
    fireEvent.click(screen.getByRole("button", { name: "TSLA" }));

    await waitFor(() => expect(screen.getAllByText("$100").length).toBeGreaterThan(0));
  });
});
