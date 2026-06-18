import type { SessionMessageView } from "../../shared/api/types";
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
      <MarkdownContent
        className={styles.conversationMessageBody}
        source={message.body}
        title={message.body}
        variant="conversation"
      />
    </article>
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
