import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useModelStepState } from "./useModelStepState";

describe("useModelStepState", () => {
  it("initializes with the given default provider", () => {
    const { result } = renderHook(() => useModelStepState("ollama"));

    expect(result.current.provider).toBe("ollama");
    expect(result.current.model).toBe("");
    expect(result.current.validated).toBe(true);
    expect(result.current.hostKeyIds).toEqual({});
  });

  it("updates model and provider via setters", () => {
    const { result } = renderHook(() => useModelStepState("litellm"));

    act(() => {
      result.current.setProvider("hosted_vllm");
      result.current.setModel("Qwen/Qwen3.5-9B");
    });

    expect(result.current.provider).toBe("hosted_vllm");
    expect(result.current.model).toBe("Qwen/Qwen3.5-9B");
  });

  it("merges partial updates via onHostKeyChange instead of overwriting", () => {
    const { result } = renderHook(() => useModelStepState("ollama"));

    act(() => {
      result.current.onHostKeyChange({ ollama_host_id: "host-1" });
    });
    act(() => {
      result.current.onHostKeyChange({ api_key_id: "key-1" });
    });

    expect(result.current.hostKeyIds).toEqual({
      ollama_host_id: "host-1",
      api_key_id: "key-1",
    });
  });

  it("reset clears model, resets validated, and defaults provider to litellm", () => {
    const { result } = renderHook(() => useModelStepState("ollama"));

    act(() => {
      result.current.setModel("some-model");
      result.current.setValidated(false);
    });
    act(() => {
      result.current.reset();
    });

    expect(result.current.model).toBe("");
    expect(result.current.validated).toBe(true);
    expect(result.current.provider).toBe("litellm");
  });

  it("reset accepts an explicit provider override", () => {
    const { result } = renderHook(() => useModelStepState("ollama"));

    act(() => {
      result.current.reset("hosted_vllm");
    });

    expect(result.current.provider).toBe("hosted_vllm");
  });

  it("reset does not clear hostKeyIds", () => {
    const { result } = renderHook(() => useModelStepState("ollama"));

    act(() => {
      result.current.onHostKeyChange({ ollama_host_id: "host-1" });
    });
    act(() => {
      result.current.reset();
    });

    expect(result.current.hostKeyIds).toEqual({ ollama_host_id: "host-1" });
  });
});
