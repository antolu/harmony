import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CitationList } from "./CitationList";

const makeSource = (n: number) => ({
  title: `Source ${n}`,
  url: `https://source${n}.com/page`,
  snippet: `Snippet for source ${n}`,
});

describe("CitationList", () => {
  it("shows all sources when no [N] references in content (D-20 fallback)", () => {
    render(
      <CitationList content="no citations here" sources={[makeSource(1)]} />,
    );
    expect(screen.getByText("Source 1")).toBeTruthy();
  });

  it("filters sources to only cited ones", () => {
    const sources = [makeSource(1), makeSource(2), makeSource(3)];
    render(<CitationList content="see [2] and [3]" sources={sources} />);
    expect(screen.queryByText("Source 1")).toBeNull();
    expect(screen.getByText("Source 2")).toBeTruthy();
    expect(screen.getByText("Source 3")).toBeTruthy();
  });

  it("shows all sources as fallback when only out-of-range [N] markers present", () => {
    render(<CitationList content="[99]" sources={[makeSource(1)]} />);
    expect(screen.getByText("Source 1")).toBeTruthy();
  });

  it("show more button reveals hidden cards", () => {
    const sources = [
      makeSource(1),
      makeSource(2),
      makeSource(3),
      makeSource(4),
    ];
    render(<CitationList content="[1][2][3][4]" sources={sources} />);
    expect(screen.getByText("Source 1")).toBeTruthy();
    expect(screen.getByText("Source 2")).toBeTruthy();
    expect(screen.getByText("Source 3")).toBeTruthy();
    expect(screen.queryByText("Source 4")).toBeNull();
    const showMore = screen.getByText("Show 1 more");
    fireEvent.click(showMore);
    expect(screen.getByText("Source 4")).toBeTruthy();
  });

  it("deduplicates repeated citations", () => {
    const sources = [makeSource(1), makeSource(2)];
    render(<CitationList content="[1] and [1] again" sources={sources} />);
    const cards = screen.getAllByText("Source 1");
    expect(cards).toHaveLength(1);
    expect(screen.queryByText("Source 2")).toBeNull();
  });

  it("handles multi-digit indices", () => {
    const sources = Array.from({ length: 10 }, (_, i) => makeSource(i + 1));
    render(<CitationList content="[10]" sources={sources} />);
    expect(screen.getByText("Source 10")).toBeTruthy();
    for (let i = 1; i <= 9; i++) {
      expect(screen.queryByText(`Source ${i}`)).toBeNull();
    }
  });
});
