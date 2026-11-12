import { useEffect, useState } from 'react';
import { App, Drawer, Empty, Spin, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { api } from '../../api';
import type { SkuInfo, StockFlowInfo } from '../../api/types';
import { specLabel, stockReasonLabel } from '../../utils/catalog';

interface Props {
  open: boolean;
  sku: SkuInfo | null;
  onClose: () => void;
}

export function StockFlowDrawer({ open, sku, onClose }: Props) {
  const [flows, setFlows] = useState<StockFlowInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const { message } = App.useApp();

  useEffect(() => {
    if (!open || !sku) return;
    setLoading(true);
    api
      .stockFlows(sku.id)
      .then(setFlows)
      .catch((error) => message.error((error as Error).message))
      .finally(() => setLoading(false));
  }, [open, sku, message]);

  const columns: ColumnsType<StockFlowInfo> = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '变更',
      dataIndex: 'change',
      key: 'change',
      width: 90,
      render: (value: number) => (
        <span className={value >= 0 ? 'flow-in' : 'flow-out'}>
          {value > 0 ? `+${value}` : value}
        </span>
      ),
    },
    {
      title: '原因',
      dataIndex: 'reason',
      key: 'reason',
      width: 110,
      render: (value: string) => <Tag bordered={false}>{stockReasonLabel(value)}</Tag>,
    },
    {
      title: '变更后库存',
      dataIndex: 'stock_after',
      key: 'stock_after',
      width: 110,
    },
    {
      title: '操作人',
      dataIndex: 'operator_name',
      key: 'operator_name',
      width: 100,
      render: (value: string) => value || '系统',
    },
  ];

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={640}
      title={`库存流水 · ${sku ? specLabel(sku.spec) : ''}`}
    >
      <Spin spinning={loading}>
        {flows.length ? (
          <Table
            rowKey="id"
            size="small"
            columns={columns}
            dataSource={flows}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无库存流水" />
        )}
      </Spin>
    </Drawer>
  );
}
