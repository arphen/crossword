# User journeys

The complete inventory of what a user can do. **Every row has a Playwright test titled
`[<ID>] ...` that ends in at least one `toHaveScreenshot`.** The static audit
(`audit-static.mjs`) fails if a row has no test, and fails if a test has no row.

How to find every journey (do all of these before declaring the list complete):

- Every route or page in the router.
- Every `data-testid` and every button, link and form in the templates.
- Every modal, drawer, menu and toast, opened and closed.
- Every data state of every screen: loading, empty, one item, many items, error, offline.
- First run vs returning user; signed out vs signed in; any destructive confirmation.
- Each setting a user can change, and that it persists after a reload.
- The finish (success) path, the abandon path, and the failure path.

| ID | Journey | Starts at, ends at | States that are screenshotted |
| --- | --- | --- | --- |
| J1 | First view | open the app, rest state | lanes, ground, tiles |
| J2 | Select a clue | click a row, glow settles | one row selected |
| J3 | Dim the screen | open View panel, choose Dim, reload | panel open, dim applied, persisted |
| J4 | Reset the view | choose Veil, press Reset | defaults restored |
| J5 | Scroll a lane | scroll lane A to the end | territory light moved |

Design contracts (viewport x theme x view tier, keyboard focus, reduced motion) live in
`design.spec.mjs` with ids `D1` to `D3`; they are not journeys.
