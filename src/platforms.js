// Marketplace rules the generator writes to and the UI checks against.
// Limits are character counts. Keep these in sync with each marketplace's
// current seller guidelines.

export const PLATFORMS = {
  etsy: {
    label: 'Etsy',
    titleMax: 140,
    tagCount: 13,
    tagMax: 20,
    bulletCount: 5,
    tagLabel: 'Tags',
    rules: [
      'Title: at most 140 characters. Lead with the words a shopper would type into Etsy search; put the most important keywords in the first 40 characters. No ALL CAPS words.',
      'Tags: exactly 13 tags, each at most 20 characters (spaces count). Use multi-word long-tail phrases, not single words. Do not repeat the same tag, and avoid tags that only repeat the category.',
      'Description: the first 160 characters appear in search previews, so open with a clear, keyword-rich sentence about what the item is. Follow with details, materials, sizing, care and gifting ideas in short paragraphs.',
      'Bullets: 5 short highlight lines the seller can paste into the description.',
    ],
  },
  amazon: {
    label: 'Amazon',
    titleMax: 200,
    tagCount: 0,
    tagMax: 0,
    bulletCount: 5,
    tagLabel: 'Backend search terms',
    rules: [
      'Title: at most 200 characters, and ideally under 80 so it is not cut off on mobile. Format: Brand (if given) + product type + key feature + material/size/color/quantity. Capitalize the first letter of each word except short prepositions and articles. No promotional phrases (such as "best seller", "free shipping", "#1") and none of these characters: ! $ ? _ { } ^ ¬ ¦. Do not repeat any word more than twice.',
      'Bullets: exactly 5 key product features, each starting with a short capitalized benefit phrase followed by details, each under 250 characters. No pricing, shipping or company information, and no unverifiable claims.',
      'Description: plain text, under 2000 characters, expanding on use cases and details not covered by the bullets.',
      'Backend search terms (tags field): about 10 to 15 lowercase terms, synonyms and alternate spellings that are NOT already in the title or bullets. No brand names (including competitors), no ASINs, no punctuation, no temporary or subjective words like "new" or "amazing". Keep the combined length under 249 bytes.',
    ],
  },
  shopify: {
    label: 'Shopify',
    titleMax: 70,
    tagCount: 10,
    tagMax: 40,
    bulletCount: 5,
    tagLabel: 'Product tags',
    rules: [
      'Title: at most 70 characters, clear and descriptive, as it doubles as the page title in Google results.',
      'Description: persuasive, brand-voice product page copy in short scannable paragraphs; open with the main benefit.',
      'Bullets: 5 benefit-led highlights for a features list on the product page.',
      'Tags: about 10 product tags useful for store collections and filtering (e.g. category, style, occasion, material).',
      'Meta description: at most 160 characters, written to earn the click in Google search results.',
    ],
  },
  ebay: {
    label: 'eBay',
    titleMax: 80,
    tagCount: 0,
    tagMax: 0,
    bulletCount: 5,
    tagLabel: 'Item specifics ideas',
    rules: [
      'Title: at most 80 characters. Pack it with the exact words buyers search: brand, model, product type, size, color, material, condition if given. No filler words like "L@@K", "wow" or "amazing", and no punctuation for decoration.',
      'Description: clear and honest, covering condition (only if provided), what is included, key specs and dimensions if given.',
      'Bullets: 5 key features or specs for a quick-scan list at the top of the description.',
      'Tags field: suggested item specifics written as "Name: Value" pairs (e.g. "Material: Leather"), using only facts from the input.',
    ],
  },
  website: {
    label: 'Your own store',
    titleMax: 70,
    tagCount: 10,
    tagMax: 40,
    bulletCount: 5,
    tagLabel: 'Tags',
    rules: [
      'Title: at most 70 characters, descriptive and search-friendly.',
      'Description: persuasive product page copy in short paragraphs that works for WooCommerce, Squarespace, Wix or any online store.',
      'Bullets: 5 benefit-led highlights.',
      'Tags: about 10 tags for categories and site search.',
      'Meta description: at most 160 characters for search results.',
    ],
  },
};

export const TONES = {
  friendly: 'Friendly and warm',
  professional: 'Professional and trustworthy',
  luxury: 'Premium and elegant',
  playful: 'Playful and fun',
  minimal: 'Minimal and to the point',
};

export const LANGUAGES = {
  en: 'English',
  es: 'Spanish',
  fr: 'French',
  de: 'German',
  it: 'Italian',
  pt: 'Portuguese',
  nl: 'Dutch',
  ja: 'Japanese',
};

export const INPUT_LIMITS = {
  productName: 150,
  details: 3000,
  audience: 200,
  keywords: 300,
};

// Validates and normalizes the generate form. Returns { input } or { error }.
export function parseGenerateInput(body = {}) {
  const str = (v) => (typeof v === 'string' ? v.trim() : '');
  const input = {
    platform: str(body.platform),
    productName: str(body.productName),
    details: str(body.details),
    audience: str(body.audience),
    keywords: str(body.keywords),
    tone: str(body.tone) || 'friendly',
    language: str(body.language) || 'en',
  };

  if (!PLATFORMS[input.platform]) return { error: 'Pick a marketplace.' };
  if (!TONES[input.tone]) return { error: 'Pick a tone.' };
  if (!LANGUAGES[input.language]) return { error: 'Pick a language.' };
  if (input.productName.length < 2) return { error: 'Tell us what the product is.' };
  if (input.details.length < 10) {
    return { error: 'Add a few product details (materials, size, features…) so the listing is accurate.' };
  }
  for (const [field, max] of Object.entries(INPUT_LIMITS)) {
    if (input[field].length > max) {
      return { error: `That ${field.replace(/[A-Z]/g, (c) => ' ' + c.toLowerCase())} is too long (max ${max} characters).` };
    }
  }
  return { input };
}

// Flags anything in a generated listing that breaks the marketplace's limits,
// so the seller sees it before pasting.
export function checkListing(platformKey, listing) {
  const p = PLATFORMS[platformKey];
  const warnings = [];
  if (!p) return warnings;
  const len = (s) => [...(s || '')].length;

  if (len(listing.title) > p.titleMax) {
    warnings.push(`Title is ${len(listing.title)} characters; ${p.label} allows ${p.titleMax}.`);
  }
  if (p.tagCount && listing.tags.length > p.tagCount) {
    warnings.push(`${listing.tags.length} tags; ${p.label} allows ${p.tagCount}.`);
  }
  if (p.tagMax) {
    for (const tag of listing.tags) {
      if (len(tag) > p.tagMax) warnings.push(`Tag "${tag}" is over ${p.tagMax} characters.`);
    }
  }
  if (platformKey === 'amazon') {
    const bytes = Buffer.byteLength(listing.tags.join(' '), 'utf8');
    if (bytes > 249) warnings.push(`Backend search terms are ${bytes} bytes; Amazon indexes 249.`);
  }
  if (listing.meta_description && len(listing.meta_description) > 160) {
    warnings.push(`Meta description is ${len(listing.meta_description)} characters; aim for 160.`);
  }
  return warnings;
}
