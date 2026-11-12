import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Card,
  Empty,
  Input,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  BulbOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
  ThunderboltOutlined,
  UserOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { api } from '../../api';
import type {
  DiagnosisContent,
  DiagnosisInfo,
  SellingPoint,
} from '../../api/types';
import { channelLabel } from '../../utils/catalog';

interface Props {
  productId: number;
  diagnoses: DiagnosisInfo[];
  loading: boolean;
  onChanged: () => void;
}

function cloneContent(content: DiagnosisContent): DiagnosisContent {
  return JSON.parse(JSON.stringify(content));
}

function ListEditor({
  items,
  onChange,
  placeholder,
}: {
  items: string[];
  onChange: (items: string[]) => void;
  placeholder: string;
}) {
  return (
    <div className="kv-editor">
      {items.map((item, index) => (
        <div className="kv-row" key={index}>
          <Input
            value={item}
            placeholder={placeholder}
            onChange={(event) => {
              const next = [...items];
              next[index] = event.target.value;
              onChange(next);
            }}
          />
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => onChange(items.filter((_, i) => i !== index))}
          />
        </div>
      ))}
      <Button type="dashed" block icon={<PlusOutlined />} onClick={() => onChange([...items, ''])}>
        添加一条
      </Button>
    </div>
  );
}

function DiagnosisEditor({
  draft,
  setDraft,
}: {
  draft: DiagnosisContent;
  setDraft: (value: DiagnosisContent) => void;
}) {
  const update = (patch: Partial<DiagnosisContent>) => setDraft({ ...draft, ...patch });
  const updateAudience = (patch: Partial<DiagnosisContent['audience']>) =>
    setDraft({ ...draft, audience: { ...draft.audience, ...patch } });
  const updatePrice = (patch: Partial<DiagnosisContent['price_analysis']>) =>
    setDraft({ ...draft, price_analysis: { ...draft.price_analysis, ...patch } });

  const updatePoint = (index: number, patch: Partial<SellingPoint>) => {
    const next = draft.selling_points.map((item, i) => (i === index ? { ...item, ...patch } : item));
    update({ selling_points: next });
  };

  return (
    <div className="diagnosis-editor">
      <div className="diag-section">
        <div className="diag-section-head">
          <span className="diag-title">
            <UserOutlined /> 目标客群
          </span>
        </div>
        <label className="field-label">人群画像</label>
        <Input.TextArea
          rows={2}
          value={draft.audience.persona}
          onChange={(event) => updateAudience({ persona: event.target.value })}
        />
        <label className="field-label">核心需求</label>
        <ListEditor
          items={draft.audience.needs}
          onChange={(needs) => updateAudience({ needs })}
          placeholder="例如：UPF50+ 有效防晒"
        />
        <label className="field-label">使用场景</label>
        <ListEditor
          items={draft.audience.scenarios}
          onChange={(scenarios) => updateAudience({ scenarios })}
          placeholder="例如：通勤骑行"
        />
      </div>

      <div className="diag-section">
        <div className="diag-section-head">
          <span className="diag-title">
            <BulbOutlined /> 价格分析
          </span>
        </div>
        <label className="field-label">价格定位</label>
        <Input.TextArea
          rows={2}
          value={draft.price_analysis.position}
          onChange={(event) => updatePrice({ position: event.target.value })}
        />
        <label className="field-label">竞品价格带</label>
        <Input.TextArea
          rows={2}
          value={draft.price_analysis.competitor_range}
          onChange={(event) => updatePrice({ competitor_range: event.target.value })}
        />
        <label className="field-label">定价建议</label>
        <Input.TextArea
          rows={2}
          value={draft.price_analysis.suggestion}
          onChange={(event) => updatePrice({ suggestion: event.target.value })}
        />
      </div>

      <div className="diag-section">
        <div className="diag-section-head">
          <span className="diag-title">
            <ThunderboltOutlined /> 卖点矩阵
          </span>
        </div>
        {draft.selling_points.map((point, index) => (
          <div className="selling-point-edit" key={index}>
            <div className="selling-point-edit-head">
              <span className="muted">卖点 {index + 1}</span>
              <Button
                type="text"
                danger
                size="small"
                icon={<DeleteOutlined />}
                onClick={() =>
                  update({ selling_points: draft.selling_points.filter((_, i) => i !== index) })
                }
              />
            </div>
            <label className="selling-field">
              <span className="selling-field-label">卖点</span>
              <Input
                value={point.point}
                placeholder="一句话概括核心卖点"
                onChange={(event) => updatePoint(index, { point: event.target.value })}
              />
            </label>
            <label className="selling-field">
              <span className="selling-field-label">支撑证据</span>
              <Input
                value={point.evidence}
                placeholder="数据、材质或用户评价"
                onChange={(event) => updatePoint(index, { evidence: event.target.value })}
              />
            </label>
            <label className="selling-field">
              <span className="selling-field-label">竞品差异</span>
              <Input
                value={point.diff}
                placeholder="与竞品相比的差异化优势"
                onChange={(event) => updatePoint(index, { diff: event.target.value })}
              />
            </label>
          </div>
        ))}
        <Button
          type="dashed"
          block
          icon={<PlusOutlined />}
          onClick={() =>
            update({ selling_points: [...draft.selling_points, { point: '', evidence: '', diff: '' }] })
          }
        >
          添加卖点
        </Button>
      </div>

      <div className="diag-section">
        <div className="diag-section-head">
          <span className="diag-title">
            <WarningOutlined /> 转化卡点
          </span>
        </div>
        <ListEditor
          items={draft.conversion_blockers}
          onChange={(conversion_blockers) => update({ conversion_blockers })}
          placeholder="例如：详情页缺少实测数据"
        />
      </div>

      <div className="diag-section">
        <div className="diag-section-head">
          <span className="diag-title">
            <BulbOutlined /> 优化方向
          </span>
        </div>
        <ListEditor
          items={draft.optimization_directions}
          onChange={(optimization_directions) => update({ optimization_directions })}
          placeholder="例如：主图增加温度对比模块"
        />
      </div>
    </div>
  );
}

function DiagnosisView({ content }: { content: DiagnosisContent }) {
  const pointColumns: ColumnsType<SellingPoint> = [
    {
      title: '卖点',
      dataIndex: 'point',
      key: 'point',
      width: 170,
      render: (value: string) => <span className="cell-strong">{value || '—'}</span>,
    },
    {
      title: '支撑证据',
      dataIndex: 'evidence',
      key: 'evidence',
      render: (value: string) => value || '—',
    },
    {
      title: '竞品差异',
      dataIndex: 'diff',
      key: 'diff',
      render: (value: string) => value || '—',
    },
  ];

  return (
    <div className="diagnosis-view">
      <div className="diagnosis-two-col">
        <div className="diag-section">
          <div className="diag-section-head">
            <span className="diag-title">
              <UserOutlined /> 目标客群
            </span>
          </div>
          <p className="diag-persona">{content.audience.persona}</p>
          <div className="diag-tag-row">
            <span className="field-label inline">核心需求</span>
            {content.audience.needs.map((need) => (
              <Tag key={need} bordered={false} color="cyan">
                {need}
              </Tag>
            ))}
          </div>
          <div className="diag-tag-row">
            <span className="field-label inline">使用场景</span>
            {content.audience.scenarios.map((scene) => (
              <Tag key={scene} bordered={false}>
                {scene}
              </Tag>
            ))}
          </div>
        </div>

        <div className="diag-section">
          <div className="diag-section-head">
            <span className="diag-title">
              <BulbOutlined /> 价格分析
            </span>
          </div>
          <div className="diag-kv">
            <span className="field-label">价格定位</span>
            <p>{content.price_analysis.position}</p>
          </div>
          <div className="diag-kv">
            <span className="field-label">竞品价格带</span>
            <p>{content.price_analysis.competitor_range}</p>
          </div>
          <div className="diag-kv">
            <span className="field-label">定价建议</span>
            <p>{content.price_analysis.suggestion}</p>
          </div>
        </div>
      </div>

      <div className="diag-section">
        <div className="diag-section-head">
          <span className="diag-title">
            <ThunderboltOutlined /> 卖点矩阵
          </span>
        </div>
        <Table
          rowKey={(record) => `${record.point}|${record.evidence}|${record.diff}`}
          size="small"
          columns={pointColumns}
          dataSource={content.selling_points}
          pagination={false}
        />
      </div>

      <div className="diagnosis-two-col">
        <div className="diag-section">
          <div className="diag-section-head">
            <span className="diag-title">
              <WarningOutlined /> 转化卡点
            </span>
            <Tag bordered={false} color="orange">
              {content.conversion_blockers.length} 项
            </Tag>
          </div>
          <ol className="diag-list">
            {content.conversion_blockers.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </div>

        <div className="diag-section">
          <div className="diag-section-head">
            <span className="diag-title">
              <BulbOutlined /> 优化方向
            </span>
            <Tag bordered={false} color="green">
              {content.optimization_directions.length} 项
            </Tag>
          </div>
          <ol className="diag-list">
            {content.optimization_directions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}

export function DiagnosisBoard({ productId, diagnoses, loading, onChanged }: Props) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [preferId, setPreferId] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<DiagnosisContent | null>(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const { message, modal } = App.useApp();

  const current = useMemo(
    () => diagnoses.find((item) => item.status === 'current') || diagnoses[0] || null,
    [diagnoses],
  );

  const selected = useMemo(
    () => diagnoses.find((item) => item.id === selectedId) || current,
    [diagnoses, selectedId, current],
  );

  useEffect(() => {
    if (!diagnoses.length) {
      setSelectedId(null);
      setEditing(false);
      setDraft(null);
      return;
    }
    if (preferId && diagnoses.some((item) => item.id === preferId)) {
      setSelectedId(preferId);
      setPreferId(null);
      return;
    }
    if (!selectedId || !diagnoses.some((item) => item.id === selectedId)) {
      setSelectedId(current?.id ?? diagnoses[0].id);
    }
  }, [diagnoses, selectedId, current, preferId]);

  useEffect(() => {
    if (selected && !editing) {
      setDraft(cloneContent(selected.content_json));
    }
  }, [selected, editing]);

  const versionOptions = diagnoses.map((item) => ({
    value: item.id,
    label: `v${item.version} · ${item.status === 'current' ? '当前结论' : '历史版本'} · ${dayjs(
      item.created_at,
    ).format('MM-DD HH:mm')}`,
  }));

  const startEdit = () => {
    if (!selected) return;
    setDraft(cloneContent(selected.content_json));
    setEditing(true);
  };

  const save = async () => {
    if (!selected || !draft) return;
    setSaving(true);
    try {
      await api.updateDiagnosis(selected.id, draft);
      message.success('诊断内容已保存');
      setEditing(false);
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const generate = () => {
    const nextVersion = Math.max(0, ...diagnoses.map((item) => item.version)) + 1;
    modal.confirm({
      title: diagnoses.length ? `生成诊断 v${nextVersion}` : '生成结构化诊断',
      content: diagnoses.length
        ? '将基于最新商品、SKU 与竞品数据生成新版本，原当前结论自动转为历史版本。'
        : '将基于商品档案、SKU 价格带与已录入竞品生成结构化诊断。',
      okText: '生成',
      cancelText: '取消',
      onOk: async () => {
        setGenerating(true);
        try {
          const result = await api.generateDiagnosis(productId);
          message.success(
            `诊断 v${result.version} 已生成（${channelLabel(result.generate_channel || result.channel)}）`,
          );
          setEditing(false);
          setPreferId(result.id);
          onChanged();
        } catch (error) {
          message.error((error as Error).message);
        } finally {
          setGenerating(false);
        }
      },
    });
  };

  return (
    <Card
      className="surface-card"
      title={
        <div>
          <div className="card-title">智能诊断看板</div>
          <div className="card-subtitle">目标客群 · 价格分析 · 卖点矩阵 · 转化卡点 · 优化方向</div>
        </div>
      }
      extra={
        <Space wrap>
          {diagnoses.length > 0 && (
            <Select
              value={selected?.id}
              style={{ width: 250 }}
              options={versionOptions}
              onChange={(value) => {
                setEditing(false);
                setSelectedId(value);
              }}
            />
          )}
          {selected?.status === 'current' && !editing && (
            <Tooltip title="编辑当前结论，所有字段均可修改">
              <Button icon={<EditOutlined />} onClick={startEdit}>
                编辑
              </Button>
            </Tooltip>
          )}
          {editing && (
            <>
              <Button onClick={() => setEditing(false)}>取消</Button>
              <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
                保存诊断
              </Button>
            </>
          )}
          <Button
            type={diagnoses.length ? 'default' : 'primary'}
            icon={diagnoses.length ? <ReloadOutlined /> : <ThunderboltOutlined />}
            loading={generating}
            onClick={generate}
          >
            {diagnoses.length
              ? `重新生成 v${Math.max(...diagnoses.map((item) => item.version)) + 1}`
              : '生成诊断'}
          </Button>
        </Space>
      }
    >
      <Spin spinning={loading || generating}>
        {!selected ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="该商品还没有诊断结论，生成后即可进入创意方案阶段"
          >
            <Button type="primary" icon={<ThunderboltOutlined />} onClick={generate}>
              生成第一版诊断
            </Button>
          </Empty>
        ) : (
          <>
            <div className="diagnosis-meta">
              <Space wrap>
                <Tag bordered={false} color={selected.status === 'current' ? 'green' : 'default'}>
                  {selected.status === 'current' ? '当前结论' : '历史版本'}
                </Tag>
                <Tag bordered={false} color="blue">
                  {channelLabel(selected.channel)}
                </Tag>
                <span className="muted">模型 {selected.model}</span>
                <span className="muted">
                  更新于 {dayjs(selected.updated_at).format('YYYY-MM-DD HH:mm')}
                </span>
                {selected.source_report_id && (
                  <Tag bordered={false} color="purple">
                    来源复盘报告 #{selected.source_report_id}
                  </Tag>
                )}
              </Space>
              {selected.status !== 'current' && (
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginTop: 12 }}
                  message="当前查看的是历史版本，仅供对照，不可编辑"
                />
              )}
            </div>
            {editing && draft ? (
              <DiagnosisEditor draft={draft} setDraft={setDraft} />
            ) : (
              <DiagnosisView content={selected.content_json} />
            )}
          </>
        )}
      </Spin>
    </Card>
  );
}
