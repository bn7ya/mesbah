---
name: ui-review
description: Reviews a screen against the interface standard — hierarchy, states, type, space, colour, depth, icons — and reports what is broken with the token-level fix. Use after a page or component exists and before it is called done, whenever a screen feels cramped, flat or arbitrary, and whenever raw values or a hand-rolled focus ring may have crept into feature styles. Not for writing copy, changing behaviour, or building the screen in the first place.
---

# Reviewing a screen

Read `.claude/docs/interface.md` first. It is the standard; this is the procedure.

You are looking at a screen the way someone who has never seen it will. Findings name the
rule they break and the token that fixes them, because "this feels cramped" is not something
anyone can act on.

## 1. Get it on screen

```bash
docker compose up --watch          # or: cd frontend && npx ng serve
```

Screenshot it in all six combinations before reading any code: **en and ar**, × **light and
dark**, × **1280 and 390**. Half the findings arrive here and nowhere else — a scheme nobody
repainted, a control that collapsed at phone width, an Arabic ascender clipped by a line
height that was set for Latin.

Drive Playwright with `colorScheme` and `locale` on the context. Switch the language through
the application's own switcher rather than the URL, so `LocaleStore` actually sets `lang` and
`dir` on the document.

## 2. Ask the seven questions

From `interface.md` §9, in order, because each answer changes the next:

1. What is this screen for? Is that thing the largest thing on it?
2. Does every gap mean something, or are they all the same?
3. Does every interactive element look interactive, and does every action answer?
4. Does it hold in the other scheme, at 390 px, in Arabic?
5. Does tab order follow reading order, and is the ring always visible?
6. Is any state carried by colour alone?
7. Is there a raw value that should have been a token?

## 3. Then read the stylesheets

Now, not before — code read first tells you what the author meant, and you are here to see
what the reader gets.

```bash
grep -rn "px\|#[0-9a-fA-F]\{3,6\}\|outline:" frontend/src/app --include=*.scss
grep -rn "margin-left\|margin-right\|padding-left\|padding-right\|left:\|right:\|text-align: *\(left\|right\)" frontend/src/app --include=*.scss
grep -rn "font-size\|font-weight\|box-shadow\|border-radius" frontend/src/app --include=*.scss
```

The three sweeps, in order: raw values and hand-rolled focus rings (rules 12 and 9), physical
properties that will break RTL (rule 22b), and a feature re-declaring what `_base.scss` or the
Material theme already decide — a heading's size, a button's radius, a card's shadow, a
selector reaching into `.mat-mdc-*`. That last one is a second system starting; the fix is
the element, the Material component or a `mat.<component>-overrides()` in `_theme.scss`, not
a closer value.

```bash
grep -rn "mat-mdc-\|::ng-deep" frontend/src/app --include=*.scss
```

## 4. Check what only a browser knows

- A Font Awesome glyph that points somewhere — a chevron, an arrow — and does not flip in
  Arabic. Look at it in `ar`, not in the source.
- A field error that shows on screen but is never announced. Submit the form empty with a
  screen reader on: the message belongs in a `<mat-error>` inside the `mat-form-field`, so
  `matInput` sets `aria-invalid` and `aria-describedby` and the field's subscript announces
  it. Text placed beside the field instead is silent.
- A component `box-shadow` on `:focus-visible` replaces the document's focus ring instead of
  adding to it. It still looks like a ring. Tab to it and compare against another control.

## 5. Fix, or hand it back

Fix what is yours: tokens, spacing, type, states, logical properties. Hand back what is not —
markup that makes correct proportion impossible goes to `angular_engineer`, wording goes to
`copywriter`, Arabic goes to `translator`.

A change to the theme, a component override or a token in `_theme.scss` or `_tokens.scss`
reaches every screen in the app. Make it as a decision for the whole app, and say so in the
report — never as a quiet fix for one page.

## Never

- Never judge a screen from its source. Look at it.
- Never report "feels cramped". Name the element, the rule and the token.
- Never add an `outline` to make focus "clearer". The document already has one.
- Never invent a value between two steps of the scale. If the screen genuinely needs one, that
  is a finding about the scale, and a new token, not a feature-local number.
- Never fix RTL with `:dir(rtl)` when a logical property would do.

## Reporting

Group by severity, not by file. For each finding: where it is, which rule it breaks, and the
change. Then one line on what you did not change and why — a token change you proposed rather
than made, or a screen you could not reach.
