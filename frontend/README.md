# TaskWeavn Frontend

Task-first UI prototype shell.

## Scope

This frontend is UI-only. It talks to the backend through the `TaskWeavnApi`
contract in `src/api/contracts.ts`. The first implementation uses
`MockTaskWeavnApi` so the UI can be developed before server endpoints exist.

## Planned Stack

- Vite
- React
- TypeScript
- TanStack Query
- TanStack Router later
- Zustand later for local UI state if needed
- lucide-react

## Local Commands

Install dependencies with a Node package manager, then run:

```bash
npm run dev
npm run check
npm run build
```

This environment currently has `node` available but no package manager, so the
initial scaffold was written without installing dependencies.

