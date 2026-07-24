import type { MainPageViewModel } from "../mainPageViewModel";
import type { MainPageController } from "../useMainPageController";
import type { ConversationAskInteraction } from "./conversationAskInteraction";

export function buildConversationAskInteraction(
  actions: MainPageController["actions"],
  viewModel: MainPageViewModel,
): ConversationAskInteraction {
  return {
    authoring:
      viewModel.mainWorkArea.kind === "authoringAsk"
        ? {
            commandError: viewModel.mainWorkArea.authoringAsk.commandError,
            commandRecoveryActions:
              viewModel.mainWorkArea.authoringAsk.commandRecoveryActions,
            isSubmitting: viewModel.mainWorkArea.authoringAsk.isSubmitting,
            rawTaskId: viewModel.mainWorkArea.authoringAsk.rawTaskId,
          }
        : null,
    execution:
      viewModel.detail.kind === "executionAsk"
        ? {
            askId: viewModel.detail.ask.id,
            commandError: viewModel.detail.commandError,
            commandRecoveryActions: viewModel.detail.commandRecoveryActions,
            isAnswering: viewModel.detail.isAnsweringAsk,
            isCancelling: viewModel.detail.isCancellingAsk,
            isDeferring: viewModel.detail.isDeferringAsk,
          }
        : null,
    onAnswerExecution: (askId, payload) =>
      actions.answerAsk({
        askId,
        selectedOptionIds: payload.selectedOptionIds,
        sessionId: viewModel.sessionId,
        text: payload.text,
      }),
    onCancelExecution: (askId) =>
      actions.cancelAsk({
        askId,
        reason: "user cancelled ASK",
        sessionId: viewModel.sessionId,
      }),
    onDeferExecution: (askId) =>
      actions.deferAsk({
        askId,
        reason: "user deferred ASK",
        sessionId: viewModel.sessionId,
      }),
    onSubmitAuthoring: (rawTaskId, answers) =>
      actions.answerAuthoringAskBatch({
        answers,
        rawTaskId,
        sessionId: viewModel.sessionId,
      }),
  };
}
