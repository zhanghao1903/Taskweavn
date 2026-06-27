import type {
  ProductRecoveryAction,
  SettingsReadinessReport,
} from "../../shared/api/platoApi";
import { useUiText } from "../../shared/ui-text";
import { formatRecoveryAction } from "./settingsCopy";
import styles from "./SettingsRoute.module.css";

export function SettingsComputerUseReadiness({
  readiness,
}: {
  readiness: SettingsReadinessReport | null;
}) {
  const uiText = useUiText();
  const computerUse = readiness?.computerUse ?? null;

  if (computerUse === null) {
    return null;
  }

  const permissionSubject = computerUse.permissionSubject ?? null;
  const recoveryActions = uniqueRecoveryActions([
    ...computerUse.recoveryActions,
    ...(permissionSubject?.recoveryActions ?? []),
  ]).filter((action) => action !== "none");

  return (
    <section
      className={styles.settingsSubsection}
      aria-label={uiText.settings.labels.computerUseReadiness}
    >
      <h2>{uiText.settings.labels.computerUseReadiness}</h2>
      <p className={styles.helperText}>{computerUse.summary}</p>
      <dl className={styles.inlineStatusList}>
        <div>
          <dt>{uiText.settings.labels.computerUseBackend}</dt>
          <dd>{computerUse.backend}</dd>
        </div>
        <div>
          <dt>{uiText.settings.labels.computerUseStatus}</dt>
          <dd>{computerUse.status}</dd>
        </div>
        {computerUse.failureKind ? (
          <div>
            <dt>{uiText.settings.labels.computerUseFailureKind}</dt>
            <dd>{computerUse.failureKind}</dd>
          </div>
        ) : null}
        {permissionSubject?.helperAppPath ? (
          <div>
            <dt>{uiText.settings.labels.computerUseHelperApp}</dt>
            <dd>{permissionSubject.helperAppPath}</dd>
          </div>
        ) : null}
        {permissionSubject?.effectiveExecutable ? (
          <div>
            <dt>{uiText.settings.labels.computerUseExecutable}</dt>
            <dd>{permissionSubject.effectiveExecutable}</dd>
          </div>
        ) : null}
        {typeof permissionSubject?.accessibilityTrusted === "boolean" ? (
          <div>
            <dt>{uiText.settings.labels.computerUseAccessibility}</dt>
            <dd>{String(permissionSubject.accessibilityTrusted)}</dd>
          </div>
        ) : null}
        {recoveryActions.length > 0 ? (
          <div>
            <dt>{uiText.settings.labels.computerUseRecoveryActions}</dt>
            <dd>
              {recoveryActions
                .map((action) => formatRecoveryAction(action, uiText))
                .join(" ")}
            </dd>
          </div>
        ) : null}
      </dl>
      {permissionSubject?.operatorInstruction ? (
        <p className={styles.helperText}>{permissionSubject.operatorInstruction}</p>
      ) : null}
    </section>
  );
}

function uniqueRecoveryActions(
  actions: ProductRecoveryAction[],
): ProductRecoveryAction[] {
  const seen = new Set<ProductRecoveryAction>();
  for (const action of actions) {
    seen.add(action);
  }
  return [...seen];
}
