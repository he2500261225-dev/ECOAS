import { useEffect, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  DeleteOutlined,
  EditOutlined,
  LinkOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { api } from '../../api';
import type { CompetitorDraft, CompetitorInfo } from '../../api/types';
import { PLATFORM_OPTIONS, channelLabel, paramsToRows, rowsToParams } from '../../utils/catalog';
import { PlatformTag } from '../StageTag';

interface Props {
  productId: number;
}

function CompetitorFields() {
  return (
    <>
      <div className="form-two-col">
        <Form.Item name="platform" label="平台" rules={[{ required: true, message: '请选择平台' }]}>
          <Select options={PLATFORM_OPTIONS} />
        </Form.Item>
        <Form.Item name="name" label="竞品名称" rules={[{ required: true, message: '请输入竞品名称' }]}>
          <Input placeholder="例如：蕉下 冰丝防晒衣" />
        </Form.Item>
      </div>
      <div className="form-two-col">
        <Form.Item name="price" label="售价（¥）" rules={[{ required: true, message: '请输入售价' }]}>
          <InputNumber min={0} precision={2} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="sales_volume" label="月销量">
          <InputNumber min={0} precision={0} style={{ width: '100%' }} />
        </Form.Item>
      </div>
      <div className="form-two-col">
        <Form.Item name="rating" label="评分">
          <InputNumber min={0} max={5} step={0.1} precision={1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="url" label="商品链接">
          <Input placeholder="https://" />
        </Form.Item>
      </div>
      <Form.Item label="核心参数">
        <Form.List name="params">
          {(fields, { add, remove }) => (
            <div className="kv-editor">
              {fields.map((field) => (
                <div className="kv-row" key={field.key}>
                  <Form.Item name={[field.name, 'key']} noStyle>
                    <Input placeholder="参数名，如 UPF" />
                  </Form.Item>
                  <Form.Item name={[field.name, 'value']} noStyle>
                    <Input placeholder="参数值，如 50+" />
                  </Form.Item>
                  <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(field.name)} />
                </div>
              ))}
              <Button type="dashed" block icon={<PlusOutlined />} onClick={() => add({ key: '', value: '' })}>
                添加参数
              </Button>
            </div>
          )}
        </Form.List>
      </Form.Item>
    </>
  );
}

export function CompetitorPanel({ productId }: Props) {
  const [competitors, setCompetitors] = useState<CompetitorInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<CompetitorInfo | null>(null);
  const [parseOpen, setParseOpen] = useState(false);
  const [parseStep, setParseStep] = useState<'input' | 'preview'>('input');
  const [parseText, setParseText] = useState('');
  const [drafts, setDrafts] = useState<CompetitorDraft[]>([]);
  const [activeDraft, setActiveDraft] = useState(0);
  const [channel, setChannel] = useState('');
  const [parsing, setParsing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editForm] = Form.useForm();
  const [parseForm] = Form.useForm();
  const { message, modal } = App.useApp();

  const load = async () => {
    setLoading(true);
    try {
      setCompetitors(await api.competitors(productId));
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  const openCreate = () => {
    setEditing(null);
    setEditOpen(true);
  };

  const openEdit = (record: CompetitorInfo) => {
    setEditing(record);
    setEditOpen(true);
  };

  useEffect(() => {
    if (!editOpen) return;
    if (editing) {
      editForm.setFieldsValue({
        platform: editing.platform,
        name: editing.name,
        price: editing.price,
        sales_volume: editing.sales_volume,
        rating: editing.rating,
        url: editing.url,
        params: paramsToRows(editing.params_json).length
          ? paramsToRows(editing.params_json)
          : [{ key: '', value: '' }],
      });
    } else {
      editForm.resetFields();
      editForm.setFieldsValue({
        platform: 'taobao',
        price: 0,
        sales_volume: 0,
        rating: 0,
        params: [{ key: '', value: '' }],
      });
    }
  }, [editOpen, editing, editForm]);

  const submitEdit = async () => {
    const values = await editForm.validateFields();
    setSaving(true);
    try {
      const payload = {
        platform: values.platform,
        name: values.name,
        price: Number(values.price),
        url: values.url || '',
        params_json: rowsToParams(values.params),
        sales_volume: Number(values.sales_volume || 0),
        rating: Number(values.rating || 0),
      };
      if (editing) {
        await api.updateCompetitor(editing.id, payload);
        message.success('竞品信息已更新');
      } else {
        await api.createCompetitor(productId, { ...payload, source: 'manual', parse_status: 'confirmed' });
        message.success('竞品已添加');
      }
      setEditOpen(false);
      load();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const openParse = () => {
    setParseStep('input');
    setParseText('');
    setDrafts([]);
    setActiveDraft(0);
    setChannel('');
    setParseOpen(true);
  };

  const fillParseForm = (draft: CompetitorDraft) => {
    parseForm.setFieldsValue({
      platform: draft.platform || 'taobao',
      name: draft.name,
      price: draft.price,
      sales_volume: draft.sales_volume,
      rating: draft.rating,
      url: draft.url,
      params: paramsToRows(draft.params_json || {}),
    });
  };

  const applyDraft = (draft: CompetitorDraft, index: number) => {
    setActiveDraft(index);
    fillParseForm(draft);
  };

  useEffect(() => {
    if (!parseOpen || parseStep !== 'preview' || !drafts.length) return;
    fillParseForm(drafts[activeDraft] ?? drafts[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parseOpen, parseStep, drafts, activeDraft]);

  const runParse = async () => {
    if (!parseText.trim()) {
      message.warning('请先粘贴竞品文本');
      return;
    }
    setParsing(true);
    try {
      const result = await api.parseCompetitor(productId, parseText);
      if (!result.drafts.length) {
        message.warning('未能从文本中识别出竞品信息，请补充名称、价格等关键信息');
        return;
      }
      setDrafts(result.drafts);
      setChannel(result.channel);
      setParseStep('preview');
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setParsing(false);
    }
  };

  const saveDraft = async () => {
    const values = await parseForm.validateFields();
    setSaving(true);
    try {
      await api.createCompetitor(productId, {
        platform: values.platform,
        name: values.name,
        price: Number(values.price),
        url: values.url || '',
        params_json: rowsToParams(values.params),
        sales_volume: Number(values.sales_volume || 0),
        rating: Number(values.rating || 0),
        source: 'ai_parse',
        parse_status: 'confirmed',
      });
      message.success('解析草稿已确认并保存');
      setParseOpen(false);
      load();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const remove = (record: CompetitorInfo) => {
    modal.confirm({
      title: '删除竞品',
      content: `确定删除「${record.name}」吗？删除后不可恢复。`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.deleteCompetitor(record.id);
          message.success('竞品已删除');
          load();
        } catch (error) {
          message.error((error as Error).message);
        }
      },
    });
  };

  const columns: ColumnsType<CompetitorInfo> = [
    {
      title: '竞品',
      key: 'name',
      render: (_, record) => (
        <div className="competitor-name-cell">
          <div className="cell-strong">{record.name}</div>
          <div className="product-sub">
            {record.source === 'ai_parse' ? (
              <Tag bordered={false} color="purple">
                智能解析
              </Tag>
            ) : (
              <Tag bordered={false}>手工录入</Tag>
            )}
            {record.url && (
              <a href={record.url} target="_blank" rel="noreferrer" className="muted">
                <LinkOutlined /> 链接
              </a>
            )}
          </div>
        </div>
      ),
    },
    {
      title: '平台',
      dataIndex: 'platform',
      key: 'platform',
      width: 110,
      render: (value: string) => <PlatformTag platform={value} />,
    },
    {
      title: '售价',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      render: (value: number) => <span className="price-text">¥{value}</span>,
    },
    {
      title: '核心参数',
      key: 'params',
      render: (_, record) => (
        <div className="param-tags">
          {Object.entries(record.params_json || {}).slice(0, 5).map(([key, value]) => (
            <Tag key={key} bordered={false} className="spec-tag">
              {key} · {value}
            </Tag>
          ))}
          {!Object.keys(record.params_json || {}).length && <span className="muted">—</span>}
        </div>
      ),
    },
    {
      title: '月销',
      dataIndex: 'sales_volume',
      key: 'sales_volume',
      width: 90,
      render: (value: number) => (value ? value.toLocaleString() : '—'),
    },
    {
      title: '评分',
      dataIndex: 'rating',
      key: 'rating',
      width: 76,
      render: (value: number) => (value ? value.toFixed(1) : '—'),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Space size={2}>
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => remove(record)} />
        </Space>
      ),
    },
  ];

  const currentDraft = drafts[activeDraft];

  return (
    <Card
      className="surface-card"
      title={
        <div>
          <div className="card-title">竞品对比与智能解析</div>
          <div className="card-subtitle">录入竞品参数，或粘贴商品文本由模型抽取结构化草稿</div>
        </div>
      }
      extra={
        <Space>
          <Button icon={<ThunderboltOutlined />} onClick={openParse}>
            智能解析
          </Button>
          <Button type="primary" ghost icon={<PlusOutlined />} onClick={openCreate}>
            添加竞品
          </Button>
        </Space>
      }
    >
      <Spin spinning={loading}>
        {competitors.length ? (
          <Table rowKey="id" size="middle" columns={columns} dataSource={competitors} pagination={false} />
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="尚未录入竞品，建议至少补充 2 个直接竞品"
          >
            <Space>
              <Button icon={<ThunderboltOutlined />} onClick={openParse}>
                粘贴文本智能解析
              </Button>
              <Button type="primary" ghost onClick={openCreate}>
                手工添加
              </Button>
            </Space>
          </Empty>
        )}
      </Spin>

      <Modal
        open={editOpen}
        title={editing ? '编辑竞品' : '添加竞品'}
        onCancel={() => setEditOpen(false)}
        onOk={submitEdit}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
        width={600}
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical">
          <CompetitorFields />
        </Form>
      </Modal>

      <Modal
        open={parseOpen}
        title="智能解析竞品文本"
        onCancel={() => setParseOpen(false)}
        width={680}
        destroyOnHidden
        footer={
          parseStep === 'input' ? (
            <Space>
              <Button onClick={() => setParseOpen(false)}>取消</Button>
              <Button type="primary" loading={parsing} icon={<ThunderboltOutlined />} onClick={runParse}>
                开始解析
              </Button>
            </Space>
          ) : (
            <Space>
              <Button onClick={() => setParseStep('input')}>重新粘贴</Button>
              <Button onClick={() => setParseOpen(false)}>取消</Button>
              <Button type="primary" loading={saving} onClick={saveDraft}>
                确认保存
              </Button>
            </Space>
          )
        }
      >
        {parseStep === 'input' ? (
          <>
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 14 }}
              message="只处理你粘贴的文本，不会访问外部竞品网站"
              description="建议包含：竞品名称、平台、价格、月销、评分，以及 UPF / 功率 / 面料等参数。"
            />
            <Input.TextArea
              rows={9}
              value={parseText}
              onChange={(event) => setParseText(event.target.value)}
              placeholder={'示例：\n觅橘 轻户外防晒衣 | 抖音\n价格：99 元，月销 8000，评分 4.6\nUPF：40+，面料：涂层型，克重：110g\nhttps://example.com/item/miju'}
            />
          </>
        ) : (
          <>
            <Alert
              type={channel === 'real' ? 'success' : 'info'}
              showIcon
              style={{ marginBottom: 14 }}
              message={`解析完成 · ${channelLabel(channel)}`}
              description="以下为可编辑草稿，请校对后保存。草稿不会直接进入诊断上下文。"
            />
            {drafts.length > 1 && (
              <div className="draft-tabs">
                {drafts.map((draft, index) => (
                  <Tag.CheckableTag
                    key={`${draft.name}-${index}`}
                    checked={index === activeDraft}
                    onChange={() => applyDraft(draft, index)}
                  >
                    {draft.name || `草稿 ${index + 1}`}
                  </Tag.CheckableTag>
                ))}
              </div>
            )}
            {currentDraft && (
              <Form form={parseForm} layout="vertical">
                <CompetitorFields />
              </Form>
            )}
          </>
        )}
      </Modal>
    </Card>
  );
}
