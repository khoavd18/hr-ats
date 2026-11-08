---
name: frontend-engineer
description: Build, fix and review web and mobile user interfaces in the project's framework, such as React, Next.js, Vue, Nuxt, Angular, Svelte, React Native or Flutter. Use when creating or refactoring components and pages; managing state and data fetching; building forms with validation; handling loading, empty and error states; making UI accessible (keyboard, screen readers, contrast); responsive layout; internationalization and Vietnamese text; client-side performance (bundle size, rendering, images); or debugging UI bugs in the browser. Not for server endpoints (use backend-api-engineer) or for test strategy across the stack (use software-testing).
---

# Frontend Engineer

Ships UI that matches the existing design system, works with a keyboard and a slow network, and never leaks secrets to the browser.

## Inputs

- The feature or bug, designs or screenshots, the API contract the UI consumes, target browsers and devices.
- Design tokens, accessibility level and performance budgets: from the project, otherwise `UNKNOWN`.

## Procedure

1. **Detect the stack**: framework and version, router, state library, styling system (CSS modules, Tailwind, component library), API client, build tool, lint and test setup. Reuse existing components before writing new ones.
2. **Model the states**: for each view, list loading, empty, error, partial and success states and the data each needs.
3. **Components**: small, typed props, presentational vs data-fetching separation following the codebase's pattern; no business rules duplicated from the backend without a reason.
4. **Data**: fetch through the existing client; handle cancellation, retries and stale data; never trust client-side checks for security.
5. **Forms**: field-level validation mirroring server rules, clear error messages, disabled submit while pending, server errors mapped to fields.
6. **Accessibility**: semantic elements, labels, focus management for dialogs, keyboard paths, contrast. Checklist in [frontend-checklist.md](references/frontend-checklist.md).
7. **Performance**: measure (Lighthouse, Web Vitals, React Profiler) before optimizing; code-split routes, size images, avoid unnecessary re-renders.
8. **Test**: component tests for logic and states, a few end-to-end tests for critical flows (**software-testing**).
9. **Verify in a browser**: check the actual page at the target widths and in the error states.

## Rules

- No API keys or secrets in client code or public environment variables; anything shipped to the browser is public.
- Never render untrusted HTML without sanitization; avoid `dangerouslySetInnerHTML` / `v-html` on user content.
- Follow the existing design system; do not introduce a new UI library for one component.
- Text visible to users goes through the project's i18n mechanism if it has one.
- Apply the [engineering quality contract](../software-testing/references/engineering-quality-contract.md).

## Outputs

Components and pages in the project's style, state handling for every view state, accessibility notes, tests, and screenshots or a description of what was checked in the browser.

## Hand-offs

API changes → **backend-api-engineer**. Test strategy → **software-testing**. Security review of auth flows → **secure-code-review**.
