import type { ICuratedCollection, ICuratedCollectionSummary } from "./collection";
import type { IAiStatusResponse } from "./status";

// Matches the actual JSON shape returned by the sidecar search + recommendations APIs
export interface IApiBookResult {
  readonly bookId: number;
  readonly title: string;
  readonly authors: readonly string[];
  readonly matchPercent: number;
  readonly matchReasons: readonly string[];
  readonly score: number;
}

export interface IApiError {
  readonly error: string;
  readonly detail: string | null;
}

export type ApiResult<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly error: IApiError };

export interface ISemanticSearchRequest {
  readonly query: string;
  readonly limit: number;
  readonly filters?: {
    readonly authors?: readonly string[];
    readonly tags?: readonly string[];
    readonly languages?: readonly string[];
  };
}

export interface ISemanticSearchResponse {
  readonly query: string;
  readonly results: readonly IApiBookResult[];
}

export interface ICollectionsResponse {
  readonly collections: readonly ICuratedCollectionSummary[];
}

export interface IRecommendationsResponse {
  readonly sourceBookId: number;
  readonly recommendations: readonly IApiBookResult[];
}

export interface IIngestionTriggerResponse {
  readonly runId: number;
  readonly status: string;
  readonly limit: number | null;
}

export interface IMoodSearchRequest {
  readonly prompt: string;
  readonly limit?: number;
}

export interface IMoodSearchResponse {
  readonly prompt: string;
  readonly semanticQuery: string;
  readonly explanation: string;
  readonly excludedTags: readonly string[];
  readonly results: readonly IApiBookResult[];
}

export interface ISequenceStep {
  readonly rank: number;
  readonly bookId: number;
  readonly title: string;
  readonly authors: readonly string[];
  readonly reason: string;
}

export interface ISequenceGenerateRequest {
  readonly goal: string;
  readonly seedBookId?: number | null;
}

export interface ISequenceGenerateResponse {
  readonly goal: string;
  readonly explanation: string;
  readonly candidateCount: number;
  readonly steps: readonly ISequenceStep[];
}

export interface ISequenceSaveRequest {
  readonly title: string;
  readonly goal: string;
  readonly steps: readonly ISequenceStep[];
}

export interface ISequenceSaveResponse {
  readonly ok: boolean;
  readonly collectionSlug: string;
  readonly itemCount: number;
}

export interface ISavedSequence {
  readonly collectionSlug: string;
  readonly title: string;
  readonly description: string;
  readonly itemCount: number;
  readonly steps: readonly ISequenceStep[];
}

export interface ISequencesListResponse {
  readonly sequences: readonly ISavedSequence[];
}

export interface IIngestionFailure {
  readonly calibreBookId: number;
  readonly title: string | null;
  readonly error: string | null;
  readonly failedAt: string | null;
}

export interface IIngestionFailuresResponse {
  readonly failures: readonly IIngestionFailure[];
}

export interface IAiApiClient {
  getStatus(): Promise<ApiResult<IAiStatusResponse>>;
  getRecentFailures(): Promise<ApiResult<IIngestionFailuresResponse>>;
  triggerIngestion(limit?: number | null): Promise<ApiResult<IIngestionTriggerResponse>>;
  searchSemantic(request: ISemanticSearchRequest): Promise<ApiResult<ISemanticSearchResponse>>;
  listCollections(): Promise<ApiResult<ICollectionsResponse>>;
  getCollection(collectionId: string): Promise<ApiResult<ICuratedCollection>>;
  getBookRecommendations(
    bookId: number,
    limit: number,
  ): Promise<ApiResult<IRecommendationsResponse>>;
  searchMood(request: IMoodSearchRequest): Promise<ApiResult<IMoodSearchResponse>>;
  generateSequence(
    request: ISequenceGenerateRequest,
  ): Promise<ApiResult<ISequenceGenerateResponse>>;
  saveSequence(
    request: ISequenceSaveRequest,
  ): Promise<ApiResult<ISequenceSaveResponse>>;
  listSequences(): Promise<ApiResult<ISequencesListResponse>>;
}
