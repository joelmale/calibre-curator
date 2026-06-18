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

export interface IAiApiClient {
  getStatus(): Promise<ApiResult<IAiStatusResponse>>;
  searchSemantic(request: ISemanticSearchRequest): Promise<ApiResult<ISemanticSearchResponse>>;
  listCollections(): Promise<ApiResult<ICollectionsResponse>>;
  getCollection(collectionId: string): Promise<ApiResult<ICuratedCollection>>;
  getBookRecommendations(
    bookId: number,
    limit: number,
  ): Promise<ApiResult<IRecommendationsResponse>>;
}
