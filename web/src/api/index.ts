import { http } from './client';
import type {
  AssetInfo,
  CompetitorDraft,
  CompetitorInfo,
  CompetitorParseResult,
  CreativePlanInfo,
  DashboardSummary,
  DiagnosisContent,
  DiagnosisInfo,
  GenerationTaskInfo,
  ImageSchemeInfo,
  PlatformMappingInfo,
  ProductDetail,
  ProductSummary,
  SkuInfo,
  StockFlowInfo,
  StoreInfo,
  TrendPoint,
  User,
  VideoScriptInfo,
  VideoShotInfo,
} from './types';

export interface SkuPayload {
  spec_json?: Record<string, string>;
  spec_text?: string;
  price: number;
  stock: number;
  warn_threshold: number;
  mappings?: Array<{
    platform?: string;
    platform_spec_name?: string;
    platform_price?: number;
    platform_sku_code?: string;
  }>;
}

export interface ProductCreatePayload {
  store_id: number;
  name: string;
  category?: string;
  price_min?: number;
  price_max?: number;
  description?: string;
  main_sku_id?: number | null;
  skus?: SkuPayload[];
}

export interface ProductUpdatePayload {
  store_id?: number;
  name?: string;
  category?: string;
  price_min?: number;
  price_max?: number;
  description?: string;
  main_sku_id?: number;
}

export interface StorePayload {
  name?: string;
  platform?: string;
  auth_status?: string;
  auth_ref?: string;
}

export interface ImageSchemePayload {
  title?: string;
  layout?: string;
  copy?: string;
  main_selling_point?: string;
  visual_tip?: string;
  order_no?: number;
}

export interface VideoScriptPayload {
  title?: string;
  hook_3s?: string;
  closing_cta?: string;
  order_no?: number;
}

export interface VideoShotPayload {
  duration_sec?: number;
  scene_desc?: string;
  voiceover?: string;
  cta_line?: string;
}

export interface AssetFilters {
  type?: 'image' | 'video';
  status?: string;
}

export interface CompetitorPayload {
  platform: string;
  name: string;
  price: number;
  url?: string;
  params_json?: Record<string, string>;
  sales_volume?: number;
  rating?: number;
  source?: string;
  parse_status?: string;
}

export const api = {
  login: (username: string, password: string) =>
    http.post<{ token: string; user: User }>('/auth/login', { username, password }),
  me: () => http.get<User>('/auth/me'),
  dashboard: () => http.get<DashboardSummary>('/dashboard/summary'),
  stores: () => http.get<StoreInfo[]>('/stores'),
  createStore: (payload: StorePayload) => http.post<StoreInfo>('/stores', payload),
  updateStore: (id: number, payload: StorePayload) =>
    http.put<StoreInfo>(`/stores/${id}`, payload),
  products: (params?: { store_id?: number; keyword?: string; stage?: string }) => {
    const qs = new URLSearchParams();
    if (params?.store_id) qs.set('store_id', String(params.store_id));
    if (params?.keyword) qs.set('keyword', params.keyword);
    if (params?.stage) qs.set('stage', params.stage);
    const suffix = qs.toString() ? `?${qs}` : '';
    return http.get<ProductSummary[]>(`/products${suffix}`);
  },
  product: (id: number) => http.get<ProductDetail>(`/products/${id}`),
  createProduct: (payload: ProductCreatePayload) =>
    http.post<ProductDetail>('/products', payload),
  updateProduct: (id: number, payload: ProductUpdatePayload) =>
    http.put<ProductDetail>(`/products/${id}`, payload),
  archiveProduct: (id: number) =>
    http.post<{ id: number; archived: boolean; message: string }>(`/products/${id}/archive`),
  productTrend: (id: number, days = 14) =>
    http.get<TrendPoint[]>(`/products/${id}/metric-trend?days=${days}`),

  createSku: (
    productId: number,
    payload: { spec_json: Record<string, string>; price: number; stock: number; warn_threshold: number },
  ) => http.post<SkuInfo>(`/products/${productId}/skus`, payload),
  updateSku: (
    id: number,
    payload: { spec_json?: Record<string, string>; price?: number; warn_threshold?: number },
  ) => http.put<SkuInfo>(`/skus/${id}`, payload),
  deleteSku: (id: number) => http.del<{ ok: boolean }>(`/skus/${id}`),
  adjustStock: (id: number, change: number, reason: string) =>
    http.post<{ sku: SkuInfo; flow: StockFlowInfo }>(`/skus/${id}/stock-adjust`, {
      change,
      reason,
    }),
  stockFlows: (id: number) => http.get<StockFlowInfo[]>(`/skus/${id}/stock-flows`),

  createMapping: (
    skuId: number,
    payload: {
      platform: string;
      platform_spec_name?: string;
      platform_price?: number;
      platform_sku_code?: string;
    },
  ) => http.post<PlatformMappingInfo>(`/skus/${skuId}/mappings`, payload),
  updateMapping: (
    id: number,
    payload: {
      platform?: string;
      platform_spec_name?: string;
      platform_price?: number;
      platform_sku_code?: string;
    },
  ) => http.put<PlatformMappingInfo>(`/mappings/${id}`, payload),
  deleteMapping: (id: number) => http.del<{ ok: boolean }>(`/mappings/${id}`),

  competitors: (productId: number) =>
    http.get<CompetitorInfo[]>(`/products/${productId}/competitors`),
  createCompetitor: (productId: number, payload: CompetitorPayload) =>
    http.post<CompetitorInfo>(`/products/${productId}/competitors`, payload),
  updateCompetitor: (id: number, payload: Partial<CompetitorPayload>) =>
    http.put<CompetitorInfo>(`/competitors/${id}`, payload),
  deleteCompetitor: (id: number) => http.del<{ ok: boolean }>(`/competitors/${id}`),
  parseCompetitor: (productId: number, text: string) =>
    http.post<CompetitorParseResult>(`/products/${productId}/competitors/parse`, { text }),

  diagnoses: (productId: number) => http.get<DiagnosisInfo[]>(`/products/${productId}/diagnoses`),
  generateDiagnosis: (productId: number, sourceReportId?: number | null) =>
    http.post<DiagnosisInfo>(`/products/${productId}/diagnoses/generate`, {
      source_report_id: sourceReportId ?? null,
    }),
  updateDiagnosis: (id: number, content: DiagnosisContent) =>
    http.put<DiagnosisInfo>(`/diagnoses/${id}`, { content_json: content }),

  creativePlans: (productId: number) =>
    http.get<CreativePlanInfo[]>(`/products/${productId}/creative-plans`),
  generateCreativePlan: (productId: number, diagnosisId?: number | null) =>
    http.post<CreativePlanInfo>(`/products/${productId}/creative-plans/generate`, {
      diagnosis_id: diagnosisId ?? null,
    }),
  updateImageScheme: (id: number, payload: ImageSchemePayload) =>
    http.put<ImageSchemeInfo>(`/image-schemes/${id}`, payload),
  confirmImageScheme: (id: number) =>
    http.post<ImageSchemeInfo>(`/image-schemes/${id}/confirm`),
  archiveImageScheme: (id: number) =>
    http.post<ImageSchemeInfo>(`/image-schemes/${id}/archive`),
  updateVideoScript: (id: number, payload: VideoScriptPayload) =>
    http.put<VideoScriptInfo>(`/video-scripts/${id}`, payload),
  confirmVideoScript: (id: number) =>
    http.post<VideoScriptInfo>(`/video-scripts/${id}/confirm`),
  archiveVideoScript: (id: number) =>
    http.post<VideoScriptInfo>(`/video-scripts/${id}/archive`),
  createVideoShot: (scriptId: number, payload: Required<VideoShotPayload>) =>
    http.post<VideoShotInfo>(`/video-scripts/${scriptId}/shots`, payload),
  updateVideoShot: (id: number, payload: VideoShotPayload) =>
    http.put<VideoShotInfo>(`/video-shots/${id}`, payload),
  deleteVideoShot: (id: number) => http.del<{ ok: boolean }>(`/video-shots/${id}`),

  tasks: (productId?: number, status?: string) => {
    const qs = new URLSearchParams();
    if (productId) qs.set('product_id', String(productId));
    if (status) qs.set('status', status);
    const suffix = qs.toString() ? `?${qs}` : '';
    return http.get<GenerationTaskInfo[]>(`/tasks${suffix}`);
  },
  task: (id: number) => http.get<GenerationTaskInfo>(`/tasks/${id}`),
  createTask: (sourceType: 'image_scheme' | 'video_script', sourceId: number) =>
    http.post<GenerationTaskInfo>('/tasks', { source_type: sourceType, source_id: sourceId }),
  cancelTask: (id: number) => http.post<GenerationTaskInfo>(`/tasks/${id}/cancel`),
  retryTask: (id: number) => http.post<GenerationTaskInfo>(`/tasks/${id}/retry`),

  assets: (productId: number, filters?: AssetFilters) => {
    const qs = new URLSearchParams();
    if (filters?.type) qs.set('type', filters.type);
    if (filters?.status) qs.set('status', filters.status);
    const suffix = qs.toString() ? `?${qs}` : '';
    return http.get<AssetInfo[]>(`/products/${productId}/assets${suffix}`);
  },
  reviewAsset: (id: number, action: 'approve' | 'reject', note: string) =>
    http.post<AssetInfo>(`/assets/${id}/review`, { action, note }),
  updateAssetTags: (id: number, tags: string[]) =>
    http.put<AssetInfo>(`/assets/${id}/tags`, { tags }),
  archiveAsset: (id: number) => http.post<AssetInfo>(`/assets/${id}/archive`),

  resetDemo: () => http.post<{ ok: boolean; message: string }>('/demo/reset'),
};

export type {
  CompetitorDraft,
  CompetitorInfo,
  CompetitorParseResult,
  DiagnosisContent,
  DiagnosisInfo,
  PlatformMappingInfo,
  StockFlowInfo,
};
