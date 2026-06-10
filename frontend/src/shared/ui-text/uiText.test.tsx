import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PRODUCT_RECOVERY_ACTIONS } from "../api/productErrors";
import { enUS } from "./enUS";
import {
  getUiText,
  normalizeUiLocale,
  resolveUiLocale,
  UiTextProvider,
  useUiText,
} from "./index";
import { zhCN } from "./zhCN";

describe("UI system text catalog", () => {
  it("keeps en-US and zh-CN catalog keys in parity", () => {
    expect(catalogShape(zhCN)).toEqual(catalogShape(enUS));
  });

  it("covers every known product recovery action", () => {
    for (const action of PRODUCT_RECOVERY_ACTIONS) {
      expect(enUS.productError.recovery[action].label).toBeTruthy();
      expect(enUS.productError.recovery[action].description).toBeTruthy();
      expect(zhCN.productError.recovery[action].label).toBeTruthy();
      expect(zhCN.productError.recovery[action].description).toBeTruthy();
    }
  });

  it("normalizes supported language tags", () => {
    expect(normalizeUiLocale("zh")).toBe("zh-CN");
    expect(normalizeUiLocale("zh-Hans")).toBe("zh-CN");
    expect(normalizeUiLocale("zh_CN")).toBe("zh-CN");
    expect(normalizeUiLocale("en")).toBe("en-US");
    expect(normalizeUiLocale("en-GB")).toBe("en-US");
    expect(normalizeUiLocale("fr-FR")).toBe("en-US");
  });

  it("resolves locale deterministically from runtime and navigator inputs", () => {
    expect(
      resolveUiLocale({
        navigatorLanguages: ["zh-CN"],
        runtimeEnv: { VITE_PLATO_UI_LOCALE: "en-GB" },
      }),
    ).toBe("en-US");
    expect(
      resolveUiLocale({
        electronRuntimeLocale: "zh-Hans",
        navigatorLanguages: ["en-US"],
      }),
    ).toBe("zh-CN");
    expect(
      resolveUiLocale({
        explicitLocale: "fr-FR",
        navigatorLanguages: ["zh-CN"],
      }),
    ).toBe("en-US");
  });

  it("returns catalog text for each supported locale", () => {
    expect(getUiText("en-US").main.empty.noPlanTitle).toBe("No task plan yet");
    expect(getUiText("zh-CN").main.empty.noPlanTitle).toBe("还没有任务计划");
  });

  it("provides active locale text through React context", () => {
    render(
      <UiTextProvider locale="zh-CN">
        <Probe />
      </UiTextProvider>,
    );

    expect(screen.getByText("还没有任务计划")).toBeInTheDocument();
  });
});

function Probe() {
  const uiText = useUiText();
  return <div>{uiText.main.empty.noPlanTitle}</div>;
}

function catalogShape(value: unknown): unknown {
  if (typeof value === "function") {
    return "function";
  }
  if (Array.isArray(value)) {
    return value.map(catalogShape);
  }
  if (typeof value === "object" && value !== null) {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, child]) => [key, catalogShape(child)]),
    );
  }
  return typeof value;
}
