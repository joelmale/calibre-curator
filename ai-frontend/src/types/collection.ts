import type { IBookRecommendation } from "./recommendation";
import type { ISODateTimeString } from "./book";

export type CollectionType =
  | "ai_generated"
  | "concept"
  | "mood"
  | "theme"
  | "author_adjacent"
  | "manual_seeded";

export interface ICuratedCollectionSummary {
  readonly collectionId: string;
  readonly title: string;
  readonly description: string;
  readonly collectionType: CollectionType;
  readonly itemCount: number;
  readonly updatedAt: ISODateTimeString;
}

export interface ICuratedCollection {
  readonly collectionId: string;
  readonly title: string;
  readonly description: string;
  readonly collectionType: CollectionType;
  readonly items: readonly IBookRecommendation[];
}
