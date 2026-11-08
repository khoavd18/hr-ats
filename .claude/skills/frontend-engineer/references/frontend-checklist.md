# Frontend Checklist

## Stack detection

| Evidence | Stack |
|---|---|
| `next.config.*`, `app/` or `pages/` | Next.js (check App vs Pages Router) |
| `vite.config.*` + React/Vue/Svelte | Vite SPA |
| `angular.json` | Angular |
| `nuxt.config.*` | Nuxt |
| `app.json` with `expo`, `react-native` | React Native / Expo |
| `pubspec.yaml` | Flutter |

## View states

| State | Show |
|---|---|
| Loading | Skeleton or spinner; keep layout stable |
| Empty | Explanation and the next action |
| Error | What failed, retry, no raw stack traces |
| Partial | Data that loaded, with clear markers for missing parts |
| Success | The content |

## Accessibility (WCAG-oriented basics)

- Interactive elements are buttons/links, not clickable `div`s.
- Every input has a label; errors are announced (`aria-describedby`, live regions).
- Dialogs trap focus and return it on close; `Esc` closes.
- Visible focus indicator; logical tab order.
- Text contrast meets the target level; information is not conveyed by color alone.
- Images have meaningful `alt` or empty `alt` when decorative.

## Performance

| Symptom | Check |
|---|---|
| Slow first load | Bundle analyzer, route code-splitting, image sizes and formats |
| Janky typing/scrolling | Re-renders (profiler), expensive computations in render, large lists without virtualization |
| Layout shift | Reserved space for images and async content |

## Security in the browser

- Tokens: prefer httpOnly cookies managed by the backend; never store long-lived secrets in localStorage.
- Sanitize any HTML from users or CMS before rendering.
- Respect CSP; do not add `unsafe-inline` to make something work.
