import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useChat } from "./useChat";

vi.mock("@/shared/api/client", () => ({
  createSSEPostConnection: vi.fn(),
}));

import { createSSEPostConnection } from "@/shared/api/client";

const mockCreateSSE = vi.mocked(createSSEPostConnection);

describe("useChat", () => {
  let capturedOnMessage: ((event: string, data: unknown) => void) | null = null;
  const mockCleanup = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    capturedOnMessage = null;

    mockCreateSSE.mockImplementation(
      (_endpoint, _body, _eventTypes, onMessage) => {
        capturedOnMessage = onMessage;
        return mockCleanup;
      },
    );
  });

  it("accumulates answer_chunk events", () => {
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.startStreaming("/ai-search", { query: "test" });
    });

    act(() => {
      capturedOnMessage!("answer_chunk", { content: "A" });
      capturedOnMessage!("answer_chunk", { content: "B" });
      capturedOnMessage!("answer_chunk", { content: "C" });
    });

    expect(result.current.content).toBe("ABC");
  });

  it("done event sets conversationId", () => {
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.startStreaming("/ai-search", { query: "test" });
    });

    act(() => {
      capturedOnMessage!("done", {
        conversation_id: "conv-123",
        sources: [],
      });
    });

    expect(result.current.conversationId).toBe("conv-123");
  });

  it("done event sets isStreaming false", () => {
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.startStreaming("/ai-search", { query: "test" });
    });

    expect(result.current.isStreaming).toBe(true);

    act(() => {
      capturedOnMessage!("done", { conversation_id: null, sources: [] });
    });

    expect(result.current.isStreaming).toBe(false);
  });

  it("status event with kind=search carries sources on the step", () => {
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.startStreaming("/agentic-search", { query: "test" });
    });

    act(() => {
      capturedOnMessage!("status", {
        message: "Searching for vacation policy",
        kind: "search",
        sources: [
          { title: "Policy doc", url: "https://example.com", snippet: "" },
        ],
      });
    });

    expect(result.current.steps).toHaveLength(1);
    expect(result.current.steps[0].kind).toBe("search");
    expect(result.current.steps[0].sources).toEqual([
      { title: "Policy doc", url: "https://example.com", snippet: "" },
    ]);
  });

  it("status event with kind=tool_call has no sources", () => {
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.startStreaming("/ai-search", { query: "test" });
    });

    act(() => {
      capturedOnMessage!("status", {
        message: "Searching for vacation policy",
        kind: "tool_call",
      });
    });

    expect(result.current.steps).toHaveLength(1);
    expect(result.current.steps[0].kind).toBe("tool_call");
    expect(result.current.steps[0].sources).toBeUndefined();
  });

  it("error event sets error and isStreaming false", () => {
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.startStreaming("/ai-search", { query: "test" });
    });

    act(() => {
      capturedOnMessage!("error", { message: "fail" });
    });

    expect(result.current.error).toBe("fail");
    expect(result.current.isStreaming).toBe(false);
  });

  it("stopStreaming calls cleanup function", () => {
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.startStreaming("/ai-search", { query: "test" });
    });

    act(() => {
      result.current.stopStreaming();
    });

    expect(mockCleanup).toHaveBeenCalled();
    expect(result.current.isStreaming).toBe(false);
  });

  it("startStreaming resets state before new events", () => {
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.startStreaming("/ai-search", { query: "test" });
    });

    act(() => {
      capturedOnMessage!("answer_chunk", { content: "existing" });
    });

    expect(result.current.content).toBe("existing");

    act(() => {
      result.current.startStreaming("/ai-search", { query: "new" });
    });

    expect(result.current.content).toBe("");
  });
});
