# Annotation Class Definitions — Reference for Expert Validation

Thank you for taking the time to look at this. This document accompanies a
sample of annotated master-layout images from ThemeSync, a system that
extracts a poster's visual theme (colors, logo placement, decorative style)
and reapplies it to a different document, such as a certificate or ID.
Before we develop that extraction step further, we'd really value an
outside, informed check on whether the bounding-box annotations on our
sample images match the class definitions below — a second set of eyes
beyond our own group.

We'd be grateful if you could look at whether each box correctly captures
the element it claims to, and whether anything seems miscategorized or
missing. No need for anything exhaustive — your honest impressions are what
we're after.

## What you're reviewing

Each image is a "master layout" — a generic branded design such as an event
poster, banner, letterhead, or social-media announcement graphic. On each
one, our group has drawn bounding boxes around specific visual elements and
labeled each box with one of four classes (defined below). We'd appreciate
you checking those boxes and labels against the definitions below, rather
than judging the poster's design quality itself.

## The four classes

| Class | What it should cover |
|---|---|
| **logo** | An institutional/organizational seal, crest, or logo graphic. The box should be tight around the visible graphic itself, not the surrounding whitespace. If a poster has more than one logo (e.g., a school seal plus a student council logo), each gets its own box. |
| **text** | One box per semantically distinct block of text — not per character or per line, and not one box around the whole page. For example, an event poster might have separate text boxes for the organization name, a sub-header, the event title, a tagline, a date/venue callout, and a footer contact line. Each of those is its own box. |
| **underlay** | A colored or shaded panel/bar placed directly behind a specific piece of text or a logo, to improve contrast or legibility — for example, a dark rounded rectangle sitting behind a tagline. This is **not** the poster's full background photo or illustration, no matter how large, colorful, or central it is to the design. A big illustrated scene or a plain background color is base artwork, not an underlay, and should not be boxed at all. |
| **embellishment** | Small decorative accents: thin decorative lines, small icons or dots, corner flourishes, or a social-media platform icon next to a handle. These are minor and intentionally not exhaustively annotated (please see the note below) — flagging one is only needed if it's clearly present and clearly unboxed, not every small mark on the page. |

**A key rule that applies across all four classes:** the full background
image or illustration of a poster is never boxed as anything. Only overlay
elements sitting on top of that background — a logo, a text block, a
contrast panel, a decorative accent — get boxes.

## What we're hoping you'll check

If you're willing, we'd appreciate a look at each of the following for the
boxes in the sample:

1. **Right class.** Does the label match the definitions above? (The most
   common mix-up to watch for: a large background illustration mislabeled
   as `underlay` — it shouldn't be boxed at all.)
2. **Tight fit.** Does the box hug the actual visible content, without a
   lot of extra margin, and without cutting off part of the element?
3. **Nothing missing.** Is there a logo, text block, contrast panel, or
   obvious decorative accent on the page that has no box at all?
4. **Nothing that shouldn't be there.** Is there a box around something
   that doesn't match any of the four definitions (most likely: a box
   drawn around the background art)?
5. **Text segmentation makes sense.** For multi-line or multi-part text,
   does the split into separate boxes match how a reader would naturally
   group the words (e.g., headline vs. tagline vs. date line), rather than
   an arbitrary or inconsistent split?

## A couple of things worth knowing before you start

- **`embellishment` is sparse on purpose.** Our group deliberately didn't
  hunt for every small decorative mark — only obvious, quick ones were
  boxed. If a poster has minor flourishes with no box, that's expected, so
  please don't feel you need to flag it unless the whole class seems to
  have been missed entirely.
- **`underlay` is narrower than "anything colorful in the background."**
  Only a panel or bar placed specifically behind text/logo counts. A
  vividly illustrated or colored full-canvas background is correctly left
  unboxed, even if it's the most visually dominant part of the poster.

We mention these so you're not spending time flagging something that's
actually working as intended — please do let us know if either choice
seems off to you, though; we'd genuinely like your take.

## How to share your feedback

A short note per image where something looks off would be wonderful —
there's no need to redraw any boxes yourself. For example:

> Image 4: the panel behind the date line is unboxed (missed underlay).
> Image 9: the box labeled `underlay` around the mountain illustration
> should not exist — that's background art, not a panel.
> Image 11: the org name and sub-header are combined into one text box;
> they read as two separate lines and should probably be split.

If most images look consistent with the definitions and only a few issues
turn up, that's genuinely useful feedback on its own — this doesn't need to
be a clean-or-broken verdict, just your honest read against the table
above. Thank you again for helping us with this — we really appreciate you
sharing your expertise.
