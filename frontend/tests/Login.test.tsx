import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { Login } from "../src/pages/Login";
import { StatusBadge } from "../src/components/StatusBadge";
import { en } from "../src/i18n/en";
import { hi } from "../src/i18n/hi";

const BANNED_WORDS = ["fraud", "fake", "scam"];

describe("StatusBadge", () => {
  it("renders the icon and label with the design-token classes", () => {
    render(<StatusBadge icon="fa-solid fa-circle-check" label="API reachable" tone="positive" />);

    expect(screen.getByText("API reachable")).toBeInTheDocument();
    const icon = document.querySelector(".fa-circle-check");
    expect(icon).not.toBeNull();
    expect(icon?.className).toContain("text-verified-official");
  });
});

describe("Login page", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sets novalidate on the form", () => {
    render(<Login />);

    const form = document.querySelector("form");
    expect(form).toHaveAttribute("novalidate");
  });

  it("renders the fa-lock icon in the page header", () => {
    render(<Login />);

    expect(document.querySelector(".fa-lock")).not.toBeNull();
  });

  it("shows the error state without banned words on a failed login", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: false,
      json: async () => ({ error: { code: "UNAUTHENTICATED", message: en.loginFailedError } }),
    } as Response);

    render(<Login />);
    fireEvent.change(screen.getByTestId("email-input"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByTestId("password-input"), { target: { value: "wrong-password" } });
    fireEvent.click(screen.getByRole("button", { name: en.submitButton }));

    const errorMessage = await screen.findByRole("alert");
    const text = errorMessage.textContent?.toLowerCase() ?? "";
    for (const banned of BANNED_WORDS) {
      expect(text).not.toContain(banned);
    }
  });

  it("renders three StatusBadge instances after a mocked successful login", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const path = typeof url === "string" ? url : url.toString();
      if (path.endsWith("/auth/login")) {
        return {
          ok: true,
          json: async () => ({ data: { accessToken: "fake-token" }, meta: {} }),
        } as Response;
      }
      if (path.endsWith("/auth/me")) {
        return {
          ok: true,
          json: async () => ({
            data: { id: "u1", email: "jane@example.com", memberships: [], role: "analyst" },
            meta: {},
          }),
        } as Response;
      }
      if (path.endsWith("/health")) {
        return { ok: true, json: async () => ({ status: "ok", mongo: "ok" }) } as Response;
      }
      throw new Error(`Unexpected fetch to ${path}`);
    });

    render(<Login />);
    fireEvent.change(screen.getByTestId("email-input"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByTestId("password-input"), {
      target: { value: "correct-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.submitButton }));

    await waitFor(() => {
      expect(screen.getAllByRole("status")).toHaveLength(3);
    });
  });
});

describe("i18n completeness", () => {
  it("has a Hindi string for every English key", () => {
    const englishKeys = Object.keys(en).sort();
    const hindiKeys = Object.keys(hi).sort();
    expect(hindiKeys).toEqual(englishKeys);
  });

  it("has no empty strings in either language", () => {
    for (const [key, value] of Object.entries(en)) {
      if (typeof value === "string") {
        expect(value.length, `en.${key} should not be empty`).toBeGreaterThan(0);
      }
    }
    for (const [key, value] of Object.entries(hi)) {
      if (typeof value === "string") {
        expect(value.length, `hi.${key} should not be empty`).toBeGreaterThan(0);
      }
    }
  });
});
