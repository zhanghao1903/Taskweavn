import { PlatoProductMark } from "../pages/main-page/PlatoProductMark";
import styles from "./StartupShell.module.css";

export type StartupShellProps = {
  workspaceName?: string | null;
};

export function StartupShell({ workspaceName = null }: StartupShellProps) {
  return (
    <main className={styles.shell} aria-busy="true" aria-live="polite">
      <section className={styles.panel} aria-label="Plato startup">
        <div className={styles.brandRow}>
          <PlatoProductMark className={styles.mark} />
          <div>
            <p className={styles.eyebrow}>Plato</p>
            <h1>Starting Plato</h1>
          </div>
        </div>
        <p className={styles.message}>Preparing local workspace runtime.</p>
        {workspaceName ? (
          <p className={styles.workspace}>{workspaceName}</p>
        ) : null}
        <div className={styles.progressTrack} aria-hidden="true">
          <div className={styles.progressBar} />
        </div>
      </section>
    </main>
  );
}
