import type { ISODateTimeString } from "./book";

export type IngestionStatus =
  | "idle"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "partial";

export interface ILibraryIndexStatus {
  readonly metadataDbReadable: boolean;
  readonly bookCount: number;
  readonly indexedBookCount: number;
  readonly pendingBookCount: number;
}

export interface IEmbeddingStatus {
  readonly provider: "ollama" | "openai" | "disabled";
  readonly model: string;
  readonly ok: boolean;
  readonly warning: string | null;
}

export interface IIngestionRunStatus {
  readonly runId: number | null;
  readonly startedAt: ISODateTimeString | null;
  readonly finishedAt: ISODateTimeString | null;
  readonly status: IngestionStatus;
  readonly scannedBooks: number;
  readonly changedBooks: number;
  readonly embeddedChunks: number;
  readonly errorCount: number;
}

export interface IAiStatusResponse {
  readonly library: ILibraryIndexStatus;
  readonly embedding: IEmbeddingStatus;
  readonly lastIngestionRun: IIngestionRunStatus | null;
}
