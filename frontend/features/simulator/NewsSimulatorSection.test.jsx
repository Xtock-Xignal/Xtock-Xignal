import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NewsSimulatorSection from "./NewsSimulatorSection";
import api from "../../utils/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("../../utils/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe("NewsSimulatorSection", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
  });

  it("renders industry classification badges from news responses", async () => {
    api.get.mockResolvedValue({
      data: {
        has_new: false,
        news: [
          {
            id: "news-1",
            source: "Yahoo RSS",
            date: "2026-01-01T10:00:00",
            title: "Nvidia chip demand rises",
            original: "Nvidia said demand for AI semiconductor chips remains strong.",
            is_vip: true,
            related_tags: ["NVDA"],
            industry_classification: {
              sector: "Information Technology",
              industry_group: "Semiconductors & Semiconductor Equipment",
              confidence: 0.85,
              explanation: "chip keyword matched",
            },
          },
        ],
      },
    });

    render(<NewsSimulatorSection />);

    expect(await screen.findByText("Nvidia chip demand rises")).toBeInTheDocument();
    expect(
      screen.getByText("Information Technology · Semiconductors & Semiconductor Equipment")
    ).toBeInTheDocument();
  });

  it("searches a highlighted financial term from an article", async () => {
    api.get.mockImplementation((url) => {
      if (String(url).startsWith("/api/news/live")) {
        return Promise.resolve({
          data: {
            has_new: false,
            news: [
              {
                id: "news-1",
                source: "Yahoo RSS",
                date: "2026-01-01T10:00:00",
                title: "Fed decision preview",
                original: "Investors are watching the FOMC decision today.",
                link: "https://example.test/news-1",
                is_vip: false,
                related_tags: [],
              },
            ],
          },
        });
      }

      if (String(url).startsWith("/api/terms/search")) {
        return Promise.resolve({
          data: {
            found: true,
            en_term: "FOMC",
            ko_term: "연방공개시장위원회",
            definition: "미국 기준금리 방향을 논의하는 회의입니다.",
            source: "DB",
          },
        });
      }

      return Promise.resolve({ data: {} });
    });

    api.post.mockResolvedValue({
      data: {
        matched_terms: [{ en_term: "FOMC", ko_term: "연방공개시장위원회" }],
      },
    });

    render(<NewsSimulatorSection />);

    fireEvent.click(await screen.findByText("Fed decision preview"));
    fireEvent.click(await screen.findByText("FOMC"));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/terms/search?keyword=FOMC");
    });
    expect(await screen.findByText("미국 기준금리 방향을 논의하는 회의입니다.")).toBeInTheDocument();
  });

  it("calls translation and summary APIs from the article view", async () => {
    api.get.mockResolvedValue({
      data: {
        has_new: false,
        news: [
          {
            id: "news-1",
            source: "Finnhub API",
            date: "2026-01-01T10:00:00",
            title: "Market update",
            original: "Stocks moved higher after earnings guidance improved.",
            link: "https://example.test/news-2",
            is_vip: false,
            related_tags: [],
          },
        ],
      },
    });
    api.post.mockImplementation((url) => {
      if (url === "/api/terms/scan") {
        return Promise.resolve({ data: { matched_terms: [] } });
      }
      if (url === "/api/news/translate") {
        return Promise.resolve({ data: { translated_text: "실적 전망 개선 이후 주가가 상승했습니다." } });
      }
      if (url === "/api/news/summary") {
        return Promise.resolve({ data: { summary: "1. 실적 전망이 개선됐습니다.\n2. 주가가 상승했습니다.\n3. 투자자는 후속 지표를 봅니다." } });
      }
      return Promise.resolve({ data: {} });
    });

    render(<NewsSimulatorSection />);

    fireEvent.click(await screen.findByText("Market update"));
    fireEvent.click(screen.getByRole("button", { name: /한글로 보기/ }));
    expect(await screen.findByText("실적 전망 개선 이후 주가가 상승했습니다.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /요약 생성/ }));
    expect(await screen.findByText(/1. 실적 전망이 개선됐습니다./)).toBeInTheDocument();
  });
});
