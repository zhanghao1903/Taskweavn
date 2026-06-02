export const PLATO_NAVIGATION_EVENT = "plato:navigation";

export function navigateApp(path: string): void {
  globalThis.history.pushState(null, "", path);
  globalThis.dispatchEvent(new Event(PLATO_NAVIGATION_EVENT));
}
