import { useMemo, useState } from 'react';
import {
  App,
  Button,
  Empty,
  Input,
  Modal,
  Segmented,
  Select,
  Space,
  Tag,
} from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  DownloadOutlined,
  EyeOutlined,
  InboxOutlined,
  TagsOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { api } from '../../api';
import type { AssetInfo, AssetStatus } from '../../api/types';
import { assetStatusColor, assetStatusLabel } from '../../utils/catalog';

interface Props {
  assets: AssetInfo[];
  onRefresh: () => void;
}

type TypeFilter = 'all' | 'image' | 'video';
type StatusFilter = 'all' | AssetStatus;

const STATUS_OPTIONS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: '全部状态' },
  { value: 'pending_review', label: '待审核' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
  { value: 'archived', label: '已归档' },
];

export function AssetLibrary({ assets, onRefresh }: Props) {
  const { message, modal } = App.useApp();
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [preview, setPreview] = useState<AssetInfo | null>(null);
  const [review, setReview] = useState<{ asset: AssetInfo; action: 'approve' | 'reject' } | null>(
    null,
  );
  const [reviewNote, setReviewNote] = useState('');
  const [reviewing, setReviewing] = useState(false);
  const [tagAsset, setTagAsset] = useState<AssetInfo | null>(null);
  const [tagValues, setTagValues] = useState<string[]>([]);
  const [savingTags, setSavingTags] = useState(false);

  const filtered = useMemo(
    () =>
      assets.filter((asset) => {
        if (typeFilter !== 'all' && asset.type !== typeFilter) return false;
        if (statusFilter !== 'all' && asset.status !== statusFilter) return false;
        return true;
      }),
    [assets, typeFilter, statusFilter],
  );

  const openReview = (asset: AssetInfo, action: 'approve' | 'reject') => {
    setReview({ asset, action });
    setReviewNote(asset.review_note || '');
  };

  const submitReview = async () => {
    if (!review) return;
    if (review.action === 'reject' && !reviewNote.trim()) {
      message.warning('驳回素材需要填写审核备注');
      return;
    }
    setReviewing(true);
    try {
      await api.reviewAsset(review.asset.id, review.action, reviewNote.trim());
      message.success(review.action === 'approve' ? '素材已审核通过' : '素材已驳回');
      setReview(null);
      onRefresh();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setReviewing(false);
    }
  };

  const openTags = (asset: AssetInfo) => {
    setTagAsset(asset);
    setTagValues(asset.tags_json || []);
  };

  const saveTags = async () => {
    if (!tagAsset) return;
    setSavingTags(true);
    try {
      await api.updateAssetTags(tagAsset.id, tagValues);
      message.success('素材标签已更新');
      setTagAsset(null);
      onRefresh();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSavingTags(false);
    }
  };

  const archive = (asset: AssetInfo) => {
    modal.confirm({
      title: `归档素材 #${asset.id}`,
      content: '归档后素材仍可预览与下载，但不再参与投放素材组合。',
      okText: '归档',
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.archiveAsset(asset.id);
          message.success('素材已归档');
          onRefresh();
        } catch (error) {
          message.error((error as Error).message);
        }
      },
    });
  };

  return (
    <>
      <div className="asset-toolbar">
        <Space wrap>
          <Segmented
            value={typeFilter}
            onChange={(value) => setTypeFilter(value as TypeFilter)}
            options={[
              { label: '全部素材', value: 'all' },
              { label: '图片', value: 'image' },
              { label: '视频', value: 'video' },
            ]}
          />
          <Select
            value={statusFilter}
            style={{ width: 140 }}
            options={STATUS_OPTIONS}
            onChange={(value) => setStatusFilter(value as StatusFilter)}
          />
        </Space>
        <span className="muted">
          共 {assets.length} 个素材，当前展示 {filtered.length} 个
        </span>
      </div>

      {filtered.length ? (
        <div className="asset-grid">
          {filtered.map((asset) => (
            <div className={`asset-card${asset.status === 'archived' ? ' is-archived' : ''}`} key={asset.id}>
              <div className="asset-preview">
                <img src={asset.file_path} alt={asset.filename} loading="lazy" />
                <div className="asset-overlay">
                  <Button
                    size="small"
                    icon={<EyeOutlined />}
                    onClick={() => setPreview(asset)}
                  >
                    预览
                  </Button>
                  <Button
                    size="small"
                    icon={<DownloadOutlined />}
                    href={asset.file_path}
                    download={asset.filename}
                  >
                    下载
                  </Button>
                </div>
                <Tag className="asset-type-badge" color={asset.type === 'video' ? 'purple' : 'cyan'}>
                  {asset.type === 'video' ? '视频' : '图片'}
                </Tag>
              </div>
              <div className="asset-body">
                <div className="asset-title">
                  素材 #{asset.id} · v{asset.version}
                </div>
                <div className="asset-meta">
                  <Tag bordered={false} color={assetStatusColor(asset.status)}>
                    {assetStatusLabel(asset.status)}
                  </Tag>
                  <span className="muted">{dayjs(asset.created_at).format('MM-DD HH:mm')}</span>
                </div>
                <div className="asset-tags">
                  {(asset.tags_json || []).map((tag) => (
                    <Tag key={tag} bordered={false} className="spec-tag">
                      {tag}
                    </Tag>
                  ))}
                  {!asset.tags_json?.length && <span className="muted">未打标</span>}
                </div>
                {asset.review_note && (
                  <div className="asset-note">
                    {asset.reviewed_by_name ? `${asset.reviewed_by_name}：` : ''}
                    {asset.review_note}
                  </div>
                )}
              </div>
              <div className="asset-actions">
                {asset.status === 'pending_review' && (
                  <>
                    <Button
                      size="small"
                      type="primary"
                      ghost
                      icon={<CheckOutlined />}
                      onClick={() => openReview(asset, 'approve')}
                    >
                      通过
                    </Button>
                    <Button
                      size="small"
                      danger
                      icon={<CloseOutlined />}
                      onClick={() => openReview(asset, 'reject')}
                    >
                      驳回
                    </Button>
                  </>
                )}
                {asset.status === 'approved' && (
                  <Button
                    size="small"
                    icon={<InboxOutlined />}
                    onClick={() => archive(asset)}
                  >
                    归档
                  </Button>
                )}
                <Button
                  size="small"
                  icon={<TagsOutlined />}
                  onClick={() => openTags(asset)}
                >
                  打标
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            assets.length
              ? '当前筛选条件下没有素材'
              : '暂无素材，任务生成成功后会自动入库'
          }
        />
      )}

      <Modal
        open={!!preview}
        title={preview ? `素材预览 · ${preview.filename}` : '素材预览'}
        footer={null}
        width={760}
        onCancel={() => setPreview(null)}
        destroyOnHidden
      >
        {preview && (
          <div className="asset-preview-modal">
            <img src={preview.file_path} alt={preview.filename} />
            <div className="muted">
              {preview.type === 'video' ? '视频动效预览（SVG）' : '主图素材（SVG）'} · 素材 #
              {preview.id} · v{preview.version}
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={!!review}
        title={
          review?.action === 'approve'
            ? `审核通过素材 #${review.asset.id}`
            : `驳回素材 #${review?.asset.id}`
        }
        okText={review?.action === 'approve' ? '确认通过' : '确认驳回'}
        cancelText="取消"
        confirmLoading={reviewing}
        okButtonProps={review?.action === 'reject' ? { danger: true } : undefined}
        onOk={submitReview}
        onCancel={() => setReview(null)}
        destroyOnHidden
      >
        <label className="field-label">
          {review?.action === 'reject' ? '驳回原因（必填）' : '审核备注（可选）'}
        </label>
        <Input.TextArea
          rows={4}
          value={reviewNote}
          onChange={(event) => setReviewNote(event.target.value)}
          placeholder={
            review?.action === 'reject'
              ? '例如：文案与诊断卖点不一致，请调整后重新生成'
              : '例如：构图清晰、卖点表达准确，可进入投放素材组合'
          }
        />
      </Modal>

      <Modal
        open={!!tagAsset}
        title={`素材打标 · #${tagAsset?.id ?? ''}`}
        okText="保存标签"
        cancelText="取消"
        confirmLoading={savingTags}
        onOk={saveTags}
        onCancel={() => setTagAsset(null)}
        destroyOnHidden
      >
        <label className="field-label">标签（回车添加，最多 10 个）</label>
        <Select
          mode="tags"
          value={tagValues}
          onChange={setTagValues}
          style={{ width: '100%' }}
          placeholder="例如：通勤场景、温控卖点、A/B 组"
          tokenSeparators={[',', '，']}
        />
      </Modal>
    </>
  );
}
