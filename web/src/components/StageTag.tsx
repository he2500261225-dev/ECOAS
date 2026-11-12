import { Tag } from 'antd';
import type { Stage } from '../api/types';

const STAGE_COLORS: Record<Stage, string> = {
  draft: 'default',
  diagnosed: 'blue',
  creative_ready: 'cyan',
  asset_ready: 'geekblue',
  launching: 'orange',
  reviewing: 'purple',
  reviewed: 'green',
};

export function StageTag({ stage, label }: { stage: Stage; label: string }) {
  return (
    <Tag color={STAGE_COLORS[stage]} bordered={false} className="stage-tag">
      {label}
    </Tag>
  );
}

const PLATFORM_META: Record<string, { label: string; color: string }> = {
  taobao: { label: '淘宝 / 天猫', color: '#ea580c' },
  jd: { label: '京东', color: '#dc2626' },
  douyin: { label: '抖音', color: '#111827' },
  pdd: { label: '拼多多', color: '#dc2626' },
  local: { label: '本地生活', color: '#0d9488' },
};

export function PlatformTag({ platform }: { platform: string }) {
  const meta = PLATFORM_META[platform] || { label: platform, color: '#64748b' };
  return (
    <Tag color={meta.color} bordered={false}>
      {meta.label}
    </Tag>
  );
}

export function platformLabel(platform: string) {
  return PLATFORM_META[platform]?.label || platform;
}
