import { useEffect, useState } from 'react';
import { App, AutoComplete, Form, Input, InputNumber, Modal, Select } from 'antd';
import { api } from '../../api';
import type { ProductDetail, StoreInfo } from '../../api/types';
import { PlatformTag } from '../StageTag';
import { SERVICE_CATEGORY_OPTIONS, specLabel } from '../../utils/catalog';

interface Props {
  open: boolean;
  product: ProductDetail;
  stores: StoreInfo[];
  onClose: () => void;
  onSaved: () => void;
}

export function ProductFormModal({ open, product, stores, onClose, onSaved }: Props) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const { message } = App.useApp();

  useEffect(() => {
    if (!open) return;
    form.setFieldsValue({
      store_id: product.store.id,
      name: product.name,
      category: product.category,
      price_min: product.price_min,
      price_max: product.price_max,
      main_sku_id: product.main_sku_id ?? undefined,
      description: product.description,
    });
  }, [open, product, form]);

  const submit = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.updateProduct(product.id, values);
      message.success('商品档案已更新');
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
      title="编辑商品档案"
      onCancel={onClose}
      onOk={submit}
      okText="保存"
      cancelText="取消"
      confirmLoading={saving}
      width={620}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" className="product-form">
        <Form.Item
          name="name"
          label="商品名称"
          rules={[{ required: true, message: '请输入商品名称' }]}
        >
          <Input placeholder="例如：冰丝防晒衣 UPF50+" maxLength={120} />
        </Form.Item>
        <div className="form-two-col">
          <Form.Item name="store_id" label="所属店铺" rules={[{ required: true, message: '请选择店铺' }]}>
            <Select
              options={stores.map((store) => ({
                value: store.id,
                label: (
                  <span className="select-store-option">
                    {store.name} <PlatformTag platform={store.platform} />
                  </span>
                ),
              }))}
            />
          </Form.Item>
          <Form.Item name="category" label="所属品类">
            <AutoComplete
              options={SERVICE_CATEGORY_OPTIONS}
              placeholder="例如：防晒服饰 / 数码配件"
              filterOption={(input, option) =>
                String(option?.value || '').includes(input.trim())
              }
            />
          </Form.Item>
        </div>
        <div className="form-two-col">
          <Form.Item name="price_min" label="价格带下限（¥）" rules={[{ required: true, message: '请输入下限' }]}>
            <InputNumber min={0} precision={2} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="price_max" label="价格带上限（¥）" rules={[{ required: true, message: '请输入上限' }]}>
            <InputNumber min={0} precision={2} style={{ width: '100%' }} />
          </Form.Item>
        </div>
        <Form.Item name="main_sku_id" label={product.is_service ? '主推套餐' : '主推 SKU'}>
          <Select
            allowClear
            placeholder={product.is_service ? '选择主推套餐' : '选择主推规格'}
            options={product.skus.map((sku) => ({
              value: sku.id,
              label: specLabel(sku.spec),
            }))}
          />
        </Form.Item>
        <Form.Item name="description" label="商品描述">
          <Input.TextArea rows={4} placeholder="描述核心卖点、面料 / 参数与适用场景" maxLength={500} showCount />
        </Form.Item>
      </Form>
    </Modal>
  );
}
