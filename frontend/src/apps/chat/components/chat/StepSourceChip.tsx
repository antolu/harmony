import { useState } from "react";
import { Globe } from "lucide-react";

interface Props {
  title: string;
  url: string;
}

function getSafeHostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

export function StepSourceChip({ title, url }: Props) {
  const [imgError, setImgError] = useState(false);
  const hostname = getSafeHostname(url);

  return (
    <span
      className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
      title={title}
    >
      {!imgError ? (
        <img
          src={`https://${hostname}/favicon.ico`}
          width={12}
          height={12}
          alt=""
          onError={() => setImgError(true)}
        />
      ) : (
        <Globe className="h-3 w-3 shrink-0" />
      )}
      <span className="truncate max-w-[120px]">{hostname}</span>
    </span>
  );
}
