import type { CSSProperties, ReactNode } from "react";

import { cx } from "../../utils/cx";
import styles from "./MarkdownContent.module.css";
import { isSafeMarkdownUrl } from "./markdownUrl";

export type MarkdownContentVariant = "conversation" | "activity" | "detail";

export type MarkdownContentProps = {
  className?: string;
  maxLines?: number;
  source: string;
  title?: string;
  variant?: MarkdownContentVariant;
};

type MarkdownBlock =
  | { depth: number; text: string; type: "heading" }
  | { language: string | null; text: string; type: "code" }
  | { ordered: boolean; items: string[]; type: "list" }
  | { rows: string[][]; header: string[]; type: "table" }
  | { text: string; type: "blockquote" }
  | { text: string; type: "paragraph" };

export function MarkdownContent({
  className,
  maxLines,
  source,
  title,
  variant = "detail",
}: MarkdownContentProps) {
  const blocks = parseMarkdownBlocks(source);
  const style =
    maxLines === undefined
      ? undefined
      : ({
          "--plato-markdown-max-lines": String(maxLines),
        } as CSSProperties);

  return (
    <div
      className={cx(
        styles.root,
        styles[variant],
        maxLines !== undefined && styles.preview,
        className,
      )}
      style={style}
      title={title}
    >
      {renderBlocks(blocks, "markdown")}
    </div>
  );
}

function parseMarkdownBlocks(source: string): MarkdownBlock[] {
  const lines = source.replace(/\r\n?/gu, "\n").split("\n");
  const blocks: MarkdownBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index] ?? "";

    if (isBlank(line)) {
      index += 1;
      continue;
    }

    const fence = line.match(/^\s*```([a-z0-9_-]+)?\s*$/iu);
    if (fence) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !/^\s*```\s*$/u.test(lines[index] ?? "")) {
        codeLines.push(lines[index] ?? "");
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      blocks.push({
        language: fence[1] ?? null,
        text: codeLines.join("\n"),
        type: "code",
      });
      continue;
    }

    if (isTableStart(lines, index)) {
      const header = parseTableRow(lines[index] ?? "");
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && isTableRow(lines[index] ?? "")) {
        rows.push(parseTableRow(lines[index] ?? ""));
        index += 1;
      }
      blocks.push({ header, rows, type: "table" });
      continue;
    }

    const heading = line.match(/^\s{0,3}(#{1,4})\s+(.+?)\s*#*\s*$/u);
    if (heading) {
      blocks.push({
        depth: heading[1].length,
        text: heading[2],
        type: "heading",
      });
      index += 1;
      continue;
    }

    const quote = line.match(/^\s*>\s?(.*)$/u);
    if (quote) {
      const quoteLines: string[] = [];
      while (index < lines.length) {
        const quoteLine = (lines[index] ?? "").match(/^\s*>\s?(.*)$/u);
        if (!quoteLine) {
          break;
        }
        quoteLines.push(quoteLine[1]);
        index += 1;
      }
      blocks.push({ text: quoteLines.join("\n"), type: "blockquote" });
      continue;
    }

    const list = parseList(lines, index);
    if (list !== null) {
      blocks.push({
        items: list.items,
        ordered: list.ordered,
        type: "list",
      });
      index = list.nextIndex;
      continue;
    }

    const paragraphLines: string[] = [];
    while (
      index < lines.length &&
      !isBlank(lines[index] ?? "") &&
      !isBlockStart(lines, index)
    ) {
      paragraphLines.push((lines[index] ?? "").trim());
      index += 1;
    }
    blocks.push({
      text: paragraphLines.join(" "),
      type: "paragraph",
    });
  }

  return blocks;
}

function renderBlocks(blocks: MarkdownBlock[], keyPrefix: string): ReactNode[] {
  return blocks.map((block, index) => {
    const key = `${keyPrefix}-${index}`;
    switch (block.type) {
      case "heading": {
        const Heading = headingTag(block.depth);
        return (
          <Heading key={key}>
            {renderInline(block.text, `${key}-heading`)}
          </Heading>
        );
      }
      case "code":
        return (
          <pre key={key}>
            <code data-language={block.language ?? undefined}>{block.text}</code>
          </pre>
        );
      case "list": {
        const List = block.ordered ? "ol" : "ul";
        return (
          <List key={key}>
            {block.items.map((item, itemIndex) => (
              <li key={`${key}-item-${itemIndex}`}>
                {renderInline(item, `${key}-item-${itemIndex}`)}
              </li>
            ))}
          </List>
        );
      }
      case "table":
        return (
          <div className={styles.tableScroll} key={key}>
            <table>
              <thead>
                <tr>
                  {block.header.map((cell, cellIndex) => (
                    <th key={`${key}-head-${cellIndex}`}>
                      {renderInline(cell, `${key}-head-${cellIndex}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {block.rows.map((row, rowIndex) => (
                  <tr key={`${key}-row-${rowIndex}`}>
                    {normalizeTableRow(row, block.header.length).map(
                      (cell, cellIndex) => (
                        <td key={`${key}-cell-${rowIndex}-${cellIndex}`}>
                          {renderInline(
                            cell,
                            `${key}-cell-${rowIndex}-${cellIndex}`,
                          )}
                        </td>
                      ),
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      case "blockquote":
        return (
          <blockquote key={key}>
            {renderBlocks(parseMarkdownBlocks(block.text), `${key}-quote`)}
          </blockquote>
        );
      case "paragraph":
        return (
          <p key={key}>{renderInline(block.text, `${key}-paragraph`)}</p>
        );
    }
  });
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let index = 0;
  let tokenIndex = 0;

  while (index < text.length) {
    const next = findNextInlineToken(text, index);
    if (next === -1) {
      nodes.push(text.slice(index));
      break;
    }
    if (next > index) {
      nodes.push(text.slice(index, next));
    }

    const token = parseInlineToken(text, next, `${keyPrefix}-${tokenIndex}`);
    if (token === null) {
      nodes.push(text[next]);
      index = next + 1;
      tokenIndex += 1;
      continue;
    }

    nodes.push(token.node);
    index = token.nextIndex;
    tokenIndex += 1;
  }

  return nodes;
}

function parseInlineToken(
  text: string,
  index: number,
  key: string,
): { nextIndex: number; node: ReactNode } | null {
  if (text[index] === "`") {
    const end = text.indexOf("`", index + 1);
    if (end > index + 1) {
      return {
        nextIndex: end + 1,
        node: <code key={key}>{text.slice(index + 1, end)}</code>,
      };
    }
  }

  if (text[index] === "[") {
    const labelEnd = text.indexOf("](", index + 1);
    const urlEnd = labelEnd === -1 ? -1 : text.indexOf(")", labelEnd + 2);
    if (labelEnd > index + 1 && urlEnd > labelEnd + 2) {
      const label = text.slice(index + 1, labelEnd);
      const href = text.slice(labelEnd + 2, urlEnd).trim();

      if (isSafeMarkdownUrl(href)) {
        return {
          nextIndex: urlEnd + 1,
          node: (
            <a href={href} key={key} rel="noreferrer noopener" target="_blank">
              {renderInline(label, `${key}-label`)}
            </a>
          ),
        };
      }

      return {
        nextIndex: urlEnd + 1,
        node: <span key={key}>{renderInline(label, `${key}-label`)}</span>,
      };
    }
  }

  if (text.startsWith("**", index)) {
    const end = text.indexOf("**", index + 2);
    if (end > index + 2) {
      return {
        nextIndex: end + 2,
        node: (
          <strong key={key}>
            {renderInline(text.slice(index + 2, end), `${key}-strong`)}
          </strong>
        ),
      };
    }
  }

  if (text.startsWith("__", index)) {
    const end = text.indexOf("__", index + 2);
    if (end > index + 2) {
      return {
        nextIndex: end + 2,
        node: (
          <strong key={key}>
            {renderInline(text.slice(index + 2, end), `${key}-strong`)}
          </strong>
        ),
      };
    }
  }

  if (text[index] === "*" && text[index + 1] !== "*") {
    const end = text.indexOf("*", index + 1);
    if (end > index + 1) {
      return {
        nextIndex: end + 1,
        node: (
          <em key={key}>
            {renderInline(text.slice(index + 1, end), `${key}-em`)}
          </em>
        ),
      };
    }
  }

  if (text[index] === "_" && text[index + 1] !== "_") {
    const end = text.indexOf("_", index + 1);
    if (end > index + 1) {
      return {
        nextIndex: end + 1,
        node: (
          <em key={key}>
            {renderInline(text.slice(index + 1, end), `${key}-em`)}
          </em>
        ),
      };
    }
  }

  return null;
}

function findNextInlineToken(text: string, startIndex: number): number {
  const positions = ["`", "[", "**", "__", "*", "_"]
    .map((token) => text.indexOf(token, startIndex))
    .filter((position) => position >= 0);

  return positions.length === 0 ? -1 : Math.min(...positions);
}

function headingTag(depth: number): "h3" | "h4" | "h5" | "h6" {
  if (depth <= 1) {
    return "h3";
  }
  if (depth === 2) {
    return "h4";
  }
  if (depth === 3) {
    return "h5";
  }
  return "h6";
}

function parseList(
  lines: string[],
  startIndex: number,
): { items: string[]; nextIndex: number; ordered: boolean } | null {
  const firstLine = lines[startIndex] ?? "";
  const ordered = /^\s*\d+[.)]\s+(.+)$/u.exec(firstLine);
  const unordered = /^\s*[-*+]\s+(.+)$/u.exec(firstLine);
  const first = ordered ?? unordered;

  if (!first) {
    return null;
  }

  const itemPattern = ordered
    ? /^\s*\d+[.)]\s+(.+)$/u
    : /^\s*[-*+]\s+(.+)$/u;
  const items: string[] = [];
  let index = startIndex;

  while (index < lines.length) {
    const match = itemPattern.exec(lines[index] ?? "");
    if (!match) {
      break;
    }
    let item = match[1].trim();
    index += 1;

    while (
      index < lines.length &&
      /^\s{2,}\S/u.test(lines[index] ?? "") &&
      !itemPattern.test(lines[index] ?? "")
    ) {
      item = `${item} ${(lines[index] ?? "").trim()}`;
      index += 1;
    }

    items.push(item);
  }

  return { items, nextIndex: index, ordered: Boolean(ordered) };
}

function isBlockStart(lines: string[], index: number): boolean {
  const line = lines[index] ?? "";
  return (
    /^\s*```/u.test(line) ||
    /^\s{0,3}#{1,4}\s+/u.test(line) ||
    /^\s*>\s?/u.test(line) ||
    /^\s*(?:[-*+]|\d+[.)])\s+/u.test(line) ||
    isTableStart(lines, index)
  );
}

function isBlank(line: string): boolean {
  return line.trim().length === 0;
}

function isTableStart(lines: string[], index: number): boolean {
  const current = lines[index] ?? "";
  const next = lines[index + 1] ?? "";
  const header = parseTableRow(current);
  return (
    header.length > 1 &&
    current.includes("|") &&
    parseTableRow(next).every((cell) => /^:?-{3,}:?$/u.test(cell)) &&
    parseTableRow(next).length === header.length
  );
}

function isTableRow(line: string): boolean {
  return line.includes("|") && parseTableRow(line).length > 1;
}

function parseTableRow(line: string): string[] {
  let source = line.trim();
  if (source.startsWith("|")) {
    source = source.slice(1);
  }
  if (source.endsWith("|")) {
    source = source.slice(0, -1);
  }
  return source.split("|").map((cell) => cell.trim());
}

function normalizeTableRow(row: string[], cellCount: number): string[] {
  return Array.from({ length: cellCount }, (_, index) => row[index] ?? "");
}
