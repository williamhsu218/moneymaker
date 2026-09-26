# 2027 电子手帐 · 农历节气版

A dated, fully hyperlinked 2027 iPad planner for Chinese buyers, sold as a digital download on Taobao and Xianyu with 小红书 as the traffic source. This product was chosen from market research, not guesswork. See the research: https://claude.ai/artifact/1sgvsRx8duo1GYarD5t3Vz

**Shop kit page (open in your browser):** https://claude.ai/artifact/DXVjGzFFXcuGocgbLQ4qSi
The kit page has the downloads, Taobao and Xianyu listing copy, four 小红书 post drafts, the delivery message, a launch checklist and the earnings math.

## The product

- **458 pages** per edition, with **10,666 page links** as direct "go to page" links, which GoodNotes, Notability, 享做笔记 and Noteshelf all follow.
- Cover, index, year calendar, yearly goals, then for each month a calendar and a plan-and-review page (habits, budget, review), then 53 weekly pages, 365 daily pages and an appendix (Cornell notes, vocabulary book, reading and film logs, yearly budget, lined, grid, dot and blank pages).
- Every date shows the **lunar date, the 24 solar terms and traditional festivals**. Statutory holidays are marked in red.
- Each month has its own **traditional Chinese color** (黛蓝, 海棠红, 竹青…).
- Two editions: **米色纸** (beige paper) and **护眼黑** (dark, eye-care).

## Files

| Path | What it is |
|---|---|
| `product/Planner-2027-Light.pdf` | Beige-paper edition (what buyers get) |
| `product/Planner-2027-Dark.pdf` | Dark edition (what buyers get) |
| `product/free/*.jpg` | Free 2027 year calendar images for 小红书 giveaways |
| `listing-images/0*.jpg` | Seven square 1600×1600 listing images for Taobao and Xianyu |
| `listing-images/xhs-*.jpg` | Three portrait 1200×1600 images for 小红书 posts |
| `source/` | Data, page templates, build and mockup scripts |

## Holiday update

The official 2027 holiday and make-up workday (调休) schedule isn't published yet; the State Council usually releases it in November or December. When it's out, the make-up workdays need adding to `source/data.mjs` (ask Claude to do it), then rebuild and send buyers the new files. The listing already promises this free update.

## Rebuilding

Requires Node 22, Playwright's Chromium, Python with PyMuPDF, and the fonts from `kp-planner-cn/source/fetch-fonts.sh` (`source/fonts` is a symlink to them).

```bash
cd planner-2027
npm install                                        # lunar-javascript
node source/build.mjs /tmp/p27                     # both PDFs + page previews
python3 source/fix_links.py product/Planner-2027-Light.pdf product/Planner-2027-Dark.pdf
node source/mockups.mjs /tmp/p27                   # listing images
```

Lunar dates, solar terms and festivals come from [lunar-javascript](https://github.com/6tail/lunar-javascript) (MIT) and were checked against published calendars.
