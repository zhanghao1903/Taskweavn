export function isSafeMarkdownUrl(value: string): boolean {
  const trimmed = value.trim();

  if (trimmed.length === 0 || containsControlOrWhitespace(trimmed)) {
    return false;
  }

  const schemeMatch = /^[a-z][a-z0-9+.-]*:/iu.exec(trimmed);
  if (!schemeMatch) {
    return (
      trimmed.startsWith("#") ||
      trimmed.startsWith("/") ||
      trimmed.startsWith("./") ||
      trimmed.startsWith("../")
    );
  }

  try {
    const protocol = new URL(trimmed).protocol;
    return protocol === "https:" || protocol === "http:" || protocol === "mailto:";
  } catch {
    return false;
  }
}

function containsControlOrWhitespace(value: string): boolean {
  for (const character of value) {
    const code = character.charCodeAt(0);
    if (code <= 0x1f || code === 0x7f || character.trim() === "") {
      return true;
    }
  }

  return false;
}
