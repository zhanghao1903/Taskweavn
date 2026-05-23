import type { ErrorInfo, ReactNode } from "react";
import { Component } from "react";

import { Badge, Panel, Text } from "../shared/components";
import {
  createFrontendLogger,
  toLoggableError,
} from "../shared/logging/frontendLogger";
import styles from "../pages/main-page/MainPage.module.css";

const errorBoundaryLogger = createFrontendLogger("app-error-boundary");

type AppErrorBoundaryProps = {
  children: ReactNode;
};

type AppErrorBoundaryState = {
  error: Error | null;
};

export class AppErrorBoundary extends Component<
  AppErrorBoundaryProps,
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = {
    error: null,
  };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return {
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    errorBoundaryLogger.error("render.failed", {
      componentStack: errorInfo.componentStack,
      error: toLoggableError(error),
    });
  }

  render() {
    if (this.state.error) {
      return (
        <main className={styles.page}>
          <header className={styles.topBar}>
            <div className={styles.brand}>柏拉图 Plato</div>
            <div className={styles.contextStack}>
              <span>Runtime boundary</span>
              <span>Render error</span>
            </div>
            <Badge tone="danger">Render error</Badge>
          </header>

          <Panel
            as="section"
            className={styles.workspace}
            aria-label="Application error"
          >
            <div className={styles.emptyState}>
              <Text as="h1" variant="heading">
                Plato could not render this view
              </Text>
              <Text variant="muted">
                {this.state.error.name}: {this.state.error.message}
              </Text>
            </div>
          </Panel>
        </main>
      );
    }

    return this.props.children;
  }
}
