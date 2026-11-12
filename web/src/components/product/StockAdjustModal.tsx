import { useEffect, useState } from 'react';
import { Alert, App, Form, InputNumber, Modal, Select } from 'antd';
import { api } from '../../api';
import type { SkuInfo } from '../../api/types';
import { STOCK_REASONS, specLabel } from '../../utils/catalog';

interface Props {
  open: boolean;
  sku: SkuInfo | null;
  onClose: () => void;
  onSaved: () => void;
}

export function StockAdjustModal({ open, sku, onClose, onSaved }: Props) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const { message } = App.useApp();

  useEffect(() => {
    if (!open) return;
    form.setFieldsValue({ change: 10, reason: 'restock' });
  }, [open, form]);

  const submit = async () => {
    if (!sku) return;
    const values = await form.validateFields();
    setSaving(true);
    try {
      const result = await api.adjustStock(sku.id, Number(values.change), values.reason);
      message.success(`库存已更新为 ${result.sku.stock}`);
      onSaved();
      onClose();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      title="调整库存"
      onCancel={onClose}
      onOk={submit}
      okText="确认调整"
      cancelText="取消"
      confirmLoading={saving}
      width={480}
      destroyOnHidden
    >
      {sku && (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message={`${specLabel(sku.spec)} · 当前库存 ${sku.stock} 件`}
            description="每次调整都会写入库存流水，便于追溯。"
          />
          <Form form={form} layout="vertical">
            <Form.Item
              name="change"
              label="调整数量"
              rules={[{ required: true, message: '请输入调整数量' }]}
              extra="正数表示入库，负数表示出库"
            >
              <InputNumber precision={0} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              name="reason"
              label="调整原因"
              rules={[{ required: true, message: '请选择调整原因' }]}
            >
              <Select options={STOCK_REASONS} />
            </Form.Item>
          </Form>
        </>
      )}
    </Modal>
  );
}
