import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarkdownContent } from "./MarkdownContent";
import { isSafeMarkdownUrl } from "./markdownUrl";

describe("MarkdownContent", () => {
  it("renders common markdown blocks and inline formatting", () => {
    render(
      <MarkdownContent
        source={[
          "# Result ready",
          "",
          "Use **React** with _Vite_ and `npm run dev`.",
          "",
          "- Write the page",
          "- Verify the build",
          "",
          "| File | Status |",
          "| --- | --- |",
          "| README.md | changed |",
          "",
          "```ts",
          "const ok = true;",
          "```",
          "",
          "[Open docs](https://example.com/docs)",
        ].join("\n")}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Result ready" }),
    ).toBeInTheDocument();
    expect(screen.getByText("React").tagName).toBe("STRONG");
    expect(screen.getByText("Vite").tagName).toBe("EM");
    expect(screen.getByText("npm run dev").tagName).toBe("CODE");
    expect(screen.getByText("Write the page")).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("README.md")).toBeInTheDocument();
    expect(screen.getByText("const ok = true;").tagName).toBe("CODE");
    expect(screen.getByRole("link", { name: "Open docs" })).toHaveAttribute(
      "href",
      "https://example.com/docs",
    );
  });

  it("renders raw HTML as inert text", () => {
    const { container } = render(
      <MarkdownContent source={'<script>alert("x")</script><img src=x>'} />,
    );

    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText(/<script>alert/)).toBeInTheDocument();
  });

  it("rejects unsafe markdown link URLs", () => {
    render(
      <MarkdownContent
        source={[
          "[Unsafe](javascript:alert(1))",
          "[Safe](./relative-path)",
        ].join(" ")}
      />,
    );

    expect(screen.queryByRole("link", { name: "Unsafe" })).not.toBeInTheDocument();
    expect(screen.getByText("Unsafe")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Safe" })).toHaveAttribute(
      "href",
      "./relative-path",
    );
  });

  it("renders nested blockquote content safely", () => {
    render(<MarkdownContent source={"> **Why:** keep the plan visible."} />);

    const quote = screen.getByText("Why:").closest("blockquote");
    expect(quote).toBeInTheDocument();
    expect(within(quote as HTMLElement).getByText("Why:").tagName).toBe(
      "STRONG",
    );
  });

  it("uses an explicit URL allowlist", () => {
    expect(isSafeMarkdownUrl("https://example.com")).toBe(true);
    expect(isSafeMarkdownUrl("http://example.com")).toBe(true);
    expect(isSafeMarkdownUrl("mailto:user@example.com")).toBe(true);
    expect(isSafeMarkdownUrl("/local/path")).toBe(true);
    expect(isSafeMarkdownUrl("#section")).toBe(true);
    expect(isSafeMarkdownUrl("javascript:alert(1)")).toBe(false);
    expect(isSafeMarkdownUrl("data:text/html;base64,AAAA")).toBe(false);
  });
});
