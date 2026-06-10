import { describe, expect, it } from "vitest";

import {
  mainPageSnapshotIdentity,
  mainPageSnapshotQueryKey,
} from "./adapter";
import { getMainPageMockSnapshot } from "../mockPlatoApi";

describe("MainPage runtime adapter helpers", () => {
  it("keys mock snapshots by fixture state id", () => {
    expect(
      mainPageSnapshotQueryKey(
        { runtimeKind: "mock", sessionId: null },
        "s3-draft-ready",
      ),
    ).toEqual(["main-page", "fixture", "s3-draft-ready"]);
  });

  it("keys HTTP snapshots by session id", () => {
    expect(
      mainPageSnapshotQueryKey(
        { runtimeKind: "http", sessionId: "session-live" },
        "s3-draft-ready",
      ),
    ).toEqual([
      "main-page",
      "snapshot",
      "current-workspace",
      "session-live",
    ]);
  });

  it("keeps HTTP local-state identity stable across fixture-like state ids", () => {
    const snapshot = getMainPageMockSnapshot("s3-draft-ready");

    expect(
      mainPageSnapshotIdentity(
        { runtimeKind: "http", sessionId: "session-live" },
        "s3-draft-ready",
        snapshot,
      ),
    ).toBe("workspace:current:session:session-live");
    expect(
      mainPageSnapshotIdentity(
        { runtimeKind: "http", sessionId: "session-live" },
        "s7-confirmation",
        snapshot,
      ),
    ).toBe("workspace:current:session:session-live");
  });
});
