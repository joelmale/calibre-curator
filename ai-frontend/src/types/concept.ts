import type { BookId } from "./book";

export type ConceptType =
  | "genre"
  | "theme"
  | "mood"
  | "setting"
  | "character_archetype"
  | "literary_style"
  | "period"
  | "custom";

export interface IConcept {
  readonly conceptId: string;
  readonly label: string;
  readonly description: string | null;
  readonly conceptType: ConceptType;
  readonly bookCount: number;
}

export interface IBookConcept {
  readonly bookId: BookId;
  readonly conceptId: string;
  readonly label: string;
  readonly confidence: number;
  readonly rationale: string | null;
}
