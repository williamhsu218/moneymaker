import { html } from './html.js';
import { PLATFORMS } from '../platforms.js';

const count = (s) => [...(s || '')].length;

function copyButton(text, label = 'Copy') {
  return html`<button type="button" class="copy" data-copy-text="${text}">${label}</button>`;
}

function limitBadge(text, max) {
  if (!max) return '';
  const n = count(text);
  return html`<span class="limit ${n > max ? 'over' : ''}">${n}/${max}</span>`;
}

export function listingAsText(platformKey, l) {
  const p = PLATFORMS[platformKey];
  return [
    `TITLE\n${l.title}`,
    `DESCRIPTION\n${l.description}`,
    `HIGHLIGHTS\n${l.bullets.map((b) => `• ${b}`).join('\n')}`,
    `${(p?.tagLabel || 'Tags').toUpperCase()}\n${l.tags.join(', ')}`,
    l.meta_description ? `META DESCRIPTION\n${l.meta_description}` : '',
  ]
    .filter(Boolean)
    .join('\n\n');
}

// Rendered server-side both for history pages and for the /api/generate
// response, so there is exactly one place that formats a listing.
export function listingCard({ platform: platformKey, listing: l, warnings = [] }) {
  const p = PLATFORMS[platformKey];
  const tagText = platformKey === 'amazon' ? l.tags.join(' ') : l.tags.join(', ');

  return html`<article class="listing">
  <div class="listing-head">
    <span class="platform-badge">${p?.label || platformKey}</span>
    ${copyButton(listingAsText(platformKey, l), 'Copy everything')}
  </div>

  ${warnings.length
    ? html`<div class="notice notice-warn"><strong>Check before posting:</strong><ul>${warnings.map((w) => html`<li>${w}</li>`)}</ul></div>`
    : ''}

  <section class="field">
    <header><h3>Title</h3>${limitBadge(l.title, p?.titleMax)}${copyButton(l.title)}</header>
    <p class="field-title">${l.title}</p>
  </section>

  <section class="field">
    <header><h3>Description</h3>${copyButton(l.description)}</header>
    <div class="field-body prewrap">${l.description}</div>
  </section>

  <section class="field">
    <header><h3>Highlights</h3>${copyButton(l.bullets.map((b) => `• ${b}`).join('\n'))}</header>
    <ul class="bullets">${l.bullets.map((b) => html`<li>${b}</li>`)}</ul>
  </section>

  <section class="field">
    <header><h3>${p?.tagLabel || 'Tags'}</h3>${p?.tagCount ? html`<span class="limit ${l.tags.length > p.tagCount ? 'over' : ''}">${l.tags.length}/${p.tagCount}</span>` : ''}${copyButton(tagText)}</header>
    <ul class="chips">${l.tags.map(
      (t) => html`<li class="${p?.tagMax && count(t) > p.tagMax ? 'over' : ''}">${t}${p?.tagMax ? html`<small>${count(t)}</small>` : ''}</li>`,
    )}</ul>
  </section>

  ${l.meta_description
    ? html`<section class="field">
    <header><h3>Meta description</h3>${limitBadge(l.meta_description, 160)}${copyButton(l.meta_description)}</header>
    <p class="field-body">${l.meta_description}</p>
  </section>`
    : ''}

  ${l.seo_keywords.length
    ? html`<section class="field">
    <header><h3>Target keywords</h3>${copyButton(l.seo_keywords.join(', '))}</header>
    <ul class="chips chips-quiet">${l.seo_keywords.map((k) => html`<li>${k}</li>`)}</ul>
  </section>`
    : ''}

  ${l.seller_tips.length
    ? html`<section class="field tips">
    <header><h3>Tips to sell more</h3></header>
    <ul>${l.seller_tips.map((t) => html`<li>${t}</li>`)}</ul>
  </section>`
    : ''}
</article>`;
}
