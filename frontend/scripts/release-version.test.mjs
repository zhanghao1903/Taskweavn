import { describe, expect, it } from "vitest";

import {
  normalizeReleaseVersion,
  toDarwinBundleVersion,
  toPackageVersion,
} from "./release-version.mjs";

describe("release version helpers", () => {
  it("maps beta release labels to npm and macOS bundle versions", () => {
    const releaseVersion = normalizeReleaseVersion("1.1-beta");
    const packageVersion = toPackageVersion(releaseVersion);

    expect(releaseVersion).toBe("1.1-beta");
    expect(packageVersion).toBe("1.1.0-beta");
    expect(toDarwinBundleVersion(packageVersion)).toBe("1.1.0");
  });

  it("preserves explicit patch versions", () => {
    const releaseVersion = normalizeReleaseVersion("1.1.2-beta.1");
    const packageVersion = toPackageVersion(releaseVersion);

    expect(packageVersion).toBe("1.1.2-beta.1");
    expect(toDarwinBundleVersion(packageVersion)).toBe("1.1.2");
  });

  it("rejects labels that are unsafe for release asset names", () => {
    expect(() => normalizeReleaseVersion("v1.1-beta")).toThrow();
    expect(() => normalizeReleaseVersion("1.1 beta")).toThrow();
    expect(() => normalizeReleaseVersion("../1.1-beta")).toThrow();
  });
});
