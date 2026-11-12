import { useEffect, useState } from 'react';
import { App, Button, Card, Empty, Spin, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ArrowRightOutlined,
  CloudUploadOutlined,
  PlusOutlined,
  ReloadOutlined,
  RiseOutlined,
  SettingOutlined,
  ShopOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import type {
  DashboardSummary,
  ProductSummary,
  StockWarning,
  StoreInfo,
} from '../api/types';
import { PlatformTag, StageTag } from '../components/StageTag';
import { TrendChart } from '../components/TrendChart';
import { NewProductDrawer } from '../components/product/NewProductDrawer';
import { StoreManageModal } from '../components/store/StoreManageModal';
import { useAuth } from '../auth/AuthContext';
import { formatPriceBand } from '../utils/catalog';

function KpiCard({
  label,
  value,
  hint,
  icon,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  icon: React.ReactNode;
  tone: string;
}) {
  return (
    <Card className="kpi-card" variant="borderless">
      <div className="kpi-inner">
        <div className="kpi-icon" style={{ background: tone }}>
          {icon}
        </div>
        <div className="kpi-body">
          <div className="kpi-label">{label}</div>
          <div className="kpi-value">{value}</div>
          <div className="kpi-hint">{hint}</div>
        </div>
      </div>
    </Card>
  );
}

function StoreCard({ store }: { store: StoreInfo }) {
  const authorized = store.auth_status === 'authorized';
  return (
    <div className="store-row">
      <div className="store-icon">
        <ShopOutlined />
      </div>
      <div className="store-main">
        <div className="store-name">
          {store.name}
          <PlatformTag platform={store.platform} />
        </div>
        <div className="store-meta">
          <span className={`auth-dot ${authorized ? 'ok' : 'warn'}`} />
          {authorized ? '授权正常' : '授权已过期'}
          <span className="store-divider">·</span>
          {store.product_count} 款{store.platform === 'local' ? '服务' : '商品'}
        </div>
      </div>
      <div className="store-warning">
        <div className={store.stock_warning_count > 0 ? 'warning-num' : 'warning-num zero'}>
          {store.stock_warning_count}
        </div>
        <div className="warning-label">库存预警</div>
      </div>
    </div>
  );
}

export function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [newProductOpen, setNewProductOpen] = useState(false);
  const [storeModalOpen, setStoreModalOpen] = useState(false);
  const { message } = App.useApp();
  const { user } = useAuth();
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const [summaryData, productData] = await Promise.all([api.dashboard(), api.products()]);
      setSummary(summaryData);
      setProducts(productData);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const kpis = summary?.kpis;

  const productColumns: ColumnsType<ProductSummary> = [
    {
      title: '商品',
      dataIndex: 'name',
      key: 'name',
      render: (_, record) => (
        <div className="product-cell">
          <div className="product-name">
            {record.name}
            {record.is_service && (
              <Tag bordered={false} color="cyan" className="service-tag">
                服务
              </Tag>
            )}
          </div>
          <div className="product-sub">
            {record.store.name} · {record.category}
            {record.main_sku_spec && (
              <span className="product-spec">
                {Object.values(record.main_sku_spec).join(' / ')}
              </span>
            )}
          </div>
        </div>
      ),
    },
    {
      title: '价格带',
      key: 'price',
      width: 116,
      render: (_, record) =>
        formatPriceBand(record.price_min, record.price_max, record.price_unit),
    },
    {
      title: 'SKU',
      dataIndex: 'sku_count',
      key: 'sku_count',
      width: 76,
      render: (_, record) => (
        <span className={record.warning_sku_count > 0 ? 'sku-warn' : ''}>
          {record.sku_count}
          {record.warning_sku_count > 0 && <span className="sku-warn-badge">{record.warning_sku_count} 预警</span>}
        </span>
      ),
    },
    {
      title: '闭环阶段',
      key: 'stage',
      width: 108,
      render: (_, record) => <StageTag stage={record.stage} label={record.stage_label} />,
    },
    {
      title: '素材',
      dataIndex: 'asset_count',
      key: 'asset_count',
      width: 64,
      render: (value: number) => <span className="muted">{value} 个</span>,
    },
    {
      title: '',
      key: 'action',
      width: 44,
      render: () => <ArrowRightOutlined className="row-arrow" />,
    },
  ];

  const warningColumns: ColumnsType<StockWarning> = [
    {
      title: '商品 / 规格',
      key: 'product',
      render: (_, record) => (
        <div className="warning-cell">
          <div className="product-name">{record.product_name}</div>
          <div className="product-sub">
            {Object.entries(record.spec).map(([k, v]) => `${k} ${v}`).join(' · ')}
          </div>
        </div>
      ),
    },
    {
      title: '库存',
      key: 'stock',
      width: 110,
      render: (_, record) => (
        <span className="stock-critical">
          {record.stock}
          <span className="stock-threshold"> / {record.threshold}</span>
        </span>
      ),
    },
    {
      title: '阶段',
      key: 'stage',
      width: 96,
      render: (_, record) => <StageTag stage={record.stage} label={record.stage_label} />,
    },
  ];

  return (
    <Spin spinning={loading}>
      <div className="page-head">
        <div>
          <h1 className="page-title">运营大盘</h1>
          <p className="page-subtitle">
            {dayjs().format('YYYY 年 M 月 D 日 dddd')} · 全店铺经营概览与单品闭环进度
          </p>
        </div>
        <div className="page-actions">
          <Button icon={<ReloadOutlined />} onClick={load}>
            刷新数据
          </Button>
          <Button icon={<CloudUploadOutlined />} onClick={() => navigate('/import')}>
            批量导入
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setNewProductOpen(true)}>
            新建商品
          </Button>
        </div>
      </div>

      <div className="kpi-grid">
        <KpiCard
          label="商品/服务总数"
          value={`${kpis?.product_total ?? '—'}`}
          hint={`覆盖 ${summary?.stores.length ?? 0} 家店铺`}
          icon={<ShopOutlined />}
          tone="linear-gradient(135deg, #ecfdf5, #ccfbf1)"
        />
        <KpiCard
          label="在售动销率"
          value={`${kpis?.on_sale_rate ?? '—'}%`}
          hint={`近 30 天有经营数据 ${kpis?.active_products ?? 0} 款`}
          icon={<RiseOutlined />}
          tone="linear-gradient(135deg, #eff6ff, #dbeafe)"
        />
        <KpiCard
          label="库存预警"
          value={`${kpis?.stock_warning_count ?? '—'}`}
          hint="低于安全库存，建议尽快补货"
          icon={<WarningOutlined />}
          tone="linear-gradient(135deg, #fff7ed, #ffedd5)"
        />
        <KpiCard
          label="近 30 天 GMV"
          value={`¥${(kpis?.gmv_30d ?? 0).toLocaleString()}`}
          hint={`整体 ROI ${kpis?.roi_30d ?? 0}`}
          icon={<ThunderboltOutlined />}
          tone="linear-gradient(135deg, #f5f3ff, #ede9fe)"
        />
      </div>

      <div className="dash-row">
        <Card
          className="surface-card chart-card"
          title={
            <div>
              <div className="card-title">GMV 走势</div>
              <div className="card-subtitle">近 14 天全店成交走势</div>
            </div>
          }
          extra={<Tag bordered={false} color="green">实时汇总</Tag>}
        >
          <TrendChart
            data={(summary?.trend ?? []).map((point) => ({ date: point.date, value: point.gmv }))}
            height={272}
            name="GMV"
          />
        </Card>

        <Card
          className="surface-card store-card"
          title={
            <div>
              <div className="card-title">店铺概览</div>
              <div className="card-subtitle">多平台店铺与授权状态</div>
            </div>
          }
          extra={
            user?.role === 'manager' ? (
              <Button
                type="link"
                size="small"
                icon={<SettingOutlined />}
                onClick={() => setStoreModalOpen(true)}
              >
                管理店铺
              </Button>
            ) : undefined
          }
        >
          {summary?.stores.length ? (
            summary.stores.map((store) => <StoreCard key={store.id} store={store} />)
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无店铺" />
          )}
        </Card>
      </div>

      <div className="dash-row">
        <Card
          className="surface-card"
          title={
            <div>
              <div className="card-title">商品运营总览</div>
              <div className="card-subtitle">按经营闭环阶段追踪每一款单品</div>
            </div>
          }
          extra={<span className="muted">共 {products.length} 款</span>}
        >
          <Table
            rowKey="id"
            columns={productColumns}
            dataSource={products}
            pagination={false}
            size="middle"
            onRow={(record) => ({
              onClick: () => navigate(`/products/${record.id}`),
              className: 'clickable-row',
            })}
          />
        </Card>

        <Card
          className="surface-card"
          title={
            <div>
              <div className="card-title">库存预警</div>
              <div className="card-subtitle">低于安全库存的 SKU</div>
            </div>
          }
          extra={
            <Tag bordered={false} color={summary?.stock_warnings.length ? 'orange' : 'default'}>
              {summary?.stock_warnings.length ?? 0} 条
            </Tag>
          }
        >
          {summary?.stock_warnings.length ? (
            <Table
              rowKey="sku_id"
              columns={warningColumns}
              dataSource={summary.stock_warnings}
              pagination={false}
              size="small"
              onRow={(record) => ({
                onClick: () => navigate(`/products/${record.product_id}`),
                className: 'clickable-row',
              })}
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="库存健康" />
          )}
        </Card>
      </div>

      <NewProductDrawer
        open={newProductOpen}
        stores={summary?.stores ?? []}
        onClose={() => setNewProductOpen(false)}
        onCreated={(product) => {
          load();
          navigate(`/products/${product.id}`);
        }}
      />
      <StoreManageModal
        open={storeModalOpen}
        onClose={() => setStoreModalOpen(false)}
        onChanged={load}
      />
    </Spin>
  );
}
