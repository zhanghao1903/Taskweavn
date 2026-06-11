const releaseVersionPattern =
  /^(?<major>0|[1-9]\d*)\.(?<minor>0|[1-9]\d*)(?:\.(?<patch>0|[1-9]\d*))?(?<suffix>-[0-9A-Za-z][0-9A-Za-z.-]*)?(?<build>\+[0-9A-Za-z][0-9A-Za-z.-]*)?$/;

export function normalizeReleaseVersion(value) {
  const version = String(value ?? "").trim();
  if (version.length === 0 || /\s/.test(version) || version.includes("/")) {
    throw new Error(
      "--release-version must be a non-empty version label without whitespace or slashes",
    );
  }
  if (!releaseVersionPattern.test(version)) {
    throw new Error(
      "--release-version must look like 1.1, 1.1.0, 1.1-beta, or 1.1.0-beta.1",
    );
  }
  return version;
}

export function toPackageVersion(releaseVersion) {
  const match = releaseVersion.match(releaseVersionPattern);
  if (!match?.groups) {
    throw new Error(`Invalid release version: ${releaseVersion}`);
  }
  const patch = match.groups.patch ?? "0";
  return `${match.groups.major}.${match.groups.minor}.${patch}${match.groups.suffix ?? ""}${match.groups.build ?? ""}`;
}

export function toDarwinBundleVersion(packageVersion) {
  const match = packageVersion.match(/^(\d+)\.(\d+)\.(\d+)/);
  if (!match) {
    throw new Error(`Invalid package version: ${packageVersion}`);
  }
  return `${match[1]}.${match[2]}.${match[3]}`;
}
