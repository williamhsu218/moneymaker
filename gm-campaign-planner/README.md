# The Game Master's Campaign Planner

A finished printable product to sell on Etsy (or Gumroad, Payhip, itch.io): a 35-page campaign planner for tabletop RPG game masters. It includes 236 original roll-table entries and works with any fantasy RPG.

**Shop kit page (open in your browser):** https://claude.ai/artifact/9WAdkCFh2fEtygcKzAB5fH
The kit page has download buttons, the listing text with copy buttons, a launch checklist and the earnings math.

## What's in this folder

| Path | What it is |
|---|---|
| `product/GM-Campaign-Planner-US-Letter.pdf` | The product, 8.5 × 11 in. Upload to Etsy. |
| `product/GM-Campaign-Planner-A4.pdf` | The product, A4. Upload to Etsy. |
| `product/FREE-Session-Prep-Page-US-Letter.pdf` | Free one-page sample to give away for marketing. |
| `listing-images/01…07.jpg` | Etsy listing photos, 2667 × 2000. Upload in number order. |
| `source/` | How the files were made (only needed to edit the design). |

## Listing text

**Title** (124 of 140 characters)

```
Game Master Campaign Planner Printable, 35 Page TTRPG Session Prep Journal, NPC & Villain Sheets, Roll Tables, GM Binder PDF
```

**Tags** (13, each 20 characters or fewer)

```
gm planner, dm planner, ttrpg printable, campaign planner, session prep, game master gift, rpg gift for gm, rpg journal, npc sheets, fantasy rpg, gm binder, tabletop rpg, dm tools
```

**Price:** $8.99. After Etsy's 6.5% transaction fee, US payment processing (3% + $0.25) and the $0.20 listing fee, you keep about $7.69 per sale.

The full description is on the kit page.

## Notes

- **Fonts:** Cinzel and EB Garamond, under the SIL Open Font License, which allows embedding them in products you sell. License texts are in `source/fonts/`.
- **Trademarks:** the title and tags avoid publisher trademarks such as "Dungeons & Dragons". Many sellers also use "dnd" as a tag because it gets a lot of searches. It's a trademark, so whether to add it is your call.
- **AI disclosure:** the description ends with "Designed with the help of AI tools." Etsy asks sellers to be open about using AI in their creative process.

## Editing the design

The pages are HTML/CSS in `source/pages.mjs` and `source/planner.css`, and the roll-table text is in `source/content.mjs`. To rebuild (requires Node 22 and Playwright's Chromium):

```bash
node gm-campaign-planner/source/build.mjs /tmp/planner-build     # PDFs + page previews
node gm-campaign-planner/source/mockups.mjs /tmp/planner-build   # listing photos
```
