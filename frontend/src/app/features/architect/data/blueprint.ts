import {
  DEFAULT_BLUEPRINT,
  LIMITS,
  type Blueprint,
  type Design,
  type DesignRequest,
  type EstimateRequest,
  type NumberKey,
  type RaisedVocabulary,
} from './architect.types';

export function withinLimit(value: number | null, key: NumberKey): value is number {
  const { min, max } = LIMITS[key];
  return value !== null && Number.isInteger(value) && value >= min && value <= max;
}

export function designRequest(blueprint: Blueprint): DesignRequest {
  const shared = {
    hidden_size: blueprint.hidden_size,
    heads: blueprint.heads,
    intermediate_size: blueprint.intermediate_size,
    vocab_size: blueprint.vocab_size,
    context_length: blueprint.context_length,
  };
  switch (blueprint.family) {
    case 'dense_decoder':
      return {
        ...shared,
        family: blueprint.family,
        tie_embeddings: blueprint.tie_embeddings,
        layers: blueprint.layers,
        kv_heads: blueprint.kv_heads,
      };
    case 'moe_decoder':
      return {
        ...shared,
        family: blueprint.family,
        tie_embeddings: blueprint.tie_embeddings,
        layers: blueprint.layers,
        kv_heads: blueprint.kv_heads,
        experts: blueprint.experts,
        experts_per_token: blueprint.experts_per_token,
      };
    case 'encoder_decoder':
      return {
        ...shared,
        family: blueprint.family,
        tie_embeddings: true,
        encoder_layers: blueprint.encoder_layers,
        decoder_layers: blueprint.decoder_layers,
      };
  }
}

export function estimateRequest(blueprint: Blueprint): EstimateRequest | null {
  const { seq_len, batch } = blueprint;
  if (!withinLimit(seq_len, 'seq_len') || !withinLimit(batch, 'batch')) {
    return null;
  }
  return { design: designRequest(blueprint), seq_len, batch, tokenizer: blueprint.tokenizer.trim() };
}

export function raisedVocabulary(request: EstimateRequest, tokens: number | null): RaisedVocabulary | null {
  const typed = request.design.vocab_size;
  return tokens !== null && typed !== null && tokens > typed ? { tokenizer: request.tokenizer, tokens } : null;
}

export function blueprintOf(
  design: Design,
  extras: { readonly tokenizer: string; readonly seq_len: number; readonly batch: number },
): Blueprint {
  const known = (value: number, key: NumberKey): number | null => (value > 0 ? value : DEFAULT_BLUEPRINT[key]);
  return {
    family: design.family,
    layers: known(design.layers, 'layers'),
    encoder_layers: known(design.encoder_layers, 'encoder_layers'),
    decoder_layers: known(design.decoder_layers, 'decoder_layers'),
    hidden_size: design.hidden_size,
    heads: design.heads,
    kv_heads: design.kv_heads,
    intermediate_size: design.intermediate_size,
    experts: known(design.experts, 'experts'),
    experts_per_token: known(design.experts_per_token, 'experts_per_token'),
    vocab_size: design.vocab_size,
    context_length: design.context_length,
    seq_len: extras.seq_len,
    batch: extras.batch,
    tie_embeddings: design.tie_embeddings,
    tokenizer: extras.tokenizer,
  };
}

export function signature(blueprint: Blueprint): string {
  return JSON.stringify([
    designRequest(blueprint),
    blueprint.tokenizer.trim(),
    blueprint.seq_len,
    blueprint.batch,
  ]);
}
