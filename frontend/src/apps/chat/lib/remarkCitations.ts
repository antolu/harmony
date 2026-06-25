interface MdastNode {
  type: string;
  value?: string;
  children?: MdastNode[];
  data?: { hName?: string; hProperties?: Record<string, unknown> };
}

const CITATION_PATTERN = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

function splitTextNode(node: MdastNode): MdastNode[] {
  const text = node.value ?? "";
  const parts: MdastNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  CITATION_PATTERN.lastIndex = 0;
  while ((match = CITATION_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }
    const indices = match[1].split(",").map((s) => parseInt(s, 10));
    parts.push({
      type: "citation",
      data: { hName: "citation", hProperties: { indices } },
    });
    lastIndex = match.index + match[0].length;
  }

  if (parts.length === 0) {
    return [node];
  }
  if (lastIndex < text.length) {
    parts.push({ type: "text", value: text.slice(lastIndex) });
  }
  return parts;
}

function visitChildren(node: MdastNode): void {
  if (!node.children) return;

  const newChildren: MdastNode[] = [];
  for (const child of node.children) {
    if (child.type === "text" && child.value?.includes("[")) {
      newChildren.push(...splitTextNode(child));
    } else {
      visitChildren(child);
      newChildren.push(child);
    }
  }
  node.children = newChildren;
}

export function remarkCitations() {
  return (tree: MdastNode) => {
    visitChildren(tree);
  };
}
