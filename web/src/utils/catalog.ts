export const PLATFORM_OPTIONS = [
  { value: 'taobao', label: '淘宝 / 天猫' },
  { value: 'jd', label: '京东' },
  { value: 'douyin', label: '抖音' },
  { value: 'pdd', label: '拼多多' },
  { value: 'local', label: '本地生活' },
];

export const SERVICE_CATEGORY_OPTIONS = [
  { value: '除甲醛服务', label: '除甲醛服务' },
  { value: '洗衣服务', label: '洗衣服务' },
];

export const SERVICE_CATEGORIES = SERVICE_CATEGORY_OPTIONS.map((item) => item.value);

export function isServiceCategory(category?: string | null): boolean {
  return SERVICE_CATEGORIES.includes((category || '').trim());
}

export function priceUnitSuffix(priceUnit?: string | null): string {
  const unit = (priceUnit || '').trim();
  if (!unit) return '';
  return unit.includes('/') ? unit.replace('元/', '/') : ` ${unit}`;
}

export function formatPriceBand(
  priceMin: number,
  priceMax: number,
  priceUnit?: string | null,
): string {
  const base =
    priceMax > priceMin ? `¥${priceMin}-${priceMax}` : `¥${priceMin}`;
  return `${base}${priceUnitSuffix(priceUnit)}`;
}

export const AUTH_STATUS_OPTIONS = [
  { value: 'authorized', label: '授权正常' },
  { value: 'pending', label: '待授权' },
  { value: 'expired', label: '授权已过期' },
  { value: 'revoked', label: '已撤销' },
];

export function specToText(spec: Record<string, string>): string {
  return Object.entries(spec)
    .map(([key, value]) => `${key}:${value}`)
    .join(', ');
}

export function textToSpec(text: string): Record<string, string> {
  const result: Record<string, string> = {};
  (text || '')
    .replace(/；/g, ';')
    .replace(/，/g, ',')
    .replace(/、/g, ',')
    .split(/[;,]/)
    .forEach((chunk) => {
      const part = chunk.trim();
      if (!part) return;
      const match = part.match(/^([^:：]+)[:：](.+)$/);
      if (match) {
        const key = match[1].trim();
        const value = match[2].trim();
        if (key && value) result[key] = value;
      } else {
        result['规格'] = part;
      }
    });
  return Object.keys(result).length ? result : { 规格: '标准' };
}

export function specLabel(spec: Record<string, string> | null | undefined): string {
  if (!spec) return '未设置';
  return Object.entries(spec)
    .map(([key, value]) => `${key} ${value}`)
    .join(' / ');
}

export function paramsToRows(params: Record<string, string>): Array<{ key: string; value: string }> {
  return Object.entries(params || {}).map(([key, value]) => ({ key, value }));
}

export function rowsToParams(rows?: Array<{ key?: string; value?: string }>): Record<string, string> {
  const result: Record<string, string> = {};
  (rows || []).forEach((row) => {
    const key = (row.key || '').trim();
    const value = (row.value || '').trim();
    if (key && value) result[key] = value;
  });
  return result;
}

export const STOCK_REASONS = [
  { value: 'restock', label: '补货入库' },
  { value: 'sale', label: '销售出库' },
  { value: 'return', label: '退货入库' },
  { value: 'audit', label: '盘点修正' },
  { value: 'manual', label: '手工调整' },
];

export function stockReasonLabel(reason: string): string {
  return STOCK_REASONS.find((item) => item.value === reason)?.label || reason;
}

export function channelLabel(channel?: string): string {
  if (channel === 'real') return '真实接口';
  if (channel === 'mock_fallback') return '真实接口失败已回退 Mock';
  return 'Mock 生成';
}

export function creativeStatusLabel(status: string): string {
  if (status === 'confirmed') return '已确认';
  if (status === 'archived') return '已归档';
  return '草稿';
}

export function creativeStatusColor(status: string): string {
  if (status === 'confirmed') return 'success';
  if (status === 'archived') return 'default';
  return 'processing';
}

export function taskStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: '排队中',
    running: '生成中',
    succeeded: '已完成',
    failed: '失败',
    timeout: '超时',
    cancelled: '已取消',
  };
  return labels[status] || status;
}

export function taskStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'default',
    running: 'processing',
    succeeded: 'success',
    failed: 'error',
    timeout: 'warning',
    cancelled: 'default',
  };
  return colors[status] || 'default';
}

export function assetStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending_review: '待审核',
    approved: '已通过',
    rejected: '已驳回',
    archived: '已归档',
  };
  return labels[status] || status;
}

export function assetStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending_review: 'processing',
    approved: 'success',
    rejected: 'error',
    archived: 'default',
  };
  return colors[status] || 'default';
}

export function taskSourceLabel(sourceType: string): string {
  return sourceType === 'video_script' ? '视频脚本' : '主图方案';
}
