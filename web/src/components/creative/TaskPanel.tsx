import { useEffect, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Space,
  Table,
  Tag,
  Timeline,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ClockCircleOutlined,
  PictureOutlined,
  ReloadOutlined,
  StopOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { api } from '../../api';
import type { GenerationTaskInfo, TaskAttemptInfo } from '../../api/types';
import {
  taskSourceLabel,
  taskStatusColor,
  taskStatusLabel,
} from '../../utils/catalog';

interface Props {
  tasks: GenerationTaskInfo[];
  onRefresh: () => void;
  focusTaskId?: number | null;
}

function elapsedLabel(task: GenerationTaskInfo): string {
  if (!task.started_at) return '—';
  const end = task.finished_at ? dayjs(task.finished_at) : dayjs();
  const seconds = Math.max(0, end.diff(dayjs(task.started_at), 'second'));
  return `${seconds}s`;
}

function attemptColor(status: string): string {
  if (status === 'succeeded') return 'green';
  if (status === 'failed') return 'red';
  if (status === 'timeout') return 'orange';
  if (status === 'cancelled') return 'gray';
  return 'blue';
}

function AttemptTimeline({ attempts }: { attempts: TaskAttemptInfo[] }) {
  if (!attempts.length) {
    return <span className="muted">尚未开始执行</span>;
  }
  return (
    <Timeline
      items={attempts.map((attempt) => ({
        color: attemptColor(attempt.status),
        children: (
          <div className="attempt-item">
            <div>
              <span className="cell-strong">第 {attempt.attempt_no} 次执行</span>
              <Tag
                bordered={false}
                color={taskStatusColor(attempt.status)}
                style={{ marginLeft: 8 }}
              >
                {taskStatusLabel(attempt.status)}
              </Tag>
            </div>
            <div className="muted">
              {attempt.started_at ? dayjs(attempt.started_at).format('YYYY-MM-DD HH:mm:ss') : '—'}
              {attempt.finished_at
                ? ` → ${dayjs(attempt.finished_at).format('HH:mm:ss')}`
                : ' → 进行中'}
            </div>
            {attempt.error_message && (
              <div className="attempt-error">{attempt.error_message}</div>
            )}
          </div>
        ),
      }))}
    />
  );
}

export function TaskPanel({ tasks, onRefresh, focusTaskId }: Props) {
  const { message, modal } = App.useApp();
  const [detailId, setDetailId] = useState<number | null>(null);

  useEffect(() => {
    if (focusTaskId) setDetailId(focusTaskId);
  }, [focusTaskId]);

  const detail = tasks.find((item) => item.id === detailId) || null;

  const cancel = (task: GenerationTaskInfo) => {
    modal.confirm({
      title: `取消任务 #${task.id}`,
      content:
        task.status === 'running'
          ? '任务正在生成中，取消后本次执行不会产出素材。'
          : '任务仍在排队，取消后不再执行。',
      okText: '取消任务',
      okButtonProps: { danger: true },
      cancelText: '返回',
      onOk: async () => {
        try {
          await api.cancelTask(task.id);
          message.success('任务已取消');
          onRefresh();
        } catch (error) {
          message.error((error as Error).message);
        }
      },
    });
  };

  const retry = async (task: GenerationTaskInfo) => {
    try {
      await api.retryTask(task.id);
      message.success('已重新排队，稍后查看执行结果');
      setDetailId(task.id);
      onRefresh();
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const columns: ColumnsType<GenerationTaskInfo> = [
    {
      title: '任务',
      key: 'task',
      render: (_, record) => (
        <div className="task-cell">
          <span className={`task-type-icon ${record.type}`}>
            {record.type === 'video' ? <VideoCameraOutlined /> : <PictureOutlined />}
          </span>
          <div>
            <div className="cell-strong">
              #{record.id} · {record.source_title || taskSourceLabel(record.source_type)}
            </div>
            <div className="product-sub">
              {taskSourceLabel(record.source_type)}
              {record.plan_version ? ` · 方案 v${record.plan_version}` : ''}
            </div>
          </div>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 108,
      render: (value: string) => (
        <Tag bordered={false} color={taskStatusColor(value)}>
          {value === 'running' && <ClockCircleOutlined spin />} {taskStatusLabel(value)}
        </Tag>
      ),
    },
    {
      title: '尝试',
      key: 'attempt',
      width: 90,
      render: (_, record) => (
        <span>
          {record.attempt}/{record.max_retry + 1}
        </span>
      ),
    },
    {
      title: '耗时',
      key: 'elapsed',
      width: 84,
      render: (_, record) => elapsedLabel(record),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (value: string) => (
        <span className="muted">{dayjs(value).format('MM-DD HH:mm:ss')}</span>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 190,
      render: (_, record) => (
        <Space size={2} wrap>
          <Button type="link" size="small" onClick={() => setDetailId(record.id)}>
            详情
          </Button>
          {(record.status === 'pending' || record.status === 'running') && (
            <Button type="link" size="small" danger icon={<StopOutlined />} onClick={() => cancel(record)}>
              取消
            </Button>
          )}
          {(record.status === 'failed' || record.status === 'timeout') &&
            record.attempt <= record.max_retry && (
              <Tooltip title={`剩余重试次数 ${record.max_retry - record.attempt + 1}`}>
                <Button
                  type="link"
                  size="small"
                  icon={<ReloadOutlined />}
                  onClick={() => retry(record)}
                >
                  重试
                </Button>
              </Tooltip>
            )}
        </Space>
      ),
    },
  ];

  const sourceSnapshot = detail
    ? ((detail.payload_json?.source as Record<string, unknown>) || {})
    : {};

  return (
    <>
      {tasks.length ? (
        <Table
          rowKey="id"
          size="middle"
          columns={columns}
          dataSource={tasks}
          pagination={false}
          scroll={{ x: 820 }}
        />
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无素材任务，在主图方案或视频脚本中点击「生成素材」即可创建"
        />
      )}

      <Drawer
        open={!!detail}
        title={detail ? `任务 #${detail.id} · ${taskSourceLabel(detail.source_type)}` : '任务详情'}
        width={620}
        onClose={() => setDetailId(null)}
      >
        {detail && (
          <>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="状态" span={2}>
                <Tag bordered={false} color={taskStatusColor(detail.status)}>
                  {taskStatusLabel(detail.status)}
                </Tag>
                <span className="muted">
                  {' '}
                  第 {Math.max(detail.attempt, 1)} / {detail.max_retry + 1} 次执行
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="素材类型">
                {detail.type === 'video' ? '视频' : '图片'}
              </Descriptions.Item>
              <Descriptions.Item label="来源">
                {detail.source_title || taskSourceLabel(detail.source_type)}
              </Descriptions.Item>
              <Descriptions.Item label="执行线程">{detail.worker_id || '—'}</Descriptions.Item>
              <Descriptions.Item label="超时阈值">{detail.timeout_seconds}s</Descriptions.Item>
              <Descriptions.Item label="创建时间" span={2}>
                {dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}
              </Descriptions.Item>
              <Descriptions.Item label="开始时间">
                {detail.started_at
                  ? dayjs(detail.started_at).format('YYYY-MM-DD HH:mm:ss')
                  : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="结束时间">
                {detail.finished_at
                  ? dayjs(detail.finished_at).format('YYYY-MM-DD HH:mm:ss')
                  : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="最近心跳" span={2}>
                {detail.heartbeat_at
                  ? dayjs(detail.heartbeat_at).format('YYYY-MM-DD HH:mm:ss')
                  : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="结果素材" span={2}>
                {detail.result_asset_id ? `素材 #${detail.result_asset_id}` : '—'}
              </Descriptions.Item>
            </Descriptions>

            {detail.error_message && (
              <Alert
                type="error"
                showIcon
                style={{ marginTop: 14 }}
                message="错误信息"
                description={detail.error_message}
              />
            )}

            {detail.attachments.length > 0 && (
              <div className="task-attachments">
                <div className="card-title">脚本附件</div>
                <Space direction="vertical" size={4}>
                  {detail.attachments.map((item) => (
                    <a
                      key={item.name}
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      download
                    >
                      {item.kind === 'script_markdown' ? 'Markdown 脚本' : 'JSON 脚本'} ·{' '}
                      {item.name}
                    </a>
                  ))}
                </Space>
              </div>
            )}

            <div className="task-attempts">
              <div className="card-title">执行时间线</div>
              <AttemptTimeline attempts={detail.attempts} />
            </div>

            <div className="task-payload">
              <div className="card-title">任务快照</div>
              <pre>{JSON.stringify(sourceSnapshot, null, 2)}</pre>
            </div>
          </>
        )}
      </Drawer>
    </>
  );
}
