import { useState, type ReactNode } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/shared/lib/utils";

function extractText(node: ReactNode): string {
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (
    node &&
    typeof node === "object" &&
    "props" in node &&
    (node as { props?: { children?: ReactNode } }).props
  ) {
    return extractText(
      (node as { props: { children?: ReactNode } }).props.children,
    );
  }
  return "";
}

function detectLanguage(children: ReactNode): string | null {
  if (
    children &&
    typeof children === "object" &&
    "props" in children &&
    (children as { props?: { className?: string } }).props
  ) {
    const className =
      (children as { props: { className?: string } }).props.className ?? "";
    const match = /language-([\w-]+)/.exec(className);
    if (match) return match[1];
  }
  return null;
}

export function CodeBlock({ children }: { children?: ReactNode }) {
  const [copied, setCopied] = useState(false);
  const language = detectLanguage(children);

  function handleCopy() {
    const text = extractText(children);
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="group/code relative my-4 overflow-hidden rounded-xl border border-border bg-secondary">
      <div className="flex items-center justify-between border-b border-border/60 px-3.5 py-1.5">
        <span className="text-xs font-medium text-muted-foreground">
          {language ?? "code"}
        </span>
        <button
          type="button"
          aria-label="Copy code"
          onClick={handleCopy}
          className={cn(
            "flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground",
          )}
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              Copy
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto px-5 py-4 text-[1rem] leading-[1.6]">
        {children}
      </pre>
    </div>
  );
}
