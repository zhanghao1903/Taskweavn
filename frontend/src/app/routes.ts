export const routes = {
  main: "/",
} as const;

export type AppRoute = (typeof routes)[keyof typeof routes];
