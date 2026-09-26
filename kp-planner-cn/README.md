# 守秘人手札 · KP 跑团主持规划本

A Chinese-language printable planner for Keepers (KP) running Call of Cthulhu–style investigation and horror games, made to sell on Xianyu (闲鱼) as a digital download. It has 28 A4 pages and 244 original Chinese roll-table entries, and it works with any rule system.

**Shop kit page (open in your browser):** https://claude.ai/artifact/BuDftqTkmK4ZEWvJjxxMGE
The kit page has download buttons, the Chinese listing copy with copy buttons, a delivery message template, a launch checklist and the earnings math.

## What's in this folder

| Path | What it is |
|---|---|
| `product/KP-Planner-CN-A4.pdf` | The product (28 pages, A4). Share it from 百度网盘 or 夸克网盘. |
| `product/FREE-Sample-Session-Prep-A4.pdf` | Free 备团单 page to give away on 小红书 and in TRPG groups. |
| `listing-images/01…06.jpg` | Square 1600 × 1600 listing images. Upload in number order. |
| `source/` | How the files were made (only needed to edit the design). |

## Listing

**Title, option A** (no trademark):

```
原创守秘人手札｜克苏鲁跑团KP主持规划本 模组设计 线索网 可打印PDF
```

**Title, option B** (uses "COC", a Chaosium trademark, for more search traffic):

```
原创守秘人手札｜COC跑团KP规划本 克苏鲁模组设计 线索网 可打印PDF
```

**Price:** ¥9.9 to launch, then ¥15.8 once you have about 10 sales. These are starting guesses, so adjust after checking similar listings. Xianyu's service fee for personal sellers is 0.6% (1.6% with the 鱼小铺 tools).

The full description and the delivery message are on the kit page.

## Notes

- **Returns:** under Article 25 of the Consumer Rights Protection Law (《消费者权益保护法》), downloaded digital goods are exempt from 7-day no-reason returns. The description states this clearly, as the law requires.
- **Business registration:** under Xianyu's rules from June 1, 2026, sellers with more than ¥100,000 a year in sales must register a business.
- **Fonts:** Noto Serif SC, Noto Sans SC and Ma Shan Zheng, all under the SIL Open Font License, which allows embedding them in products you sell.
- **AI disclosure:** the description says parts were designed with AI tools.

## Editing the design

The pages are in `source/pages.mjs` and `source/planner.css`, and the roll-table text is in `source/content.mjs`. To rebuild (requires Node 22, Playwright's Chromium and fonttools):

```bash
kp-planner-cn/source/fetch-fonts.sh                          # one time, ~70 MB
node kp-planner-cn/source/build.mjs /tmp/kp-build            # PDF + page previews
node kp-planner-cn/source/mockups.mjs /tmp/kp-build          # listing images
```
