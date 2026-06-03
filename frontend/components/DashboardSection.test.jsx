import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardSection from "./DashboardSection";

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: () => null }),
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("../utils/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import api from "../utils/api";

describe("DashboardSection", () => {
  class MockWebSocket {
    static OPEN = 1;

    constructor(url) {
      this.url = url;
      this.readyState = MockWebSocket.OPEN;
      MockWebSocket.instances.push(this);
      setTimeout(() => {
        this.onopen?.();
      }, 0);
    }

    send = vi.fn();
    close = vi.fn();
  }

  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  it("requests chart history when a stock row is opened", async () => {
    api.get
      .mockResolvedValueOnce({
        data: {
          indices: [],
          topStock: {
            symbol: "AAPL",
            price: 100,
            change: 1,
            changePercent: 1,
            marketCap: 1000000000,
            chartData: [{ date: "2026-01-01", price: 100 }],
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          symbol: "AAPL",
          rows: [
            { date: "2026-01-02", close: 100.5, volume: 1000 },
            { date: "2026-01-03", close: 102.25, volume: 1500 },
          ],
        },
      });

    render(<DashboardSection />);

    const row = await screen.findByText("Apple Inc.");
    fireEvent.click(row);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith(
        "/api/chart/history/AAPL",
        expect.objectContaining({
          params: { period: "1mo", interval: "1d" },
        })
      );
    });

    expect(await screen.findByText("$102.25")).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
    expect(MockWebSocket.instances[0].url).toBe("ws://localhost:8000/api/chart/ws/AAPL");
  });

  it("merges realtime tick rows into the existing chart row shape", async () => {
    api.get
      .mockResolvedValueOnce({
        data: {
          indices: [],
          topStock: {
            symbol: "AAPL",
            price: 100,
            change: 1,
            changePercent: 1,
            marketCap: 1000000000,
            chartData: [{ date: "2026-01-01", price: 100 }],
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          symbol: "AAPL",
          rows: [{ date: "2026-01-02", close: 100.5, volume: 1000 }],
        },
      });

    render(<DashboardSection />);

    fireEvent.click(await screen.findByText("Apple Inc."));

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    const socket = MockWebSocket.instances[0];
    const firstPayload = JSON.stringify({
      type: "tick",
      symbol: "AAPL",
      price: 101.25,
      time: "2026-01-02T15:00:00Z",
      row: {
        date: "2026-01-02",
        time: "2026-01-02T15:00:00Z",
        open: 101.25,
        high: 101.25,
        low: 101.25,
        close: 101.25,
        volume: 0,
      },
    });
    const samePricePayload = JSON.stringify({
      type: "tick",
      symbol: "AAPL",
      price: 101.25,
      time: "2026-01-02T15:01:00Z",
      row: {
        date: "2026-01-02",
        time: "2026-01-02T15:01:00Z",
        open: 101.25,
        high: 101.25,
        low: 101.25,
        close: 101.25,
        volume: 0,
      },
    });

    act(() => {
      socket.onmessage({ data: firstPayload });
      socket.onmessage({ data: samePricePayload });
    });

    expect(await screen.findByText((text) => text.includes("최신가"))).toBeInTheDocument();
    expect(screen.getAllByText("$101.25").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("$100.5")).not.toBeInTheDocument();
  });
});
