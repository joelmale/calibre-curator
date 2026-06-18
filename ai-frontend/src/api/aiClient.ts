import { HttpClient } from "./httpClient";
import type {
  IAiApiClient,
  ICollectionsResponse,
  IIngestionTriggerResponse,
  IRecommendationsResponse,
  ISemanticSearchRequest,
  ISemanticSearchResponse,
  ApiResult,
} from "../types/api";
import type { ICuratedCollection } from "../types/collection";
import type { IAiStatusResponse } from "../types/status";

export class AiApiClient implements IAiApiClient {
  public constructor(private readonly http: HttpClient) {}

  public getStatus(): Promise<ApiResult<IAiStatusResponse>> {
    return this.http.get<IAiStatusResponse>("/status");
  }

  public triggerIngestion(limit?: number | null): Promise<ApiResult<IIngestionTriggerResponse>> {
    const body = limit != null ? { limit } : {};
    return this.http.post<typeof body, IIngestionTriggerResponse>("/ingestion/run", body);
  }

  public searchSemantic(
    request: ISemanticSearchRequest,
  ): Promise<ApiResult<ISemanticSearchResponse>> {
    return this.http.post<ISemanticSearchRequest, ISemanticSearchResponse>(
      "/search/semantic",
      request,
    );
  }

  public listCollections(): Promise<ApiResult<ICollectionsResponse>> {
    return this.http.get<ICollectionsResponse>("/collections/");
  }

  public getCollection(collectionId: string): Promise<ApiResult<ICuratedCollection>> {
    return this.http.get<ICuratedCollection>(
      `/collections/${encodeURIComponent(collectionId)}`,
    );
  }

  public getBookRecommendations(
    bookId: number,
    limit: number,
  ): Promise<ApiResult<IRecommendationsResponse>> {
    return this.http.get<IRecommendationsResponse>(
      `/recommendations/books/${bookId}?limit=${limit}`,
    );
  }
}
