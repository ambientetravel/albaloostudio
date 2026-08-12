# Art brief

The generation rules, written down so they stop living in a chat window and get
reused verbatim on every prompt. Two kinds of art, and the difference between
them is a game-design rule, not a filing convention.

## The block that goes on the front of every prompt

> Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
> oxblood / lapis / gold palette, matte gouache texture, clean readable shapes,
> no photorealism, no anime, no 3D render look. Illustrated for a children's
> educational game — dignified, never cartoonish, never grim. No blood, no
> wounds, no dismemberment. No modern objects.
>
> Composition: one single subject, centred, whole and uncropped, generous empty
> margin on all four sides. Flat, even, mid-grey background, one solid colour,
> no gradient, no vignette, no texture, no scenery, no floor line. No text, no
> letters, no numerals, no signature, no watermark, no logo, no border, no
> frame, no UI. Square, 2048x2048.

The flat grey and the margin are not taste — `tools/spriteprep.py` floods the
background inward from the four corners and keeps the largest connected shape.
A gradient, a vignette or a subject touching the edge breaks the cut-out.

A drop shadow is tolerated: the tool eats it by saturation, since the shadow is
grey where the figure is brown. Do not ask for one, but do not regenerate over
one either.

## Units

A single soldier, standing, full body, feet included, facing three-quarters to
the right, weapon and shield readable in silhouette.

## Upgrade and Doctrine emblems

**Never a person. No figure, no face, no hands, no soldier.** This is the rule
that carries the most weight in the whole art set. A unit and a trait are
different kinds of thing — that is the entire point of the card kinds — and an
emblem with a soldier on it undoes the distinction the game is built on.

An emblem is objects, formation marks, or terrain: shields, spears, arrows,
horses, a defile, a shape of a line. Horses are allowed; riders are not.

## The test that actually decides it

`python3 tools/spriteprep.py --contact --kind card` renders every emblem at
24 / 28 / 40 / 64 px, which is what the game draws. An emblem is finished when
it is distinguishable **from every other emblem** in the 24px column. Looking
good large is not the test and never has been.

`shoot-the-horses` failed exactly here: it came back as a bundle of arrows with
no horse, which at 24px is the same picture as `ready-volley`. Two cards that do
opposite things must not be the same picture.
