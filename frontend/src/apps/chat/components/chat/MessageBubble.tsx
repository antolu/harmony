import ReactMarkdown, { type Components } from "react-markdown";
import "highlight.js/styles/github.css";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import rehypeHighlight from "rehype-highlight";
import { defaultSchema } from "hast-util-sanitize";
import { MarkdownErrorBoundary } from "./MarkdownErrorBoundary";
import { StreamingCursor } from "./StreamingCursor";
import { CitationChip } from "./CitationChip";
import { CodeBlock } from "./CodeBlock";
import { remarkCitations } from "@/apps/chat/lib/remarkCitations";
import type { SourceItem } from "@/shared/hooks/useChat";

const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames ?? []), "citation"],
  attributes: {
    ...defaultSchema.attributes,
    a: [...(defaultSchema.attributes?.a ?? []), "href", "target", "rel"],
    citation: ["indices"],
  },
};

interface Props {
  content: string;
  isStreaming?: boolean;
  isUser?: boolean;
  sources?: SourceItem[];
}

export function MessageBubble({
  content,
  isStreaming,
  isUser,
  sources,
}: Props) {
  if (isUser) {
    return (
      <div className="text-[0.95rem] leading-relaxed text-foreground bg-muted rounded-2xl px-4 py-2.5 max-w-[80%] self-end shadow-sm">
        {content}
      </div>
    );
  }

  return (
    <div className="max-w-full">
      <MarkdownErrorBoundary rawContent={content}>
        <div className="prose prose-base max-w-none dark:prose-invert font-serif text-[1.0625rem] leading-[1.6] prose-headings:font-sans prose-p:my-2.5 prose-p:leading-[1.6] prose-headings:mb-2 prose-headings:mt-5 prose-ul:my-2.5 prose-ol:my-2.5 prose-li:my-0.5 prose-pre:bg-transparent prose-pre:text-foreground prose-pre:my-0 prose-a:text-primary">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkCitations]}
            rehypePlugins={[[rehypeSanitize, sanitizeSchema], rehypeHighlight]}
            components={
              {
                citation: (props: { indices?: number[] | string }) => {
                  let { indices } = props;
                  if (!indices) return null;
                  if (typeof indices === "string") {
                    indices = indices
                      .split(/[\s,]+/)
                      .map(Number)
                      .filter((n) => !isNaN(n));
                  }
                  if (!Array.isArray(indices) || indices.length === 0)
                    return null;
                  if (!sources || sources.length === 0) {
                    return (
                      <sup className="text-[0.65rem] text-muted-foreground">
                        [{indices.join(",")}]
                      </sup>
                    );
                  }
                  return <CitationChip indices={indices} sources={sources} />;
                },
                pre({ children }) {
                  return <CodeBlock>{children}</CodeBlock>;
                },
                code(props) {
                  const { children, className, ...rest } = props;
                  return (
                    <code className={className} {...rest}>
                      {children}
                    </code>
                  );
                },
                blockquote({ children }) {
                  return (
                    <blockquote className="border-l-4 border-border pl-4 italic text-muted-foreground">
                      {children}
                    </blockquote>
                  );
                },
                table({ children }) {
                  return (
                    <table className="border-collapse border border-border">
                      {children}
                    </table>
                  );
                },
                h1({ children }) {
                  return (
                    <h1 className="text-2xl font-semibold mt-6 first:mt-0">
                      {children}
                    </h1>
                  );
                },
                h2({ children }) {
                  return (
                    <h2 className="text-xl font-semibold mt-5 first:mt-0">
                      {children}
                    </h2>
                  );
                },
                h3({ children }) {
                  return (
                    <h3 className="text-lg font-semibold mt-4 first:mt-0">
                      {children}
                    </h3>
                  );
                },
              } as Components
            }
          >
            {content}
          </ReactMarkdown>
        </div>
      </MarkdownErrorBoundary>
      {isStreaming && <StreamingCursor />}
    </div>
  );
}
