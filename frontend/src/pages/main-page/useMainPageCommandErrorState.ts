import { useCallback, useState } from "react";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";

type CommandErrorSetter = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export type MainPageCommandErrorState = {
  authoringAskError: string | null;
  authoringAskRecoveryActions: ProductRecoveryAction[];
  confirmationError: string | null;
  confirmationRecoveryActions: ProductRecoveryAction[];
  executionAskError: string | null;
  executionAskRecoveryActions: ProductRecoveryAction[];
  inputError: string | null;
  inputRecoveryActions: ProductRecoveryAction[];
  taskTreeCommandError: string | null;
  taskTreeCommandRecoveryActions: ProductRecoveryAction[];
  resetCommandErrorState: () => void;
  setAuthoringAskCommandError: CommandErrorSetter;
  setConfirmationCommandError: CommandErrorSetter;
  setExecutionAskCommandError: CommandErrorSetter;
  setInputCommandError: CommandErrorSetter;
  setTaskTreeCommandError: (message: string | null) => void;
  setTaskTreeCommandFailure: CommandErrorSetter;
};

export function useMainPageCommandErrorState(): MainPageCommandErrorState {
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
  const [taskTreeCommandError, setTaskTreeCommandError] = useState<
    string | null
  >(null);
  const [
    taskTreeCommandRecoveryActions,
    setTaskTreeCommandRecoveryActions,
  ] = useState<ProductRecoveryAction[]>([]);

  const setConfirmationCommandError = useCallback<CommandErrorSetter>(
    (message, recoveryActions = []) => {
      setConfirmationError(message);
      setConfirmationRecoveryActions(message === null ? [] : recoveryActions);
    },
    [],
  );

  const setAuthoringAskCommandError = useCallback<CommandErrorSetter>(
    (message, recoveryActions = []) => {
      setAuthoringAskError(message);
      setAuthoringAskRecoveryActions(message === null ? [] : recoveryActions);
    },
    [],
  );

  const setExecutionAskCommandError = useCallback<CommandErrorSetter>(
    (message, recoveryActions = []) => {
      setExecutionAskError(message);
      setExecutionAskRecoveryActions(message === null ? [] : recoveryActions);
    },
    [],
  );

  const setInputCommandError = useCallback<CommandErrorSetter>(
    (message, recoveryActions = []) => {
      setInputError(message);
      setInputRecoveryActions(message === null ? [] : recoveryActions);
    },
    [],
  );

  const setTaskTreeCommandFailure = useCallback<CommandErrorSetter>(
    (message, recoveryActions = []) => {
      setTaskTreeCommandError(message);
      setTaskTreeCommandRecoveryActions(
        message === null ? [] : recoveryActions,
      );
    },
    [],
  );

  const resetCommandErrorState = useCallback(() => {
    setAuthoringAskError(null);
    setAuthoringAskRecoveryActions([]);
    setConfirmationError(null);
    setConfirmationRecoveryActions([]);
    setExecutionAskError(null);
    setExecutionAskRecoveryActions([]);
    setInputError(null);
    setInputRecoveryActions([]);
    setTaskTreeCommandError(null);
    setTaskTreeCommandRecoveryActions([]);
  }, []);

  return {
    authoringAskError,
    authoringAskRecoveryActions,
    confirmationError,
    confirmationRecoveryActions,
    executionAskError,
    executionAskRecoveryActions,
    inputError,
    inputRecoveryActions,
    taskTreeCommandError,
    taskTreeCommandRecoveryActions,
    resetCommandErrorState,
    setAuthoringAskCommandError,
    setConfirmationCommandError,
    setExecutionAskCommandError,
    setInputCommandError,
    setTaskTreeCommandError,
    setTaskTreeCommandFailure,
  };
}
