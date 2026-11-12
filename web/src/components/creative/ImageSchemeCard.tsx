import { useEffect, useState } from 'react';
import { App, Button, Card, Input, Tag, Tooltip } from 'antd';
import {
  CheckOutlined,
  EditOutlined,
  InboxOutlined,
  PictureOutlined,
  SaveOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { api } from '../../api';
import type { ImageSchemeInfo } from '../../api/types';
import { creativeStatusColor, creativeStatusLabel } from '../../utils/catalog';

interface Props {
  scheme: ImageSchemeInfo;
  onChanged: () => void;
  onGenerate: (scheme: ImageSchemeInfo) => void;
  generating?: boolean;
  isService?: boolean;
}

interface Draft {
  title: string;
  copy: string;
  layout: string;
  main_selling_point: string;
  visual_tip: string;
}

function toDraft(scheme: ImageSchemeInfo): Draft {
  return {
    title: scheme.title,
    copy: scheme.copy,
    layout: scheme.layout,
    main_selling_point: scheme.main_selling_point,
    visual_tip: scheme.visual_tip,
  };
}

export function ImageSchemeCard({
  scheme,
  onChanged,
  onGenerate,
  generating,
  isService = false,
}: Props) {
  const { message } = App.useApp();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<Draft>(toDraft(scheme));

  useEffect(() => {
    setDraft(toDraft(scheme));
    setEditing(false);
  }, [scheme]);

  const save = async () => {
    if (!draft.title.trim()) {
      message.warning('方案标题不能为空');
      return;
    }
    setSaving(true);
    try {
      await api.updateImageScheme(scheme.id, draft);
      message.success(isService ? '获客素材方案已保存' : '主图方案已保存');
      setEditing(false);
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const setStatus = async (action: 'confirm' | 'archive') => {
    try {
      if (action === 'confirm') {
        await api.confirmImageScheme(scheme.id);
        message.success(isService ? '获客素材方案已确认' : '主图方案已确认');
      } else {
        await api.archiveImageScheme(scheme.id);
        message.success(isService ? '获客素材方案已归档' : '主图方案已归档');
      }
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const archived = scheme.status === 'archived';

  return (
    <Card
      className={`creative-card${archived ? ' is-archived' : ''}`}
      title={
        <div>
          <div className="card-title">
            <PictureOutlined /> {scheme.title}
          </div>
          <div className="card-subtitle">
            {isService ? '获客素材方向' : '主图方向'} {scheme.order_no}
          </div>
        </div>
      }
      extra={
        <Tag bordered={false} color={creativeStatusColor(scheme.status)}>
          {creativeStatusLabel(scheme.status)}
        </Tag>
      }
    >
      {editing ? (
        <div className="creative-editor">
          <label className="field-label">方案标题</label>
          <Input
            value={draft.title}
            onChange={(event) => setDraft({ ...draft, title: event.target.value })}
          />
          <label className="field-label">{isService ? '素材文案' : '主图文案'}</label>
          <Input.TextArea
            rows={2}
            value={draft.copy}
            onChange={(event) => setDraft({ ...draft, copy: event.target.value })}
          />
          <label className="field-label">构图说明</label>
          <Input.TextArea
            rows={3}
            value={draft.layout}
            onChange={(event) => setDraft({ ...draft, layout: event.target.value })}
          />
          <label className="field-label">核心卖点</label>
          <Input.TextArea
            rows={2}
            value={draft.main_selling_point}
            onChange={(event) => setDraft({ ...draft, main_selling_point: event.target.value })}
          />
          <label className="field-label">视觉提示</label>
          <Input.TextArea
            rows={2}
            value={draft.visual_tip}
            onChange={(event) => setDraft({ ...draft, visual_tip: event.target.value })}
          />
          <div className="creative-card-actions">
            <Button onClick={() => setEditing(false)}>取消</Button>
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
              保存
            </Button>
          </div>
        </div>
      ) : (
        <>
          <p className="scheme-copy">
            {scheme.copy || (isService ? '未填写素材文案' : '未填写主图文案')}
          </p>
          <div className="scheme-field">
            <span className="field-label">核心卖点</span>
            <p>{scheme.main_selling_point || '—'}</p>
          </div>
          <div className="scheme-field">
            <span className="field-label">构图说明</span>
            <p>{scheme.layout || '—'}</p>
          </div>
          <div className="scheme-field">
            <span className="field-label">视觉提示</span>
            <p>{scheme.visual_tip || '—'}</p>
          </div>
          <div className="creative-card-actions">
            {!archived && (
              <Button size="small" icon={<EditOutlined />} onClick={() => setEditing(true)}>
                编辑
              </Button>
            )}
            {scheme.status === 'draft' && (
              <Button
                size="small"
                icon={<CheckOutlined />}
                onClick={() => setStatus('confirm')}
              >
                确认
              </Button>
            )}
            {!archived && (
              <Tooltip title="归档后不再参与素材生成与投放组合">
                <Button
                  size="small"
                  icon={<InboxOutlined />}
                  onClick={() => setStatus('archive')}
                >
                  归档
                </Button>
              </Tooltip>
            )}
            <Button
              size="small"
              type="primary"
              ghost
              icon={<ThunderboltOutlined />}
              disabled={archived}
              loading={generating}
              onClick={() => onGenerate(scheme)}
            >
              生成素材
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}
