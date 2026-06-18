import { HttpClient } from "./httpClient";
import type {
  IAiApiClient,
  ICollectionsResponse,
  IIngestionTriggerResponse,
  IIngestionFailuresResponse,
  IRecommendationsResponse,
  ISemanticSearchRequest,
  ISemanticSearchResponse,
  IMoodSearchRequest,
  IMoodSearchResponse,
  ISequenceGenerateRequest,
  ISequenceGenerateResponse,
  ISequenceSaveRequest,
  ISequenceSaveResponse,
  ISequencesListResponse,
  ApiResult,
} from "../types/api";
import type { ICuratedCollection } from "../types/collection";
import type { IAiStatusResponse, IIngestionProgress } from "../types/status";

export class AiApiClient implements IAiApiClient {
  public constructor(private readonly http: HttpClient) {}

  public getStatus(): Promise<ApiResult<IAiStatusResponse>> {
    return this.http.get<IAiStatusResponse>("/status");
  }

  public getRecentFailures(): Promise<ApiResult<IIngestionFailuresResponse>> {
    return this.http.get<IIngestionFailuresResponse>("/status/failures");
  }

  public getIngestionProgress(): Promise<ApiResult<IIngestionProgress>> {
    return this.http.get<IIngestionProgress>("/ingestion/progress");
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

  public searchMood(
    request: IMoodSearchRequest,
  ): Promise<ApiResult<IMoodSearchResponse>> {
    return this.http.post<IMoodSearchRequest, IMoodSearchResponse>(
      "/mood/search",
      request,
    );
  }

  public generateSequence(
    request: ISequenceGenerateRequest,
  ): Promise<ApiResult<ISequenceGenerateResponse>> {
    return this.http.post<ISequenceGenerateRequest, ISequenceGenerateResponse>(
      "/sequences/generate",
      request,
    );
  }

  public saveSequence(
    request: ISequenceSaveRequest,
  ): Promise<ApiResult<ISequenceSaveResponse>> {
    return this.http.post<ISequenceSaveRequest, ISequenceSaveResponse>(
      "/sequences/save",
      request,
    );
  }

  public listSequences(): Promise<ApiResult<ISequencesListResponse>> {
    return this.http.get<ISequencesListResponse>("/sequences");
  }
}
