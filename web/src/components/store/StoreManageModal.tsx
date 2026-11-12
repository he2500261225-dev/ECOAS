import { useEffect, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ArrowLeftOutlined, EditOutlined, PlusOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { api } from '../../api';
import type { StoreInfo } from '../../api/types';
import { AUTH_STATUS_OPTIONS, PLATFORM_OPTIONS } from '../../utils/catalog';
import { PlatformTag } from '../StageTag';

interface Props {
  open: boolean;
  onClose: () => void;
  onChanged: () => void;
}

function authTag(status: string) {
  if (status === 'authorized') return <Tag bordered={false} color="green">授权正常</Tag>;
  if (status === 'pending') return <Tag bordered={false} color="blue">待授权</Tag>;
  if (status === 'revoked') return <Tag bordered={false} color="default">已撤销</Tag>;
  return <Tag bordered={false} color="orange">授权过期</Tag>;
}

export function StoreManageModal({ open, onClose, onChanged }: Props) {
  const [stores, setStores] = useState<StoreInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<StoreInfo | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const { message } = App.useApp();

  const load = async () => {
    setLoading(true);
    try {
      setStores(await api.stores());
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      setFormOpen(false);
      load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const openEdit = (store: StoreInfo) => {
    setEditing(store);
    setFormOpen(true);
  };

  useEffect(() => {
    if (!formOpen) return;
    form.resetFields();
    if (editing) {
      form.setFieldsValue({
        name: editing.name,
        platform: editing.platform,
        auth_status: editing.auth_status,
        auth_ref: editing.auth_ref || '',
      });
    } else {
      form.setFieldsValue({ platform: 'taobao', auth_status: 'authorized', auth_ref: '' });
    }
  }, [formOpen, editing, form]);

  const submit = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (editing) {
        await api.updateStore(editing.id, values);
        message.success('店铺信息已更新');
      } else {
        await api.createStore(values);
        message.success('店铺已创建');
      }
      setFormOpen(false);
      await load();
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const columns: ColumnsType<StoreInfo> = [
    {
      title: '店铺',
      key: 'name',
      render: (_, record) => (
        <div>
          <div className="cell-strong">{record.name}</div>
          <div className="product-sub">
            <PlatformTag platform={record.platform} />
            <span className="muted">{record.product_count} 款商品</span>
          </div>
        </div>
      ),
    },
    {
      title: '授权状态',
      dataIndex: 'auth_status',
      key: 'auth_status',
      width: 110,
      render: (value: string) => authTag(value),
    },
    {
      title: '接入标识（脱敏）',
      dataIndex: 'auth_ref',
      key: 'auth_ref',
      render: (value: string) =>
        value ? <code className="sku-code">{value}</code> : <span className="muted">未接入</span>,
    },
    {
      title: '库存预警',
      dataIndex: 'stock_warning_count',
      key: 'stock_warning_count',
      width: 90,
      render: (value: number) =>
        value > 0 ? <span className="stock-critical">{value}</span> : <span className="muted">0</span>,
    },
    {
      title: '',
      key: 'action',
      width: 72,
      render: (_, record) => (
        <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
          编辑
        </Button>
      ),
    },
  ];

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={760}
      title={
        <Space>
          {formOpen && (
            <Button
              type="text"
              size="small"
              icon={<ArrowLeftOutlined />}
              onClick={() => setFormOpen(false)}
            />
          )}
          {formOpen ? (editing ? '编辑店铺' : '新建店铺') : '店铺管理'}
        </Space>
      }
      destroyOnHidden
    >
      <Alert
        type="warning"
        showIcon
        icon={<SafetyCertificateOutlined />}
        style={{ marginBottom: 16 }}
        message="合规边界"
        description="平台账号只保存接入标识与脱敏授权状态，严禁录入明文密码或 Cookie。未脱敏的标识会自动打码后存储。"
      />

      {formOpen ? (
        <Form form={form} layout="vertical">
          <div className="form-two-col">
            <Form.Item
              name="name"
              label="店铺名称"
              rules={[{ required: true, message: '请输入店铺名称' }]}
            >
              <Input placeholder="例如：天猫旗舰店" />
            </Form.Item>
            <Form.Item
              name="platform"
              label="平台"
              rules={[{ required: true, message: '请选择平台' }]}
            >
              <Select options={PLATFORM_OPTIONS} />
            </Form.Item>
          </div>
          <div className="form-two-col">
            <Form.Item
              name="auth_status"
              label="授权状态"
              rules={[{ required: true, message: '请选择授权状态' }]}
            >
              <Select options={AUTH_STATUS_OPTIONS} />
            </Form.Item>
            <Form.Item
              name="auth_ref"
              label="接入标识"
              extra="仅填写脱敏标识，例如 oauth_****9f2a"
            >
              <Input placeholder="oauth_****9f2a" />
            </Form.Item>
          </div>
          <div className="modal-foot-right">
            <Space>
              <Button onClick={() => setFormOpen(false)}>取消</Button>
              <Button type="primary" loading={saving} onClick={submit}>
                保存
              </Button>
            </Space>
          </div>
        </Form>
      ) : (
        <>
          <div className="modal-toolbar">
            <span className="muted">共 {stores.length} 家店铺</span>
            <Button type="primary" ghost icon={<PlusOutlined />} onClick={openCreate}>
              新建店铺
            </Button>
          </div>
          <Spin spinning={loading}>
            <Table rowKey="id" size="middle" columns={columns} dataSource={stores} pagination={false} />
          </Spin>
        </>
      )}
    </Modal>
  );
}
