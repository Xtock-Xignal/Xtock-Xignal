import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "./LoginPage";

vi.mock("../utils/api", () => ({
  default: {
    post: vi.fn(),
  },
}));

import api from "../utils/api";

describe("LoginPage", () => {
  beforeEach(() => {
    api.post.mockReset();
    window.alert = vi.fn();
  });

  it("로그인 성공 시 onLogin 콜백이 호출된다", async () => {
    const onLogin = vi.fn();
    api.post.mockResolvedValue({
      data: {
        success: true,
        user: { username: "테스터", email: "test@example.com" },
      },
    });

    render(<LoginPage onLogin={onLogin} />);

    fireEvent.change(screen.getByPlaceholderText("이메일 주소"), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("비밀번호"), {
      target: { value: "pass1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));

    await waitFor(() => {
      expect(onLogin).toHaveBeenCalledWith({
        username: "테스터",
        email: "test@example.com",
      });
    });

    expect(api.post).toHaveBeenCalledWith("/api/login", {
      email: "test@example.com",
      password: "pass1234",
    });
  });

  it("회원가입 화면에서 성공하면 로그인 화면으로 돌아간다", async () => {
    api.post.mockResolvedValue({
      data: {
        success: true,
      },
    });
    const onLogin = vi.fn();

    render(<LoginPage onLogin={onLogin} />);

    fireEvent.click(screen.getByText("회원가입"));
    fireEvent.change(screen.getByPlaceholderText("사용자 이름"), {
      target: { value: "new-user" },
    });
    fireEvent.change(screen.getByPlaceholderText("이메일 주소"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("비밀번호"), {
      target: { value: "new-pass" },
    });
    fireEvent.click(screen.getByRole("button", { name: "회원가입" }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/register", {
        username: "new-user",
        email: "new@example.com",
        password: "new-pass",
      });
    });

    expect(screen.getByRole("button", { name: "로그인" })).toBeInTheDocument();
    expect(onLogin).not.toHaveBeenCalled();
  });
});
