import { useEffect, useState } from 'react';
import {
  App,
  Button,
  Card,
  Descriptions,
  Empty,
  Space,
  Spin,
  Steps,
  Table,
  Tabs,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ArrowLeftOutlined,
  EditOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  InboxOutlined,
  PictureOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import type {
  DiagnosisInfo,
  ProductDetail as ProductDetailType,
  SkuInfo,
  Stage,
  StoreInfo,
  TrendPoint,
} from '../api/types';
import { PlatformTag, StageTag, platformLabel } from '../components/StageTag';
import { TrendChart } from '../components/TrendChart';
import { UnderConstruction } from '../components/UnderConstruction';
import { ProductFormModal } from '../components/product/ProductFormModal';
import { SkuFormModal } from '../components/product/SkuFormModal';
import { StockAdjustModal } from '../components/product/StockAdjustModal';
import { StockFlowDrawer } from '../components/product/StockFlowDrawer';
import { MappingPanel } from '../components/product/MappingPanel';
import { CompetitorPanel } from '../components/product/CompetitorPanel';
import { DiagnosisBoard } from '../components/product/DiagnosisBoard';
import { CreativeWorkspace } from '../components/creative/CreativeWorkspace';
import { formatPriceBand, specLabel } from '../utils/catalog';

const STAGE_INDEX: Record<Stage, number> = {
  draft: 0,
  diagnosed: 1,
  creative_ready: 2,
  asset_ready: 3,
  launching: 4,
  reviewing: 5,
  reviewed: 6,
};

const STEPS = ['商品建档', '智能诊断', '创意方案', '素材制作', '投放实验', '数据回填', '闭环复盘'];

export function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { message, modal } = App.useApp();
  const [product, setProduct] = useState<ProductDetailType | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [diagnoses, setDiagnoses] = useState<DiagnosisInfo[]>([]);
  const [stores, setStores] = useState<StoreInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [diagLoading, setDiagLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('profile');

  const [productModalOpen, setProductModalOpen] = useState(false);
  const [skuFormOpen, setSkuFormOpen] = useState(false);
  const [editingSku, setEditingSku] = useState<SkuInfo | null>(null);
  const [stockSku, setStockSku] = useState<SkuInfo | null>(null);
  const [flowSku, setFlowSku] = useState<SkuInfo | null>(null);

  const productId = Number(id);

  const loadProduct = async () => {
    const [p, t] = await Promise.all([api.product(productId), api.productTrend(productId, 30)]);
    setProduct(p);
    setTrend(t);
  };

  const loadDiagnoses = async () => {
    setDiagLoading(true);
    try {
      const [items, p] = await Promise.all([api.diagnoses(productId), api.product(productId)]);
      setDiagnoses(items);
      setProduct(p);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setDiagLoading(false);
    }
  };

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      api.product(productId),
      api.productTrend(productId, 30),
      api.diagnoses(productId),
      api.stores(),
    ])
      .then(([p, t, d, s]) => {
        setProduct(p);
        setTrend(t);
        setDiagnoses(d);
        setStores(s);
      })
      .catch((error) => message.error((error as Error).message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const refreshProduct = async () => {
    try {
      await loadProduct();
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const archiveProduct = () => {
    if (!product) return;
    modal.confirm({
      title: '归档商品',
      content: `归档后「${product.name}」将不再出现在运营大盘与默认列表中，历史数据仍保留。`,
      okText: '归档',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.archiveProduct(product.id);
          message.success('商品已归档');
          navigate('/dashboard');
        } catch (error) {
          message.error((error as Error).message);
        }
      },
    });
  };

  const removeSku = (sku: SkuInfo) => {
    modal.confirm({
      title: '删除 SKU',
      content: `确定删除「${specLabel(sku.spec)}」吗？关联的平台映射与库存流水将一并删除。`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.deleteSku(sku.id);
          message.success('SKU 已删除');
          refreshProduct();
        } catch (error) {
          message.error((error as Error).message);
        }
      },
    });
  };

  const isService = Boolean(product?.is_service);
  const servicePrice = (value: number, record: SkuInfo) => {
    const unit = record.spec?.['计价单位'] || product?.price_unit || '';
    return `¥${value}${unit ? unit.replace(/^元/, '') : ''}`;
  };

  const skuColumns: ColumnsType<SkuInfo> = [
    {
      title: isService ? '套餐' : '规格',
      key: 'spec',
      render: (_, record) => (
        <div className="sku-spec">
          {Object.entries(record.spec).map(([key, value]) => (
            <Tag key={key} bordered={false} className="spec-tag">
              {key} · {value}
            </Tag>
          ))}
        </div>
      ),
    },
    {
      title: '售价',
      dataIndex: 'price',
      key: 'price',
      width: isService ? 120 : 100,
      render: (value: number, record) => (
        <span className="price-text">
          {isService ? servicePrice(value, record) : `¥${value}`}
        </span>
      ),
    },
    ...(isService
      ? []
      : [
          {
            title: '库存',
            dataIndex: 'stock',
            key: 'stock',
            width: 110,
            render: (value: number, record: SkuInfo) => (
              <span className={record.warning ? 'stock-critical' : ''}>
                {value}
                {record.warning && <span className="inline-tag">预警</span>}
              </span>
            ),
          },
          {
            title: '安全库存',
            dataIndex: 'warn_threshold',
            key: 'warn_threshold',
            width: 100,
            render: (value: number) => <span className="muted">{value}</span>,
          },
        ]),
    {
      title: '平台映射',
      key: 'mappings',
      width: 96,
      render: (_, record) => (
        <span className="muted">
          {record.mappings?.length ? `${record.mappings.length} 条` : '未建立'}
        </span>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: isService ? 150 : 300,
      render: (_, record) => (
        <Space size={2} wrap>
          {!isService && (
            <>
              <Button type="link" size="small" onClick={() => setStockSku(record)}>
                调整库存
              </Button>
              <Button type="link" size="small" onClick={() => setFlowSku(record)}>
                流水
              </Button>
            </>
          )}
          <Button
            type="link"
            size="small"
            onClick={() => {
              setEditingSku(record);
              setSkuFormOpen(true);
            }}
          >
            编辑
          </Button>
          <Button type="link" size="small" danger onClick={() => removeSku(record)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="page-loading">
        <Spin size="large" />
      </div>
    );
  }

  if (!product) {
    return <Empty description="商品不存在" />;
  }

  const current = STAGE_INDEX[product.stage] ?? 0;
  const mainSku = product.skus.find((sku) => sku.id === product.main_sku_id);

  const profileTab = (
    <div className="profile-tab">
      <div className="detail-grid">
        <Card
          className="surface-card"
          title={<div className="card-title">{isService ? '服务套餐与价格' : 'SKU 矩阵与库存'}</div>}
          extra={
            <Space>
              <span className="muted">
                共 {product.skus.length} {isService ? '个套餐' : '个 SKU'}
              </span>
              <Button
                type="primary"
                ghost
                size="small"
                icon={<PlusOutlined />}
                onClick={() => {
                  setEditingSku(null);
                  setSkuFormOpen(true);
                }}
              >
                {isService ? '新增套餐' : '新增 SKU'}
              </Button>
            </Space>
          }
        >
          <Table
            rowKey="id"
            columns={skuColumns}
            dataSource={product.skus}
            pagination={false}
            size="middle"
            scroll={{ x: 800 }}
          />
        </Card>

        <Card
          className="surface-card"
          title={<div className="card-title">商品概览</div>}
          extra={
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => setProductModalOpen(true)}>
              编辑档案
            </Button>
          }
        >
          <Descriptions column={1} size="small" styles={{ label: { width: 88 } }}>
            <Descriptions.Item label="所属店铺">
              {product.store.name} · {platformLabel(product.store.platform)}
            </Descriptions.Item>
            <Descriptions.Item label="所属品类">{product.category || '未设置'}</Descriptions.Item>
            <Descriptions.Item label={isService ? '主推套餐' : '主推 SKU'}>
              {mainSku ? specLabel(mainSku.spec) : '未设置'}
            </Descriptions.Item>
            {isService && (
              <Descriptions.Item label="价格单位">{product.price_unit || '未设置'}</Descriptions.Item>
            )}
            <Descriptions.Item label="创建时间">
              {dayjs(product.created_at).format('YYYY-MM-DD HH:mm')}
            </Descriptions.Item>
            <Descriptions.Item label="最近更新">
              {dayjs(product.updated_at).format('YYYY-MM-DD HH:mm')}
            </Descriptions.Item>
            <Descriptions.Item label="商品描述">
              <span className="desc-text">{product.description || '暂无描述'}</span>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      </div>

      <MappingPanel product={product} onChanged={refreshProduct} />

      <CompetitorPanel productId={product.id} />

      <DiagnosisBoard
        productId={product.id}
        diagnoses={diagnoses}
        loading={diagLoading}
        onChanged={loadDiagnoses}
      />

      <Card
        className="surface-card"
        title={<div className="card-title">经营指标走势（近 30 天）</div>}
        extra={<span className="muted">数据来源：经营数据回填 / 导入</span>}
      >
        {trend.length ? (
          <TrendChart
            data={trend.map((point) => ({ date: point.date, value: point.gmv }))}
            height={240}
            name="GMV"
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无经营数据，投放周期结束后可在工作台回填" />
        )}
      </Card>
    </div>
  );

  const tabItems = [
    {
      key: 'profile',
      label: (
        <span>
          <FileTextOutlined /> 档案与诊断
        </span>
      ),
      children: profileTab,
    },
    {
      key: 'creative',
      label: (
        <span>
          <PictureOutlined /> 创意与素材
        </span>
      ),
      children: (
        <CreativeWorkspace
          productId={product.id}
          isService={isService}
          hasDiagnosis={diagnoses.some((item) => item.status === 'current')}
          onChanged={refreshProduct}
          onGoDiagnosis={() => setActiveTab('profile')}
        />
      ),
    },
    {
      key: 'review',
      label: (
        <span>
          <ExperimentOutlined /> 投放与复盘
        </span>
      ),
      children: (
        <UnderConstruction
          title="投放实验与经营复盘"
          description="投放建议审批、经营数据回填、目标对比与复盘报告"
          milestone="M4"
          items={[
            '生成人群包、出价、预算、周期与 A/B 分组建议',
            '提交 / 审批 / 驳回，高风险仅主管可审批',
            '按天回填经营数据，自动派生 CTR / CVR / ROI',
            '目标 vs 实际复盘报告与行动项转入下一轮诊断',
          ]}
        />
      ),
    },
  ];

  return (
    <div className="detail-page">
      <div className="page-head detail-head">
        <div className="detail-title-wrap">
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/dashboard')}>
            返回大盘
          </Button>
          <h1 className="page-title">{product.name}</h1>
          <div className="detail-tags">
            <StageTag stage={product.stage} label={product.stage_label} />
            <PlatformTag platform={product.store.platform} />
            {isService && <Tag color="cyan">服务</Tag>}
            <span className="muted">{product.store.name}</span>
            {product.archived && <Tag color="default">已归档</Tag>}
          </div>
        </div>
        <div className="detail-head-right">
          <div className="detail-price">
            <span className="muted">{isService ? '服务价格带' : '在售价格带'}</span>
            <strong>
              {formatPriceBand(product.price_min, product.price_max, product.price_unit)}
            </strong>
          </div>
          <Space>
            <Button icon={<EditOutlined />} onClick={() => setProductModalOpen(true)}>
              编辑商品
            </Button>
            <Button danger icon={<InboxOutlined />} onClick={archiveProduct}>
              归档
            </Button>
          </Space>
        </div>
      </div>

      <Card className="surface-card steps-card">
        <Steps
          current={current}
          status={product.stage === 'reviewed' ? 'finish' : 'process'}
          items={STEPS.map((title) => ({ title }))}
          size="small"
        />
      </Card>

      <Tabs
        className="workspace-tabs"
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        destroyOnHidden
      />

      <ProductFormModal
        open={productModalOpen}
        product={product}
        stores={stores}
        onClose={() => setProductModalOpen(false)}
        onSaved={refreshProduct}
      />
      <SkuFormModal
        open={skuFormOpen}
        productId={product.id}
        sku={editingSku}
        isService={isService}
        onClose={() => setSkuFormOpen(false)}
        onSaved={refreshProduct}
      />
      <StockAdjustModal
        open={!!stockSku}
        sku={stockSku}
        onClose={() => setStockSku(null)}
        onSaved={refreshProduct}
      />
      <StockFlowDrawer open={!!flowSku} sku={flowSku} onClose={() => setFlowSku(null)} />
    </div>
  );
}
