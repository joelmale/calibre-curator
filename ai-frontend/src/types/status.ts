import type { ISODateTimeString } from "./book";

export type PipelinePhase = "idle" | "scanning" | "extracting" | "embedding";

export interface IIngestionProgress {
  readonly phase: PipelinePhase;
  readonly total_to_process: number;
  readonly current_index: number;
  readonly current_book_id: number | null;
  readonly current_title: string | null;
  readonly chunks_embedded_so_far: number;
  readonly chunks_total: number;
}

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
  readonly statusBreakdown: Readonly<Record<string, number>>;
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

export interface IChatStatus {
  readonly priority: readonly string[];
  readonly chain: readonly string[];
}

export interface IAiStatusResponse {
  readonly library: ILibraryIndexStatus;
  readonly embedding: IEmbeddingStatus;
  readonly chat?: IChatStatus;
  readonly lastIngestionRun: IIngestionRunStatus | null;
}
