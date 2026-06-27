import type {
  ConversationQuestionCardView,
  ConversationRouterTraceView,
  SessionMessageView,
} from "../../shared/api/types";
import {
  Badge,
  MarkdownContent,
  type BadgeTone,
} from "../../shared/components";
import { cx } from "../../shared/utils/cx";
import { selectMessageKindPresentation } from "./mainPageSelectors";
import styles from "./MainPage.module.css";

export type SessionMessageCardProps = {
  message: SessionMessageView;
};

export function SessionMessageCard({ message }: SessionMessageCardProps) {
  const kindPresentation = selectMessageKindPresentation(message.kind);
  const isUserMessage = isUserAuthoredMessage(message);
  const userIntent = isUserMessage ? selectUserMessageIntent(message) : null;

  return (
    <article
      className={cx(
        styles.conversationMessage,
        isUserMessage
          ? styles.userConversationMessage
          : styles.systemConversationMessage,
        userIntent?.className,
      )}
      data-session-message-id={message.id}
      tabIndex={-1}
    >
      <div className={styles.conversationMessageMeta}>
        {userIntent ? (
          <Badge size="sm" tone={userIntent.tone}>
            {userIntent.label}
          </Badge>
        ) : (
          <Badge size="sm" tone={kindPresentation.tone}>
            {kindPresentation.label}
          </Badge>
        )}
        <span>{isUserMessage ? "You" : message.title}</span>
        {!isUserMessage ? (
          <span>
            {message.taskNodeId ? "Task activity" : "Session activity"}
          </span>
        ) : null}
        <time
          className={styles.conversationMessageTime}
          dateTime={message.createdAt}
          title={formatConversationDateTime(message.createdAt)}
        >
          {formatConversationTime(message.createdAt)}
        </time>
      </div>
      {renderConversationContent(message)}
    </article>
  );
}

function renderConversationContent(message: SessionMessageView) {
  const render = message.conversationRender;
  if (
    render === null ||
    render === undefined ||
    render.protocolVersion !== "plato.conversation.render.v1"
  ) {
    return renderMarkdownMessageBody(message.body);
  }

  if (render.renderKind === "router_trace" && render.routerTrace) {
    return <RouterTrace trace={render.routerTrace} />;
  }

  if (render.renderKind === "question_card" && render.questionCard) {
    return <QuestionCard card={render.questionCard} />;
  }

  if (render.renderKind === "text" && render.text) {
    return renderMarkdownMessageBody(render.text.body);
  }

  return renderMarkdownMessageBody(message.body);
}

function renderMarkdownMessageBody(body: string) {
  return (
    <MarkdownContent
      className={styles.conversationMessageBody}
      source={body}
      title={body}
      variant="conversation"
    />
  );
}

function RouterTrace({ trace }: { trace: ConversationRouterTraceView }) {
  return (
    <div className={styles.routerTraceCard}>
      <p>{trace.explanation}</p>
      <dl>
        <div>
          <dt>Intent</dt>
          <dd>{formatToken(trace.intent)}</dd>
        </div>
        <div>
          <dt>Scope</dt>
          <dd>{formatToken(trace.scopeKind)}</dd>
        </div>
        <div>
          <dt>Effect</dt>
          <dd>{formatToken(trace.sideEffect)}</dd>
        </div>
        <div>
          <dt>Dispatch</dt>
          <dd>{formatToken(trace.dispatchTarget)}</dd>
        </div>
        <div>
          <dt>Outcome</dt>
          <dd>{formatToken(trace.outcomeStatus)}</dd>
        </div>
      </dl>
    </div>
  );
}

function QuestionCard({ card }: { card: ConversationQuestionCardView }) {
  const isPending = card.status === "pending";

  return (
    <div className={styles.conversationQuestionCard} data-router-ask-card>
      <div className={styles.conversationQuestionHeader}>
        <strong>{card.title}</strong>
        <Badge size="sm" tone={isPending ? "warning" : "neutral"}>
          {formatToken(card.status)}
        </Badge>
      </div>
      {card.body ? <p>{card.body}</p> : null}
      {card.questions.length > 0 ? (
        <div className={styles.conversationQuestionInputs}>
          {card.questions.map((question) => (
            <label key={question.id}>
              <span>
                {question.label}
                {question.required ? "" : " (optional)"}
              </span>
              <textarea
                disabled
                placeholder={question.inputHint ?? "Answer in the input box."}
                rows={2}
              />
            </label>
          ))}
        </div>
      ) : null}
      {card.options.length > 0 ? (
        <div className={styles.conversationQuestionOptions}>
          {card.options.map((option) => (
            <button disabled key={option.id} type="button">
              <span>{option.label}</span>
              {option.description ? <small>{option.description}</small> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

type UserMessageIntent = {
  className: string;
  label: string;
  tone: BadgeTone;
};

function isUserAuthoredMessage(message: SessionMessageView): boolean {
  return message.title.trim().toLocaleLowerCase().startsWith("user ");
}

function selectUserMessageIntent(message: SessionMessageView): UserMessageIntent {
  const text = `${message.title}\n${message.body}`.toLocaleLowerCase();

  if (
    /\b(user answer|user response|ask answered|answer submitted|provided answer)\b/u.test(
      text,
    )
  ) {
    return {
      className: styles.userAnswerConversationMessage,
      label: "Answer",
      tone: "success",
    };
  }

  if (
    /\b(retry requested|stop requested|requested stop|draft task tree published|publish requested|confirmed|confirmation resolved|cancelled|canceled|deferred|skip requested)\b/u.test(
      text,
    )
  ) {
    return {
      className: styles.userActionConversationMessage,
      label: "Action",
      tone: "warning",
    };
  }

  return {
    className: styles.userInputConversationMessage,
    label: "Input",
    tone: "blue",
  };
}

function formatConversationTime(value: string): string {
  const date = parseConversationDate(value);
  if (date === null) {
    return value;
  }

  const time = `${padDatePart(date.getHours())}:${padDatePart(
    date.getMinutes(),
  )}`;

  if (isSameLocalDate(date, new Date())) {
    return time;
  }

  return `${formatLocalDate(date)} ${time}`;
}

function formatConversationDateTime(value: string): string {
  const date = parseConversationDate(value);
  if (date === null) {
    return value;
  }

  return `${formatLocalDate(date)} ${padDatePart(
    date.getHours(),
  )}:${padDatePart(date.getMinutes())}`;
}

function parseConversationDate(value: string): Date | null {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date;
}

function isSameLocalDate(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}

function formatLocalDate(date: Date): string {
  return [
    date.getFullYear(),
    padDatePart(date.getMonth() + 1),
    padDatePart(date.getDate()),
  ].join("-");
}

function padDatePart(value: number): string {
  return String(value).padStart(2, "0");
}

function formatToken(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toLocaleUpperCase() + part.slice(1))
    .join(" ");
}
