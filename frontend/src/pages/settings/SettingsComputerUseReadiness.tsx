import type {
  ProductRecoveryAction,
  SettingsReadinessReport,
} from "../../shared/api/platoApi";
import { Button } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import { formatRecoveryAction } from "./settingsCopy";
import styles from "./SettingsRoute.module.css";

export function SettingsComputerUseReadiness({
  isRecoveryActionPending = false,
  onRecoveryAction,
  readiness,
}: {
  isRecoveryActionPending?: boolean;
  onRecoveryAction?: (action: ProductRecoveryAction) => void;
  readiness: SettingsReadinessReport | null;
}) {
  const uiText = useUiText();
  const computerUse = readiness?.computerUse ?? null;

  if (computerUse === null) {
    return null;
  }

  const permissionSubject = computerUse.permissionSubject ?? null;
  const signatureSummary = formatSignatureSummary(permissionSubject?.signature ?? null);
  const recoveryActions = uniqueRecoveryActions([
    ...computerUse.recoveryActions,
    ...(permissionSubject?.recoveryActions ?? []),
  ]).filter((action) => action !== "none");
  const actionableRecoveryActions = recoveryActions.filter(isActionableRecoveryAction);
  const manualRecoveryActions = recoveryActions.filter(
    (action) => !isActionableRecoveryAction(action),
  );

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
        {signatureSummary ? (
          <div>
            <dt>{uiText.settings.labels.computerUseSignature}</dt>
            <dd>{signatureSummary}</dd>
          </div>
        ) : null}
        {recoveryActions.length > 0 ? (
          <div>
            <dt>{uiText.settings.labels.computerUseRecoveryActions}</dt>
            <dd>
              {manualRecoveryActions
                .map((action) => formatRecoveryAction(action, uiText))
                .join(" ")}
            </dd>
          </div>
        ) : null}
      </dl>
      {actionableRecoveryActions.length > 0 ? (
        <div
          aria-label={uiText.settings.labels.computerUseRecoveryActions}
          className={styles.recoveryActionButtons}
        >
          {actionableRecoveryActions.map((action) => (
            <Button
              disabled={isRecoveryActionPending}
              key={action}
              onClick={() => onRecoveryAction?.(action)}
              size="sm"
              type="button"
              variant="secondary"
            >
              {formatRecoveryAction(action, uiText)}
            </Button>
          ))}
        </div>
      ) : null}
      {permissionSubject?.operatorInstruction ? (
        <p className={styles.helperText}>{permissionSubject.operatorInstruction}</p>
      ) : null}
    </section>
  );
}

function formatSignatureSummary(
  signature: NonNullable<
    NonNullable<SettingsReadinessReport["computerUse"]>["permissionSubject"]
  >["signature"] = null,
): string | null {
  if (!signature) {
    return null;
  }
  const parts = [
    signature.status ? `status=${signature.status}` : null,
    signature.identifier ? `identifier=${signature.identifier}` : null,
    typeof signature.infoPlistBound === "boolean"
      ? `infoPlistBound=${String(signature.infoPlistBound)}`
      : null,
    typeof signature.sealedResources === "boolean"
      ? `sealedResources=${String(signature.sealedResources)}`
      : null,
  ].filter((part): part is string => Boolean(part));
  return parts.length > 0 ? parts.join(" ") : null;
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

function isActionableRecoveryAction(action: ProductRecoveryAction): boolean {
  return (
    action === "open_macos_privacy_accessibility" ||
    action === "open_macos_privacy_automation" ||
    action === "restart_helper" ||
    action === "rerun_helper_preflight"
  );
}
