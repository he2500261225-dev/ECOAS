export type Role = 'operator' | 'manager';

export interface User {
  id: number;
  username: string;
  display_name: string;
  role: Role;
}

export interface StoreInfo {
  id: number;
  name: string;
  platform: string;
  auth_status: string;
  auth_ref?: string;
  product_count: number;
  stock_warning_count: number;
}

export type Stage =
  | 'draft'
  | 'diagnosed'
  | 'creative_ready'
  | 'asset_ready'
  | 'launching'
  | 'reviewing'
  | 'reviewed';

export interface ProductSummary {
  id: number;
  name: string;
  category: string;
  is_service: boolean;
  price_unit: string;
  price_min: number;
  price_max: number;
  description: string;
  store: { id: number; name: string; platform: string };
  sku_count: number;
  main_sku_spec: Record<string, string> | null;
  warning_sku_count: number;
  asset_count: number;
  archived?: boolean;
  stage: Stage;
  stage_label: string;
  updated_at: string;
}

export interface PlatformMappingInfo {
  id: number;
  sku_id: number;
  platform: string;
  platform_spec_name: string;
  platform_price: number;
  platform_sku_code: string;
}

export interface SkuInfo {
  id: number;
  spec: Record<string, string>;
  price: number;
  stock: number;
  warn_threshold: number;
  warning: boolean;
  mappings: PlatformMappingInfo[];
}

export interface ProductDetail {
  id: number;
  name: string;
  category: string;
  is_service: boolean;
  price_unit: string;
  price_min: number;
  price_max: number;
  description: string;
  store: { id: number; name: string; platform: string };
  main_sku_id: number | null;
  skus: SkuInfo[];
  archived: boolean;
  stage: Stage;
  stage_label: string;
  created_at: string;
  updated_at: string;
}

export interface StockFlowInfo {
  id: number;
  sku_id: number;
  change: number;
  reason: string;
  stock_after: number;
  operator_id: number | null;
  operator_name: string;
  created_at: string;
}

export interface CompetitorInfo {
  id: number;
  product_id: number;
  platform: string;
  name: string;
  price: number;
  url: string;
  params_json: Record<string, string>;
  sales_volume: number;
  rating: number;
  source: string;
  parse_status: string;
  created_at: string;
}

export interface CompetitorDraft {
  platform: string;
  name: string;
  price: number;
  url: string;
  params_json: Record<string, string>;
  sales_volume: number;
  rating: number;
  source: string;
  parse_status: string;
}

export interface CompetitorParseResult {
  drafts: CompetitorDraft[];
  channel: string;
  model: string;
  note: string;
  warnings: string[];
}

export interface SellingPoint {
  point: string;
  evidence: string;
  diff: string;
}

export interface DiagnosisContent {
  audience: {
    persona: string;
    needs: string[];
    scenarios: string[];
  };
  price_analysis: {
    position: string;
    competitor_range: string;
    suggestion: string;
  };
  selling_points: SellingPoint[];
  conversion_blockers: string[];
  optimization_directions: string[];
}

export interface DiagnosisInfo {
  id: number;
  product_id: number;
  version: number;
  status: 'current' | 'history';
  content_json: DiagnosisContent;
  source_report_id: number | null;
  model: string;
  channel: 'mock' | 'real' | 'mock_fallback';
  created_by: number | null;
  created_at: string;
  updated_at: string;
  generate_channel?: string;
  note?: string;
  warnings?: string[];
}

export type CreativeStatus = 'draft' | 'confirmed' | 'archived';

export interface ImageSchemeInfo {
  id: number;
  plan_id: number;
  order_no: number;
  title: string;
  layout: string;
  copy: string;
  main_selling_point: string;
  visual_tip: string;
  status: CreativeStatus;
}

export interface VideoShotInfo {
  id: number;
  script_id: number;
  shot_no: number;
  duration_sec: number;
  scene_desc: string;
  voiceover: string;
  cta_line: string;
}

export interface VideoScriptInfo {
  id: number;
  plan_id: number;
  order_no: number;
  title: string;
  hook_3s: string;
  closing_cta: string;
  status: CreativeStatus;
  shots: VideoShotInfo[];
  total_duration: number;
}

export interface CreativePlanInfo {
  id: number;
  product_id: number;
  diagnosis_id: number | null;
  version: number;
  status: CreativeStatus;
  created_at: string;
  image_schemes: ImageSchemeInfo[];
  video_scripts: VideoScriptInfo[];
  generate_channel?: string;
  model?: string;
  note?: string;
  warnings?: string[];
}

export type TaskStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'timeout'
  | 'cancelled';

export interface TaskAttemptInfo {
  id: number;
  task_id: number;
  attempt_no: number;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  error_message: string;
}

export interface TaskAttachment {
  kind: string;
  name: string;
  url: string;
}

export interface GenerationTaskInfo {
  id: number;
  product_id: number;
  type: 'image' | 'video';
  source_type: 'image_scheme' | 'video_script';
  source_id: number;
  source_title: string;
  plan_version: number | null;
  payload_json: Record<string, unknown>;
  status: TaskStatus;
  attempt: number;
  max_retry: number;
  timeout_seconds: number;
  worker_id: string | null;
  heartbeat_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string;
  result_asset_id: number | null;
  attachments: TaskAttachment[];
  result_meta: Record<string, unknown>;
  created_by: number | null;
  created_at: string;
  attempts: TaskAttemptInfo[];
}

export type AssetStatus = 'pending_review' | 'approved' | 'rejected' | 'archived';

export interface AssetInfo {
  id: number;
  product_id: number;
  task_id: number | null;
  type: 'image' | 'video';
  source_type: string;
  source_id: number | null;
  filename: string;
  file_path: string;
  mime: string;
  version: number;
  status: AssetStatus;
  tags_json: string[];
  review_note: string;
  reviewed_by: number | null;
  reviewed_by_name: string;
  reviewed_at: string | null;
  created_at: string;
}

export interface TrendPoint {
  date: string;
  gmv: number;
  orders: number;
  roi: number;
  impressions?: number;
  clicks?: number;
  spend?: number;
  ctr?: number;
  cvr?: number;
}

export interface StockWarning {
  product_id: number;
  product_name: string;
  sku_id: number;
  spec: Record<string, string>;
  stock: number;
  threshold: number;
  store_name: string;
  stage: Stage;
  stage_label: string;
}

export interface DashboardSummary {
  kpis: {
    product_total: number;
    on_sale_rate: number;
    active_products: number;
    stock_warning_count: number;
    gmv_30d: number;
    roi_30d: number;
    pending_approvals: number;
  };
  stores: StoreInfo[];
  stock_warnings: StockWarning[];
  trend: TrendPoint[];
}
