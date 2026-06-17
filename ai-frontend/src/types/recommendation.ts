import type { IBookSummary, PercentInteger } from "./book";

export type RecommendationType =
  | "similar_concepts"
  | "similar_text"
  | "author_adjacent"
  | "tag_adjacent"
  | "reading_history"
  | "collection_context";

export interface IBookRecommendation extends IBookSummary {
  readonly matchScore: number;
  readonly matchPercent: PercentInteger;
  readonly recommendationType: RecommendationType;
  readonly matchReasons: readonly string[];
}
