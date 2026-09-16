// Compatibility boundary: generation is owned by crossword-generator.
export { constructOriginalFill, generateCandidateBatches } from '@crossword/generator';
export type {
  ConstructionFailure,
  FillGrid,
  LexiconResolver,
  OriginalConstructionRequest,
  OriginalConstructionResult
} from '@crossword/generator';
