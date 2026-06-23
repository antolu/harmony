import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useApiKeyCreation } from "./useApiKeyCreation";

vi.mock("@/shared/api/client", () => ({
  api: {
    createLlmApiKey: vi.fn(),
  },
}));

import { api } from "@/shared/api/client";

const mockCreateLlmApiKey = vi.mocked(api.createLlmApiKey);

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useApiKeyCreation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts with creating=false", () => {
    const { result } = renderHook(() => useApiKeyCreation(), { wrapper });
    expect(result.current.creating).toBe(false);
  });

  it("sets creating=true during the request and false after it resolves", async () => {
    let resolveCreate: (
      value:
        | import("@/shared/api/client").LlmApiKeyEntry
        | PromiseLike<import("@/shared/api/client").LlmApiKeyEntry>,
    ) => void = () => {};
    mockCreateLlmApiKey.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve;
        }),
    );

    const { result } = renderHook(() => useApiKeyCreation(), { wrapper });

    let createPromise!: Promise<unknown>;
    act(() => {
      createPromise = result.current.createKey("my-key", "secret-value");
    });

    await waitFor(() => expect(result.current.creating).toBe(true));

    resolveCreate({
      id: "key-1",
      name: "my-key",
      value_set: true,
      created_at: "",
      updated_at: "",
      model_count: 0,
    });
    await act(async () => {
      await createPromise;
    });

    expect(result.current.creating).toBe(false);
    expect(mockCreateLlmApiKey).toHaveBeenCalledWith("my-key", "secret-value");
  });

  it("resets creating=false even when the request fails", async () => {
    mockCreateLlmApiKey.mockRejectedValue(new Error("network error"));

    const { result } = renderHook(() => useApiKeyCreation(), { wrapper });

    await act(async () => {
      await expect(
        result.current.createKey("my-key", "secret-value"),
      ).rejects.toThrow("network error");
    });

    expect(result.current.creating).toBe(false);
  });
});
