import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import Anthropic from '@anthropic-ai/sdk';
import { createClaudeGenerator, createDemoGenerator, GenerationError, estimateCostUsd } from '../src/generator.js';
import { parseGenerateInput, checkListing } from '../src/platforms.js';
import { validInput } from './helpers.js';

const listingJson = {
  title: 'Speckled Ceramic Mug',
  description: 'Hand-thrown.',
  bullets: ['• One', 'Two', 'Three', 'Four', 'Five'],
  tags: Array.from({ length: 15 }, (_, i) => `tag ${i % 14}`),
  meta_description: 'Meta',
  seo_keywords: ['ceramic mug'],
  seller_tips: ['Add dimensions'],
};

function fakeClient(respond) {
  const calls = [];
  return {
    calls,
    beta: {
      messages: {
        create: async (params) => {
          calls.push(params);
          return respond(params);
        },
      },
    },
  };
}

const gen = (client) => createClaudeGenerator({ model: 'claude-opus-5', effort: 'low', client });

describe('Claude generator', () => {
  test('sends a structured-output request with refusal fallbacks', async () => {
    const client = fakeClient(() => ({
      model: 'claude-opus-5',
      stop_reason: 'end_turn',
      content: [{ type: 'thinking', thinking: '' }, { type: 'text', text: JSON.stringify(listingJson) }],
      usage: { input_tokens: 1200, output_tokens: 900 },
    }));
    const result = await gen(client).generate(validInput);

    const params = client.calls[0];
    assert.equal(params.model, 'claude-opus-5');
    assert.deepEqual(params.betas, ['server-side-fallback-2026-07-01']);
    assert.equal(params.fallbacks, 'default');
    assert.equal(params.output_config.effort, 'low');
    assert.equal(params.output_config.format.type, 'json_schema');
    assert.equal(params.output_config.format.schema.additionalProperties, false);
    assert.equal(params.thinking, undefined);
    assert.match(params.messages[0].content, /Marketplace: Etsy/);
    assert.match(params.messages[0].content, /<seller_notes>/);

    assert.equal(result.listing.title, 'Speckled Ceramic Mug');
    assert.equal(result.listing.bullets[0], 'One', 'leading bullet characters stripped');
    assert.equal(result.listing.tags.length, 13, 'deduped and capped to Etsy limit');
    assert.equal(result.inputTokens, 1200);
    assert.equal(result.outputTokens, 900);
  });

  test('uses only the text after a fallback switch and totals every attempt', async () => {
    const client = fakeClient(() => ({
      model: 'claude-opus-4-8',
      stop_reason: 'end_turn',
      content: [
        { type: 'text', text: '{"partial":' },
        { type: 'fallback', from: { model: 'claude-opus-5' }, to: { model: 'claude-opus-4-8' } },
        { type: 'text', text: JSON.stringify(listingJson) },
      ],
      usage: {
        input_tokens: 1000,
        output_tokens: 700,
        iterations: [
          { type: 'message', input_tokens: 1000, output_tokens: 5 },
          { type: 'fallback_message', input_tokens: 1000, output_tokens: 700 },
        ],
      },
    }));
    const result = await gen(client).generate(validInput);
    assert.equal(result.model, 'claude-opus-4-8');
    assert.equal(result.listing.title, 'Speckled Ceramic Mug');
    assert.equal(result.inputTokens, 2000);
    assert.equal(result.outputTokens, 705);
  });

  test('turns a refusal into a customer-safe error', async () => {
    const client = fakeClient(() => ({ stop_reason: 'refusal', content: [], usage: {} }));
    await assert.rejects(gen(client).generate(validInput), (err) => {
      assert.ok(err instanceof GenerationError);
      assert.equal(err.status, 422);
      return true;
    });
  });

  test('maps rate limits to a retryable 503', async () => {
    const client = fakeClient(() => {
      throw new Anthropic.RateLimitError(429, {}, 'rate limited', new Headers());
    });
    await assert.rejects(gen(client).generate(validInput), (err) => {
      assert.ok(err instanceof GenerationError);
      assert.equal(err.status, 503);
      return true;
    });
  });

  test('rejects unparseable output', async () => {
    const client = fakeClient(() => ({ stop_reason: 'end_turn', content: [{ type: 'text', text: 'not json' }], usage: {} }));
    await assert.rejects(gen(client).generate(validInput), GenerationError);
  });
});

describe('demo generator', () => {
  test('respects every platform limit it can', async () => {
    for (const platform of ['etsy', 'amazon', 'shopify', 'ebay', 'website']) {
      const { listing } = await createDemoGenerator().generate({ ...validInput, platform, keywords: 'gift for her' });
      const warnings = checkListing(platform, listing).filter((w) => !w.includes('Tag "'));
      assert.deepEqual(warnings, [], platform);
    }
  });
});

describe('input validation and checks', () => {
  test('normalizes defaults', () => {
    const { input } = parseGenerateInput({ platform: 'ebay', productName: ' Lamp ', details: 'Brass desk lamp, works.' });
    assert.equal(input.productName, 'Lamp');
    assert.equal(input.tone, 'friendly');
    assert.equal(input.language, 'en');
  });

  test('catches over-limit titles', () => {
    const warnings = checkListing('ebay', { title: 'x'.repeat(81), tags: [], bullets: [] });
    assert.equal(warnings.length, 1);
  });

  test('estimates cost from list prices', () => {
    assert.equal(estimateCostUsd('claude-opus-5', 1_000_000, 0), 5);
    assert.equal(estimateCostUsd('unknown', 1, 1), null);
  });
});
