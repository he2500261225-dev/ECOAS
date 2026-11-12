import { useEffect, useMemo, useState } from 'react';
import { App, Button, Card, Empty, Form, Input, InputNumber, Modal, Select, Space, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DeleteOutlined, EditOutlined, PlusOutlined, SwapOutlined } from '@ant-design/icons';
import { api } from '../../api';
import type { PlatformMappingInfo, ProductDetail } from '../../api/types';
import { PLATFORM_OPTIONS, specLabel } from '../../utils/catalog';
import { PlatformTag } from '../StageTag';

interface MappingRow extends PlatformMappingInfo {
  sku_spec: Record<string, string>;
}

interface Props {
  product: ProductDetail;
  onChanged: () => void;
}

export function MappingPanel({ product, onChanged }: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<MappingRow | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const { message, modal } = App.useApp();

  const rows = useMemo<MappingRow[]>(
    () =>
      product.skus.flatMap((sku) =>
        (sku.mappings || []).map((mapping) => ({ ...mapping, sku_spec: sku.spec })),
      ),
    [product.skus],
  );

  useEffect(() => {
    if (!modalOpen) return;
    form.resetFields();
    if (editing) {
      form.setFieldsValue({
        sku_id: editing.sku_id,
        platform: editing.platform,
        platform_spec_name: editing.platform_spec_name,
        platform_price: editing.platform_price,
        platform_sku_code: editing.platform_sku_code,
      });
    } else {
      form.setFieldsValue({
        platform: product.store.platform,
        platform_price: product.skus[0]?.price,
      });
    }
  }, [modalOpen, editing, form, product]);

  const openCreate = () => {
    setEditing(null);
    setModalOpen(true);
  };

  const openEdit = (row: MappingRow) => {
    setEditing(row);
    setModalOpen(true);
  };

  const submit = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (editing) {
        await api.updateMapping(editing.id, {
          platform: values.platform,
          platform_spec_name: values.platform_spec_name,
          platform_price: Number(values.platform_price ?? 0),
          platform_sku_code: values.platform_sku_code || '',
        });
        message.success('平台映射已更新');
      } else {
        await api.createMapping(Number(values.sku_id), {
          platform: values.platform,
          platform_spec_name: values.platform_spec_name,
          platform_price: Number(values.platform_price ?? 0),
          platform_sku_code: values.platform_sku_code || '',
        });
        message.success('平台映射已新增');
      }
      setModalOpen(false);
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const remove = (row: MappingRow) => {
    modal.confirm({
      title: '删除平台映射',
      content: `确定删除「${specLabel(row.sku_spec)} → ${row.platform_sku_code || row.platform_spec_name}」吗？`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.deleteMapping(row.id);
          message.success('平台映射已删除');
          onChanged();
        } catch (error) {
          message.error((error as Error).message);
        }
      },
    });
  };

  const columns: ColumnsType<MappingRow> = [
    {
      title: '本地 SKU',
      key: 'sku',
      width: 200,
      render: (_, record) => <span className="cell-strong">{specLabel(record.sku_spec)}</span>,
    },
    {
      title: '平台',
      dataIndex: 'platform',
      key: 'platform',
      width: 120,
      render: (value: string) => <PlatformTag platform={value} />,
    },
    {
      title: '平台规格名',
      dataIndex: 'platform_spec_name',
      key: 'platform_spec_name',
      render: (value: string) => value || <span className="muted">—</span>,
    },
    {
      title: '平台售价',
      dataIndex: 'platform_price',
      key: 'platform_price',
      width: 110,
      render: (value: number) => <span className="price-text">¥{value}</span>,
    },
    {
      title: '平台 SKU 编码',
      dataIndex: 'platform_sku_code',
      key: 'platform_sku_code',
      width: 180,
      render: (value: string) =>
        value ? <code className="sku-code">{value}</code> : <span className="muted">未填写</span>,
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Space size={2}>
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => remove(record)}
          />
        </Space>
      ),
    },
  ];

  return (
    <Card
      className="surface-card"
      title={
        <div>
          <div className="card-title">平台规格映射</div>
          <div className="card-subtitle">本地 SKU 与各平台后台规格、编码、售价的对应关系</div>
        </div>
      }
      extra={
        <Button type="primary" ghost icon={<PlusOutlined />} onClick={openCreate} disabled={!product.skus.length}>
          新增映射
        </Button>
      }
    >
      {rows.length ? (
        <Table rowKey="id" size="middle" columns={columns} dataSource={rows} pagination={false} />
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="尚未建立平台映射，建议为每个 SKU 补充平台编码"
        >
          <Button icon={<SwapOutlined />} onClick={openCreate} disabled={!product.skus.length}>
            建立第一条映射
          </Button>
        </Empty>
      )}

      <Modal
        open={modalOpen}
        title={editing ? '编辑平台映射' : '新增平台映射'}
        onCancel={() => setModalOpen(false)}
        onOk={submit}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
        width={520}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item name="sku_id" label="本地 SKU" rules={[{ required: true, message: '请选择 SKU' }]}>
            <Select
              disabled={!!editing}
              placeholder="选择 SKU"
              options={product.skus.map((sku) => ({ value: sku.id, label: specLabel(sku.spec) }))}
            />
          </Form.Item>
          <div className="form-two-col">
            <Form.Item name="platform" label="平台" rules={[{ required: true, message: '请选择平台' }]}>
              <Select options={PLATFORM_OPTIONS} />
            </Form.Item>
            <Form.Item name="platform_price" label="平台售价（¥）">
              <InputNumber min={0} precision={2} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <Form.Item name="platform_spec_name" label="平台规格名">
            <Input placeholder="例如：雾霾蓝/M" />
          </Form.Item>
          <Form.Item name="platform_sku_code" label="平台 SKU 编码">
            <Input placeholder="例如：TM20250001" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
