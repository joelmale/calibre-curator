export type BookId = number;
export type ISODateTimeString = string;
export type PercentInteger = number;

export interface IBookSummary {
  readonly bookId: BookId;
  readonly title: string;
  readonly authors: readonly string[];
  readonly coverUrl: string | null;
  readonly detailUrl: string;
  readonly tags: readonly string[];
  readonly language: string | null;
  readonly seriesName: string | null;
}

export interface IMatchChunk {
  readonly chunkId: string;
  readonly snippet: string;
  readonly sourceType: "metadata" | "epub_text" | "pdf_text" | "opf_metadata";
  readonly sourceFormat: "EPUB" | "PDF" | "MOBI" | "AZW3" | "OPF" | null;
}

export interface IBookSearchResult extends IBookSummary {
  readonly matchScore: number;
  readonly matchPercent: PercentInteger;
  readonly matchReasons: readonly string[];
  readonly matchedChunks: readonly IMatchChunk[];
}
