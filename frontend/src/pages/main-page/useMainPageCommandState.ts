import { useCallback, useState } from "react";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";

type SetCommandError = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export function useMainPageCommandState() {
  const [confirmationError, setConfirmationError] = useState<string | null>(
    null,
  );
  const [confirmationRecoveryActions, setConfirmationRecoveryActions] =
    useState<ProductRecoveryAction[]>([]);
  const [authoringAskError, setAuthoringAskError] = useState<string | null>(
    null,
  );
  const [authoringAskRecoveryActions, setAuthoringAskRecoveryActions] =
    useState<ProductRecoveryAction[]>([]);
  const [executionAskError, setExecutionAskError] = useState<string | null>(
    null,
  );
  const [executionAskRecoveryActions, setExecutionAskRecoveryActions] =
    useState<ProductRecoveryAction[]>([]);
  const [inputError, setInputError] = useState<string | null>(null);
  const [inputRecoveryActions, setInputRecoveryActions] = useState<
    ProductRecoveryAction[]
  >([]);
  const [taskTreeCommandError, setTaskTreeCommandError] = useState<string | null>(
    null,
  );
  const [
    taskTreeCommandRecoveryActions,
    setTaskTreeCommandRecoveryActions,
  ] = useState<ProductRecoveryAction[]>([]);

  const setConfirmationCommandError: SetCommandError = useCallback(
    (message, recoveryActions = []) => {
      setConfirmationError(message);
      setConfirmationRecoveryActions(message === null ? [] : recoveryActions);
    },
    [],
  );

  const setAuthoringAskCommandError: SetCommandError = useCallback(
    (message, recoveryActions = []) => {
      setAuthoringAskError(message);
      setAuthoringAskRecoveryActions(message === null ? [] : recoveryActions);
    },
    [],
  );

  const setExecutionAskCommandError: SetCommandError = useCallback(
    (message, recoveryActions = []) => {
      setExecutionAskError(message);
      setExecutionAskRecoveryActions(message === null ? [] : recoveryActions);
    },
    [],
  );

  const setInputCommandError: SetCommandError = useCallback(
    (message, recoveryActions = []) => {
      setInputError(message);
      setInputRecoveryActions(message === null ? [] : recoveryActions);
    },
    [],
  );

  const setTaskTreeCommandFailure: SetCommandError = useCallback(
    (message, recoveryActions = []) => {
      setTaskTreeCommandError(message);
      setTaskTreeCommandRecoveryActions(
        message === null ? [] : recoveryActions,
      );
    },
    [],
  );

  const clearCommandRecoveryActions = useCallback(() => {
    setAuthoringAskRecoveryActions([]);
    setConfirmationRecoveryActions([]);
    setExecutionAskRecoveryActions([]);
    setInputRecoveryActions([]);
    setTaskTreeCommandRecoveryActions([]);
  }, []);

  const clearCommandState = useCallback(() => {
    setAuthoringAskError(null);
    setConfirmationError(null);
    setExecutionAskError(null);
    setInputError(null);
    setTaskTreeCommandError(null);
    clearCommandRecoveryActions();
  }, [clearCommandRecoveryActions]);

  return {
    authoringAskError,
    authoringAskRecoveryActions,
    clearCommandState,
    confirmationError,
    confirmationRecoveryActions,
    executionAskError,
    executionAskRecoveryActions,
    inputError,
    inputRecoveryActions,
    setAuthoringAskCommandError,
    setConfirmationCommandError,
    setExecutionAskCommandError,
    setInputCommandError,
    setTaskTreeCommandError,
    setTaskTreeCommandFailure,
    taskTreeCommandError,
    taskTreeCommandRecoveryActions,
  };
}
