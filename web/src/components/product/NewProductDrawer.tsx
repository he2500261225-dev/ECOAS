import { useEffect, useState } from 'react';
import {
  Alert,
  App,
  AutoComplete,
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
} from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { api } from '../../api';
import type { ProductDetail, StoreInfo } from '../../api/types';
import { SERVICE_CATEGORY_OPTIONS, isServiceCategory } from '../../utils/catalog';

interface Props {
  open: boolean;
  stores: StoreInfo[];
  onClose: () => void;
  onCreated: (product: ProductDetail) => void;
}

export function NewProductDrawer({ open, stores, onClose, onCreated }: Props) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const { message } = App.useApp();
  const category = Form.useWatch('category', form);
  const isService = isServiceCategory(category);

  useEffect(() => {
    if (!open) return;
    form.resetFields();
    form.setFieldsValue({
      store_id: stores[0]?.id,
      skus: [{ spec_text: '', price: 99, stock: 50, warn_threshold: 10 }],
    });
  }, [open, stores, form]);

  const submit = async () => {
    const values = await form.validateFields();
    const store = stores.find((item) => item.id === values.store_id);
    if (!store) {
      message.error('请选择所属店铺');
      return;
    }
    setSaving(true);
    try {
      const product = await api.createProduct({
        store_id: values.store_id,
        name: values.name,
        category: values.category || '',
        description: values.description || '',
        price_min: values.price_min ?? undefined,
        price_max: values.price_max ?? undefined,
        skus: (values.skus || []).map(
          (sku: {
            spec_text: string;
            price: number;
            stock: number;
            warn_threshold: number;
            platform_sku_code?: string;
            platform_spec_name?: string;
            platform_price?: number;
          }) => ({
            spec_text: sku.spec_text,
            price: Number(sku.price || 0),
            stock: isService ? 9999 : Number(sku.stock || 0),
            warn_threshold: isService ? 0 : Number(sku.warn_threshold || 0),
            mappings: sku.platform_sku_code
              ? [
                  {
                    platform: store.platform,
                    platform_spec_name: sku.platform_spec_name || sku.spec_text,
                    platform_price:
                      sku.platform_price === undefined || sku.platform_price === null
                        ? Number(sku.price || 0)
                        : Number(sku.platform_price),
                    platform_sku_code: sku.platform_sku_code,
                  },
                ]
              : [],
          }),
        ),
      });
      message.success(`商品「${product.name}」已创建`);
      onCreated(product);
      onClose();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={760}
      title="新建商品"
      extra={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" loading={saving} onClick={submit}>
            创建商品
          </Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 18 }}
        message={
          isService
            ? '本地服务品类：库存不参与实物管理，创建后可维护服务套餐、平台映射与竞品'
            : '先完成基础建档，创建后可继续维护 SKU、库存流水、平台映射与竞品'
        }
      />
      <Form form={form} layout="vertical">
        <div className="form-two-col">
          <Form.Item name="name" label="商品名称" rules={[{ required: true, message: '请输入商品名称' }]}>
            <Input placeholder="例如：冰丝防晒衣 UPF50+" />
          </Form.Item>
          <Form.Item name="store_id" label="所属店铺" rules={[{ required: true, message: '请选择店铺' }]}>
            <Select
              options={stores.map((store) => ({
                value: store.id,
                label: `${store.name} · ${store.platform}`,
              }))}
            />
          </Form.Item>
        </div>
        <div className="form-two-col">
          <Form.Item name="category" label="所属品类">
            <AutoComplete
              options={SERVICE_CATEGORY_OPTIONS}
              placeholder="例如：防晒服饰 / 除甲醛服务"
              filterOption={(input, option) =>
                String(option?.value || '').includes(input.trim())
              }
            />
          </Form.Item>
          <div className="form-two-col nested">
            <Form.Item name="price_min" label="价格带下限（¥）">
              <InputNumber min={0} precision={2} style={{ width: '100%' }} placeholder="留空自动计算" />
            </Form.Item>
            <Form.Item name="price_max" label="价格带上限（¥）">
              <InputNumber min={0} precision={2} style={{ width: '100%' }} placeholder="留空自动计算" />
            </Form.Item>
          </div>
        </div>
        <Form.Item name="description" label="商品描述">
          <Input.TextArea rows={3} placeholder="核心卖点、面料 / 参数、适用场景" maxLength={500} showCount />
        </Form.Item>

        <div className="form-section-title">
          <span>{isService ? '首批服务套餐' : '首批 SKU'}</span>
          <span className="muted">
            {isService
              ? '至少添加 1 个套餐；库存自动设为不限制，平台编码选填'
              : '至少添加 1 个；平台编码选填，填写后自动建立映射'}
          </span>
        </div>
        <Form.List name="skus">
          {(fields, { add, remove }) => (
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              {fields.map((field, index) => (
                <div className="new-sku-card" key={field.key}>
                  <div className="new-sku-head">
                    <span className="cell-strong">{isService ? `套餐 ${index + 1}` : `SKU ${index + 1}`}</span>
                    {fields.length > 1 && (
                      <Button
                        type="text"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={() => remove(field.name)}
                      />
                    )}
                  </div>
                  <Form.Item
                    name={[field.name, 'spec_text']}
                    label={isService ? '套餐内容' : '规格'}
                    rules={[{ required: true, message: isService ? '请输入套餐内容' : '请输入规格' }]}
                  >
                    <Input
                      placeholder={
                        isService
                          ? '套餐:全屋治理, 计价单位:元/㎡, 服务范围:100㎡以内'
                          : '颜色:雾霾蓝, 尺码:M'
                      }
                    />
                  </Form.Item>
                  <div className={isService ? 'form-two-col' : 'form-three-col'}>
                    <Form.Item
                      name={[field.name, 'price']}
                      label={isService ? '套餐价格（¥）' : '售价（¥）'}
                      rules={[{ required: true, message: '请输入售价' }]}
                    >
                      <InputNumber min={0} precision={2} style={{ width: '100%' }} />
                    </Form.Item>
                    {!isService && (
                      <>
                        <Form.Item
                          name={[field.name, 'stock']}
                          label="初始库存"
                          rules={[{ required: true, message: '请输入库存' }]}
                        >
                          <InputNumber min={0} precision={0} style={{ width: '100%' }} />
                        </Form.Item>
                        <Form.Item
                          name={[field.name, 'warn_threshold']}
                          label="安全库存"
                          rules={[{ required: true, message: '请输入安全库存' }]}
                        >
                          <InputNumber min={0} precision={0} style={{ width: '100%' }} />
                        </Form.Item>
                      </>
                    )}
                  </div>
                  <div className="form-three-col">
                    <Form.Item name={[field.name, 'platform_spec_name']} label="平台规格名（选填）">
                      <Input placeholder="雾霾蓝/M" />
                    </Form.Item>
                    <Form.Item name={[field.name, 'platform_price']} label="平台售价（选填）">
                      <InputNumber min={0} precision={2} style={{ width: '100%' }} />
                    </Form.Item>
                    <Form.Item name={[field.name, 'platform_sku_code']} label="平台 SKU 编码（选填）">
                      <Input placeholder="TM20250001" />
                    </Form.Item>
                  </div>
                </div>
              ))}
              <Button
                type="dashed"
                block
                icon={<PlusOutlined />}
                onClick={() =>
                  add({
                    spec_text: '',
                    price: 99,
                    stock: isService ? 9999 : 50,
                    warn_threshold: isService ? 0 : 10,
                  })
                }
              >
                {isService ? '添加套餐' : '添加 SKU'}
              </Button>
            </Space>
          )}
        </Form.List>
      </Form>
      <div className="drawer-foot-hint">
        {stores.length ? (
          <span className="muted">
            {isService
              ? '创建后可在工作台继续维护服务套餐、平台映射与竞品'
              : '创建后可在工作台继续维护库存流水、平台映射与竞品'}
          </span>
        ) : (
          <span className="muted">暂无店铺，请先由主管在「管理店铺」中创建店铺</span>
        )}
      </div>
    </Drawer>
  );
}
