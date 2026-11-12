import { useEffect, useState } from 'react';
import { App, Form, Input, InputNumber, Modal } from 'antd';
import { api } from '../../api';
import type { SkuInfo } from '../../api/types';
import { specToText, textToSpec } from '../../utils/catalog';

interface Props {
  open: boolean;
  productId: number;
  sku: SkuInfo | null;
  isService?: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export function SkuFormModal({ open, productId, sku, isService = false, onClose, onSaved }: Props) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const { message } = App.useApp();

  useEffect(() => {
    if (!open) return;
    form.resetFields();
    form.setFieldsValue(
      sku
        ? {
            spec_text: specToText(sku.spec),
            price: sku.price,
            warn_threshold: sku.warn_threshold,
          }
        : {
            spec_text: '',
            price: 99,
            stock: isService ? 9999 : 50,
            warn_threshold: isService ? 0 : 10,
          },
    );
  }, [open, sku, isService, form]);

  const submit = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (sku) {
        await api.updateSku(sku.id, {
          spec_json: textToSpec(values.spec_text),
          price: Number(values.price),
          ...(isService ? {} : { warn_threshold: Number(values.warn_threshold) }),
        });
        message.success(isService ? '服务套餐已更新' : 'SKU 已更新');
      } else {
        await api.createSku(productId, {
          spec_json: textToSpec(values.spec_text),
          price: Number(values.price),
          stock: isService ? 9999 : Number(values.stock),
          warn_threshold: isService ? 0 : Number(values.warn_threshold),
        });
        message.success(isService ? '服务套餐已新增' : 'SKU 已新增');
      }
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
      title={sku ? (isService ? '编辑服务套餐' : '编辑 SKU') : isService ? '新增服务套餐' : '新增 SKU'}
      onCancel={onClose}
      onOk={submit}
      okText="保存"
      cancelText="取消"
      confirmLoading={saving}
      width={520}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="spec_text"
          label={isService ? '套餐内容' : '规格'}
          rules={[{ required: true, message: isService ? '请输入套餐内容' : '请输入规格' }]}
          extra={
            isService
              ? '多个字段用逗号分隔，建议填写：套餐、计价单位、服务范围、时效'
              : '多个规格用逗号分隔，例如：颜色:雾霾蓝, 尺码:M'
          }
        >
          <Input
            placeholder={isService ? '套餐:全屋治理, 计价单位:元/㎡, 服务范围:100㎡以内' : '颜色:雾霾蓝, 尺码:M'}
          />
        </Form.Item>
        <div className="form-two-col">
          <Form.Item name="price" label="售价（¥）" rules={[{ required: true, message: '请输入售价' }]}>
            <InputNumber min={0} precision={2} style={{ width: '100%' }} />
          </Form.Item>
          {isService ? (
            <Form.Item label="库存模式" extra="服务套餐不占用实物库存，无需调整库存">
              <Input value="不限制（9999）" disabled />
            </Form.Item>
          ) : sku ? (
            <Form.Item label="当前库存" extra="库存变更请使用「调整库存」以生成流水">
              <InputNumber value={sku.stock} disabled style={{ width: '100%' }} />
            </Form.Item>
          ) : (
            <Form.Item name="stock" label="初始库存" rules={[{ required: true, message: '请输入库存' }]}>
              <InputNumber min={0} precision={0} style={{ width: '100%' }} />
            </Form.Item>
          )}
        </div>
        {!isService && (
          <Form.Item
            name="warn_threshold"
            label="安全库存阈值"
            rules={[{ required: true, message: '请输入安全库存' }]}
          >
            <InputNumber min={0} precision={0} style={{ width: '100%' }} />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}
