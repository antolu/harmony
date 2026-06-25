import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import rehypeHighlight from "rehype-highlight";
import { defaultSchema } from "hast-util-sanitize";
import { MarkdownErrorBoundary } from "./MarkdownErrorBoundary";
import { StreamingCursor } from "./StreamingCursor";
import { CitationChip } from "./CitationChip";
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
      <div className="text-sm text-foreground bg-muted rounded-lg p-3 max-w-[80%] self-end">
        {content}
      </div>
    );
  }

  return (
    <div className="max-w-full">
      <MarkdownErrorBoundary rawContent={content}>
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkCitations]}
            rehypePlugins={[[rehypeSanitize, sanitizeSchema], rehypeHighlight]}
            components={
              {
                citation: (props: { indices?: number[] }) => {
                  const { indices } = props;
                  if (!indices || !sources) return null;
                  return <CitationChip indices={indices} sources={sources} />;
                },
                code(props) {
                  const { children, className, node, ...rest } = props;
                  const isCodeBlock =
                    node?.position !== undefined &&
                    (node.type as string) !== "inlineCode" &&
                    !!className;
                  if (isCodeBlock && isStreaming && !className) {
                    return (
                      <pre className="bg-muted p-2 rounded text-xs whitespace-pre-wrap overflow-x-auto">
                        <code>{children}</code>
                      </pre>
                    );
                  }
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
                  return <h1 className="text-xl font-semibold">{children}</h1>;
                },
                h2({ children }) {
                  return <h2 className="text-xl font-semibold">{children}</h2>;
                },
                h3({ children }) {
                  return <h3 className="text-xl font-semibold">{children}</h3>;
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
