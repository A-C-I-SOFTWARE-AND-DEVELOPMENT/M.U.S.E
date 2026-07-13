import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  private handleReload = () => {
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-dvh w-full flex-col items-center justify-center bg-zinc-950 text-white">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-8 text-center shadow-2xl shadow-cyan-500/10">
            <h1 className="text-2xl font-bold text-red-500">
              Something went wrong.
            </h1>
            <p className="mt-2 text-sm text-zinc-400">
              An unexpected error occurred in the application.
            </p>
            {this.state.error && (
              <pre className="mt-4 max-w-md whitespace-pre-wrap rounded-md bg-zinc-900 p-4 text-left text-xs text-red-400">
                {this.state.error.toString()}
              </pre>
            )}
            <button
              onClick={this.handleReload}
              className="mt-6 rounded-md bg-cyan-500 px-4 py-2 text-sm font-semibold text-zinc-950 transition-colors hover:bg-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-zinc-950"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export { ErrorBoundary };
export default ErrorBoundary;
