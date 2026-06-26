import * as React from "react";

interface Props {
  children: React.ReactNode;
  rawContent?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class MarkdownErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  static getDerivedStateFromProps(
    _nextProps: Props,
    prevState: State,
  ): Partial<State> | null {
    if (prevState.hasError) {
      return { hasError: false, error: null };
    }
    return null;
  }

  render() {
    if (this.state.hasError) {
      return (
        <pre className="text-sm text-muted-foreground bg-muted p-2 rounded overflow-x-auto whitespace-pre-wrap">
          {this.props.rawContent ??
            "(Rendering error — cannot display formatted content)"}
        </pre>
      );
    }
    return this.props.children;
  }
}
