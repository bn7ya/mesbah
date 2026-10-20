# The Interface

How a screen in this project is composed, and why. `design-pattern.md` says where code goes;
`language.md` says how words are written; this says how the thing looks and answers back.

It is not a style guide argued one stylesheet at a time. The controls, the palette, the type
scale and the control states are decided once — by Angular Material, themed in
`src/styles/_theme.scss`, with the spacing scale in `_tokens.scss` and element defaults in
`_base.scss` — and the job of this document is to say what those decisions are, so that a
screen is *composed* out of them rather than argued into existence.

`interface_designer` owns this document and those three files. `unifier` audits against it.

---

## 1. Signifiers and feedback

**Every interactive element has to look interactive, and every action has to answer.**

A control needs at least four states — resting, hover, focus, pressed — plus disabled where
it can be, and busy where it waits. A field needs focus, error, and disabled. Angular
Material's components carry all of them — the state layer for hover, focus and pressed, the
disabled treatment, the field's error colour — which is the strongest reason to reach for
the Material component rather than styling a `<div>` with a click handler. A control
Material lacks is built once in `shared/` on the CDK, with the same states.

**Never remove the focus ring.** `mat.strong-focus-indicators()` draws one on every Material
control and `_base.scss` draws the same ring on everything else, in `--mat-sys-primary`. A
component that writes its own `outline` or `box-shadow` on `:focus-visible` *replaces* it
rather than adding to it — silently, and still looking like a focus ring, which is what makes
it hard to catch. The correct amount of focus CSS in a feature stylesheet is none.

**Every action gets a response.** A submit shows its busy state — `aria-busy="true"` and
`[disabled]` on the button, and its label says what is happening. A failure the user must
read says so in the page, in an element with `role="alert"`; a short outcome that needs no
answer is a `MatSnackBar`. A destructive action asks first, in a `MatDialog` — never
`confirm()`. A list that is loading shows its shape, not emptiness. Silence after a click
reads as a broken button, and the user's next move is to click it again.

The first feature that needs a confirmation builds one dialog component on `MatDialog` in
`shared/`, once, and every later feature opens that.

**The pieces that carry a state are drawn once, in `shared/`.** A message in a box is
`<app-note>` — `kind="error"` for a failure (`role="alert"`), the default for a hint. A list, a
table or a panel with nothing in it is `<app-empty-state>`. A state or a tag is `<app-status>`
— an icon and a word, in the accent, the error colour or the secondary tone — and whether a model
fits is `<app-fit-verdict>`. A command or an address is `<app-code-block>`: monospace, wrapped
inside its block. A feature that draws its own box for any of these has made a second one.

**State is never carried by colour alone.** A failure is an icon *and* text *and* the tone:
the sign-in page sets a `fa-circle-exclamation` beside the words on
`--mat-sys-error-container`. A field in error has `aria-invalid="true"`, the error colour,
and the reason in its `<mat-error>` — which `matInput` links by `aria-describedby` and the
field announces through its `aria-live` subscript, so a screen reader hears it too. A chosen
toggle shows a check as well as a fill.

---

## 2. Hierarchy

**The most important thing on the screen is the largest thing on the screen.** If the page
title and a helper label set at the same size, the page is wrong.

Work down from the one thing the screen exists for. Each level of importance drops a type
step or gains a weight; two adjacent levels never read the same. Hierarchy comes from size,
weight and position — and from restraint: if everything is emphasised, nothing is.

**Group by proximity, deliberately.** Elements that are one thing sit one step apart;
separate groups sit two or three apart. The gaps carry as much meaning as the words, and a
uniform gap everywhere tells the reader nothing. The sign-in card is the worked example:
title and subtitle at `--app-space-2`, one field to the next at the field's own error line
plus `--app-space-2`, one section of the card to the next at `--app-space-7`.

**Replace text with form where form is clearer** — a direction arrow between two places
rather than the words "from" and "to". But an icon that needs a legend is worse than the
word it replaced, and an icon-only control always carries an `aria-label`.

---

## 3. Type

**Material's type scale, and exactly three weights.** Five roles — display, headline,
title, body, label — in large, medium and small, each a `font` shorthand token:
`--mat-sys-headline-medium`, `--mat-sys-body-large`, `--mat-sys-label-large`. Each carries
its size, weight and leading together, so a step is applied whole with
`font: var(--mat-sys-title-medium)`, never assembled from parts. The weights are the theme's
regular, medium and bold — 400, 500, 700. The steps are in `rem`, so the reader's browser
setting still scales them.

**Use the element, not a size.** `_base.scss` sets four heading steps and nothing else sets one:

| Element | Step | It names |
|---|---|---|
| `<h1>` | `headline-medium` | the page; on a project's tabs, the project |
| `<h2>` | `title-large` | a section of a page, above its card; a run, under its project |
| `<h3>` | `title-medium` | a card or a row in a list; a group of fields in a card; a section of a run |
| `<h4>` | `title-small` | a label inside a group |

Body text is `body-large`; secondary text is `class="text-secondary"`:

```html
<h1>{{ 'orders.title' | t }}</h1>
<p class="text-secondary">{{ 'orders.subtitle' | t }}</p>
```

**Depth sets size.** A heading is one step below the heading it sits under, so the element is
chosen by depth and the size follows. A section's title sits above its card, never inside it.
A project's tabs carry no title of their own — the tab label already says where you are — so
each section is an `<h2>` straight under the tabs, as on Overview. A caption over a list
("Ready designs", "Popular models") is a label, `label-large` in the secondary tone, not a
heading level: the names beneath it stay the largest thing in the group. A feature that
re-declares a heading's `font` has started a second scale.

**One family.** The theme sets Tajawal, self-hosted, with matched Arabic and Latin designs,
in every type token, so a mixed sentence does not fall between two fonts. Three weights ship
— 400, 500, 700 — and they are the only three a screen uses.

**Arabic sets at `letter-spacing: 0`, always.** The general advice to tighten headline
tracking by 2–3 % is true for Latin and actively wrong for Arabic, which is connected: the
tracking breaks the joins. Material's type scale tracks its body and label steps, so
`_theme.scss` overrides every `--mat-sys-*-tracking` to zero under `:lang(ar)`, and
`_base.scss` does the same for plain text. Do not reintroduce tracking, italics or
capitalisation on Arabic text.

---

## 4. Space

**A 4-px grid.** `--app-space-1` through `--app-space-10` — 0.25, 0.5, 0.75, 1, 1.25, 1.5, 2,
2.5, 3 and 4 rem (4 to 64 px). A value that is not on the scale is a bug, not a preference,
and the hook blocks raw px in feature styles.

(Advice elsewhere says "multiples of 4 or 8". This scale is 4, and mixing the two produces a
scale with holes in it. Use the scale.)

**Insets are equal or 1:2.** A card pads equally on every side — a section's `mat-card` takes
`--app-space-6`, a card that is one row of a list `--app-space-5`. A control's inline padding is
about double its block padding, and Material's buttons and fields already are; a feature does
not re-pad them.

**The page has one rhythm.** The sections of a page sit `--app-space-8` apart. A section's title
sits `--app-space-3` above its content, and `--app-space-2` above its lead line. An action beside
a title (New project, Add member) aligns to the top of the heading block, not the bottom.

**Let it breathe, then stop.** Whitespace is how grouping is expressed (§2). It is not a
quality in itself, and a screen the user has to scroll to see two fields is not airy, it is
padded.

---

## 5. Colour and the two schemes

**One accent.** `--mat-sys-primary` is the brand gold and it means *primary action*; its
palette is generated from `#7a5c12` into `_theme-colors.scss`, and regenerated, never
hand-edited. `--mat-sys-error` and its container pair mean danger and nothing else. A new
semantic colour — success, warning — is a theme decision with both schemes, never a hex in a
feature. Links take the accent and stay underlined, so they do not depend on hue.

**Two text tones per scheme, and never opacity.** `--mat-sys-on-surface` and
`--mat-sys-on-surface-variant`. Faded text is not a third tone; it is a contrast failure
with extra steps. Material's tonal palettes hold both to 4.5:1 against every surface.

**Depth comes from tone first.** `--mat-sys-surface` is the page; the
`--mat-sys-surface-container-*` steps are what sits on it, and a raised `mat-card` reads as
raised because it is a different step. Hairlines in `--mat-sys-outline-variant` appear where
tone alone cannot separate two things.

**Both schemes are live and both are designed.** `color-scheme: light dark` follows the
operating system, and the theme's `theme-type: color-scheme` gives every `--mat-sys-*` colour
both values through `light-dark()`. So: **repaint the page in the other scheme, do not
reason about it.** The failures here are never the ones you predict.

In dark, elevation is a lighter surface, not a heavier shadow — a shadow on a dark ground is
invisible, and reaching for a stronger one produces a grey smudge. Keep chroma down on dark
fills, because a saturated accent that reads well on white glares on near-black.

---

## 6. Depth

**Shadows are subtle, and they say height, not weight.** Material's elevation levels,
`--mat-sys-level0` to `--mat-sys-level5`, are the only shadows; its components already pick
theirs — a raised card at level 1, a menu at level 2, a dialog higher. What separates them is
how far the light travels, not how dark it gets. If the shadow is the first thing you notice,
it is too strong.

A flat card on a page needs almost none — the tone step is already doing the work. A dialog
over a backdrop needs the most, because it has the furthest to come. A feature-local
`box-shadow` is a third system; use a level.

---

## 7. Icons, buttons, images

**Icons are Font Awesome 7 Free**, bundled from npm (ADR-009), drawn through `<mat-icon>`,
whose default font set is `fa-solid`:

```html
<mat-icon fontIcon="fa-circle-exclamation" />
```

**An icon sits in Material's icon box.** `mat-icon` reserves `--app-icon-box`, and
`_theme.scss` sets the glyph at `--app-icon-size` in the middle of it, the optical size of
the icons Material's own buttons and fields are drawn around. Beside small label text, such as a
mark in a message footer, `class="app-icon-small"` gives the glyph a smaller box
(`--app-icon-box-small`), set in the theme.

**Directional glyphs mirror, or they are not directional.** Font Awesome does not flip
itself — so prefer a glyph with no direction, and where direction is the point, add
`class="mat-icon-rtl-mirror"`, which Material flips under `[dir=rtl]`. A chevron pointing the
wrong way in Arabic is the single most common RTL bug and the easiest to catch.

**An icon is never the button.** Put the behaviour on a `matIconButton` or `matButton`;
`mat-icon` is `aria-hidden` by default; give an icon-only button a translated `aria-label`.

**Keyboard patterns come from Material** — `mat-menu`, `mat-tab-group`, `mat-select`,
`mat-selection-list` — and from the CDK where Material has none. A one-of-several choice is
a `mat-button-toggle-group`, as the language switch is.

**Text over an image needs a gradient, not a hope.** A linear-gradient overlay resolving into
a solid background, so the text is readable over the brightest part of the picture rather
than the part the designer happened to be looking at.

---

## 8. Layout and breakpoints

**Breakpoints are viewport media queries**, from `_layout.scss`:

```scss
@use "layout" as *;

.orders {
  @include from($screen-md) { grid-template-columns: 1fr 1fr; }
}
```

`$content-max` and `$card-max` cap widths. A component that has to answer to its own width
rather than the viewport may use a container query inside itself. Spacing and direction are
logical properties throughout — `padding-inline`, `inset-inline-start`, `text-align: start`.

---

## 9. Reviewing a screen

In this order, because each answer changes the next:

1. What is this screen for? Is that thing the largest thing on it?
2. Does every gap mean something, or are they all the same?
3. Does every interactive element look interactive, and does every action answer?
4. Repaint it in the other scheme. Then at 390 px. Then in Arabic.
5. Tab through it. Does focus go where reading goes, and is the ring always visible?
6. Is any state carried by colour alone?
7. Is there a raw value anywhere that should have been a token, or a Material component
   restyled outside `_theme.scss`?

`/ui-review` runs this and reports what it finds.
