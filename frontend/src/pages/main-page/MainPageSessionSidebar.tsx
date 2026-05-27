import type { SessionSummary } from "../../shared/api/types";
import { Button, Panel, Text } from "../../shared/components";
import styles from "./MainPage.module.css";

export type MainPageSessionSidebarProps = {
  activeSession: SessionSummary;
  isCreatingSession: boolean;
  isDeletingSession: boolean;
  isRenamingSession: boolean;
  onCreateSession: () => void;
  onDeleteSession: (session: SessionSummary) => void;
  onRenameSession: (session: SessionSummary) => void;
  onSelectSession: (session: SessionSummary, currentSessionId: string) => void;
  sessions: SessionSummary[];
};

export function MainPageSessionSidebar({
  activeSession,
  isCreatingSession,
  isDeletingSession,
  isRenamingSession,
  onCreateSession,
  onDeleteSession,
  onRenameSession,
  onSelectSession,
  sessions,
}: MainPageSessionSidebarProps) {
  return (
    <Panel
      as="aside"
      className={styles.sidebar}
      aria-label="Workflow sessions"
    >
      <div className={styles.sidebarHeader}>
        <Text as="span" variant="label">
          Workflow
        </Text>
        <Button
          disabled={isCreatingSession}
          onClick={onCreateSession}
          size="sm"
        >
          {isCreatingSession ? "Creating" : "New"}
        </Button>
      </div>
      <Text as="div" variant="eyebrow">
        Sessions
      </Text>
      {sessions.map((session) => (
        <button
          className={
            session.id === activeSession.id
              ? styles.activeNavItem
              : styles.navItem
          }
          key={session.id}
          onClick={() => onSelectSession(session, activeSession.id)}
          type="button"
        >
          {session.name}
        </button>
      ))}
      <div className={styles.sidebarActions}>
        <Button
          disabled={isRenamingSession}
          onClick={() => onRenameSession(activeSession)}
          size="sm"
          variant="ghost"
        >
          Rename
        </Button>
        <Button
          disabled={isDeletingSession}
          onClick={() => onDeleteSession(activeSession)}
          size="sm"
          variant="danger"
        >
          Delete
        </Button>
      </div>
    </Panel>
  );
}
