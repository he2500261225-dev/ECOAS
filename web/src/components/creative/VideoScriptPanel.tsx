import { useEffect, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Collapse,
  Empty,
  Input,
  InputNumber,
  Space,
  Table,
  Tag,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  CheckOutlined,
  DeleteOutlined,
  InboxOutlined,
  PlusOutlined,
  SaveOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { api } from '../../api';
import type { VideoScriptInfo, VideoShotInfo } from '../../api/types';
import { creativeStatusColor, creativeStatusLabel } from '../../utils/catalog';

interface Props {
  scripts: VideoScriptInfo[];
  onChanged: () => void;
  onGenerate: (script: VideoScriptInfo) => void;
  generatingId?: number | null;
}

function VideoScriptEditor({
  script,
  onChanged,
  onGenerate,
  generating,
}: {
  script: VideoScriptInfo;
  onChanged: () => void;
  onGenerate: (script: VideoScriptInfo) => void;
  generating?: boolean;
}) {
  const { message, modal } = App.useApp();
  const [title, setTitle] = useState(script.title);
  const [hook, setHook] = useState(script.hook_3s);
  const [closing, setClosing] = useState(script.closing_cta);
  const [shots, setShots] = useState<VideoShotInfo[]>(script.shots);
  const [savingScript, setSavingScript] = useState(false);
  const [savingShots, setSavingShots] = useState(false);

  useEffect(() => {
    setTitle(script.title);
    setHook(script.hook_3s);
    setClosing(script.closing_cta);
    setShots(script.shots);
  }, [script]);

  const scriptDirty =
    title !== script.title || hook !== script.hook_3s || closing !== script.closing_cta;

  const dirtyShots = shots.filter((shot) => {
    const origin = script.shots.find((item) => item.id === shot.id);
    if (!origin) return false;
    return (
      origin.duration_sec !== shot.duration_sec ||
      origin.scene_desc !== shot.scene_desc ||
      origin.voiceover !== shot.voiceover ||
      origin.cta_line !== shot.cta_line
    );
  });

  const totalDuration = shots.reduce((sum, shot) => sum + Number(shot.duration_sec || 0), 0);
  const archived = script.status === 'archived';

  const updateShot = (id: number, patch: Partial<VideoShotInfo>) => {
    setShots((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };

  const saveScript = async () => {
    if (!title.trim()) {
      message.warning('脚本标题不能为空');
      return;
    }
    setSavingScript(true);
    try {
      await api.updateVideoScript(script.id, {
        title,
        hook_3s: hook,
        closing_cta: closing,
      });
      message.success('脚本内容已保存');
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSavingScript(false);
    }
  };

  const saveShots = async () => {
    if (!dirtyShots.length) return;
    setSavingShots(true);
    try {
      await Promise.all(
        dirtyShots.map((shot) =>
          api.updateVideoShot(shot.id, {
            duration_sec: Number(shot.duration_sec),
            scene_desc: shot.scene_desc,
            voiceover: shot.voiceover,
            cta_line: shot.cta_line,
          }),
        ),
      );
      message.success(`已保存 ${dirtyShots.length} 个分镜的修改`);
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSavingShots(false);
    }
  };

  const addShot = async () => {
    try {
      const nextNo = shots.length + 1;
      await api.createVideoShot(script.id, {
        duration_sec: 3,
        scene_desc: `分镜 ${nextNo}：补充画面描述`,
        voiceover: '',
        cta_line: '',
      });
      message.success('已新增分镜，请完善画面与口播');
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const removeShot = (shot: VideoShotInfo) => {
    if (shots.length <= 1) {
      message.warning('至少保留一个分镜');
      return;
    }
    modal.confirm({
      title: '删除分镜',
      content: `确定删除镜号 ${shot.shot_no} 吗？删除后镜号会自动重排。`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.deleteVideoShot(shot.id);
          message.success('分镜已删除');
          onChanged();
        } catch (error) {
          message.error((error as Error).message);
        }
      },
    });
  };

  const changeStatus = async (action: 'confirm' | 'archive') => {
    try {
      if (action === 'confirm') {
        await api.confirmVideoScript(script.id);
        message.success('视频脚本已确认');
      } else {
        await api.archiveVideoScript(script.id);
        message.success('视频脚本已归档');
      }
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const columns: ColumnsType<VideoShotInfo> = [
    {
      title: '镜号',
      dataIndex: 'shot_no',
      key: 'shot_no',
      width: 62,
      render: (value: number) => <span className="cell-strong">{value}</span>,
    },
    {
      title: '时长(s)',
      dataIndex: 'duration_sec',
      key: 'duration_sec',
      width: 92,
      render: (value: number, record) => (
        <InputNumber
          min={1}
          max={60}
          value={value}
          disabled={archived}
          onChange={(next) => updateShot(record.id, { duration_sec: Number(next || 1) })}
          style={{ width: '100%' }}
        />
      ),
    },
    {
      title: '画面描述',
      dataIndex: 'scene_desc',
      key: 'scene_desc',
      render: (value: string, record) => (
        <Input.TextArea
          value={value}
          disabled={archived}
          autoSize={{ minRows: 1, maxRows: 3 }}
          onChange={(event) => updateShot(record.id, { scene_desc: event.target.value })}
        />
      ),
    },
    {
      title: '口播台词',
      dataIndex: 'voiceover',
      key: 'voiceover',
      render: (value: string, record) => (
        <Input.TextArea
          value={value}
          disabled={archived}
          autoSize={{ minRows: 1, maxRows: 3 }}
          onChange={(event) => updateShot(record.id, { voiceover: event.target.value })}
        />
      ),
    },
    {
      title: '促单话术',
      dataIndex: 'cta_line',
      key: 'cta_line',
      render: (value: string, record) => (
        <Input
          value={value}
          disabled={archived}
          onChange={(event) => updateShot(record.id, { cta_line: event.target.value })}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 56,
      render: (_, record) => (
        <Button
          type="text"
          danger
          size="small"
          icon={<DeleteOutlined />}
          disabled={archived}
          onClick={() => removeShot(record)}
        />
      ),
    },
  ];

  return (
    <div className="script-editor">
      <div className="form-two-col">
        <div>
          <label className="field-label">脚本标题</label>
          <Input
            value={title}
            disabled={archived}
            onChange={(event) => setTitle(event.target.value)}
          />
        </div>
        <div>
          <label className="field-label">结尾促单</label>
          <Input
            value={closing}
            disabled={archived}
            onChange={(event) => setClosing(event.target.value)}
          />
        </div>
      </div>
      <label className="field-label">前 3 秒钩子</label>
      <Input.TextArea
        rows={2}
        value={hook}
        disabled={archived}
        onChange={(event) => setHook(event.target.value)}
      />

      <div className="script-shots-head">
        <span className="card-title">
          分镜脚本
          <span className="muted">
            {' '}
            共 {shots.length} 镜 · 约 {totalDuration}s
          </span>
        </span>
        <Space>
          <Button size="small" icon={<PlusOutlined />} disabled={archived} onClick={addShot}>
            添加分镜
          </Button>
          <Button
            size="small"
            type="primary"
            icon={<SaveOutlined />}
            loading={savingShots}
            disabled={archived || !dirtyShots.length}
            onClick={saveShots}
          >
            保存分镜{dirtyShots.length ? `（${dirtyShots.length}）` : ''}
          </Button>
        </Space>
      </div>

      {shots.length < 4 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 10 }}
          message={`当前只有 ${shots.length} 个分镜，至少 4 个才能确认脚本`}
        />
      )}

      <Table
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={shots}
        pagination={false}
        scroll={{ x: 880 }}
      />

      <div className="creative-card-actions">
        <Button
          size="small"
          icon={<SaveOutlined />}
          loading={savingScript}
          disabled={archived || !scriptDirty}
          onClick={saveScript}
        >
          保存脚本
        </Button>
        {script.status === 'draft' && (
          <Tooltip title={shots.length < 4 ? '至少 4 个分镜才能确认' : '确认后进入投放素材组合'}>
            <Button
              size="small"
              icon={<CheckOutlined />}
              disabled={shots.length < 4}
              onClick={() => changeStatus('confirm')}
            >
              确认
            </Button>
          </Tooltip>
        )}
        {!archived && (
          <Button
            size="small"
            icon={<InboxOutlined />}
            onClick={() => changeStatus('archive')}
          >
            归档
          </Button>
        )}
        <Button
          size="small"
          type="primary"
          ghost
          icon={<ThunderboltOutlined />}
          disabled={archived}
          loading={generating}
          onClick={() => onGenerate(script)}
        >
          生成视频素材
        </Button>
      </div>
    </div>
  );
}

export function VideoScriptPanel({ scripts, onChanged, onGenerate, generatingId }: Props) {
  if (!scripts.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无视频脚本" />;
  }

  const items = scripts.map((script) => ({
    key: String(script.id),
    label: (
      <div className="script-collapse-head">
        <span className="script-collapse-title">{script.title}</span>
        <Space size={6}>
          <Tag bordered={false}>
            {script.shots.length} 镜 · {script.total_duration}s
          </Tag>
          <Tag bordered={false} color={creativeStatusColor(script.status)}>
            {creativeStatusLabel(script.status)}
          </Tag>
        </Space>
      </div>
    ),
    children: (
      <VideoScriptEditor
        script={script}
        onChanged={onChanged}
        onGenerate={onGenerate}
        generating={generatingId === script.id}
      />
    ),
  }));

  return (
    <Collapse
      className="script-collapse"
      defaultActiveKey={scripts.length ? [String(scripts[0].id)] : []}
      items={items}
    />
  );
}
