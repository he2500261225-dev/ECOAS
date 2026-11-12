import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, App, Button, Card, Empty, Select, Space, Spin, Tag } from 'antd';
import {
  InboxOutlined,
  PictureOutlined,
  ThunderboltOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { api } from '../../api';
import type {
  AssetInfo,
  CreativePlanInfo,
  GenerationTaskInfo,
  ImageSchemeInfo,
  VideoScriptInfo,
} from '../../api/types';
import {
  creativeStatusColor,
  creativeStatusLabel,
} from '../../utils/catalog';
import { ImageSchemeCard } from './ImageSchemeCard';
import { VideoScriptPanel } from './VideoScriptPanel';
import { TaskPanel } from './TaskPanel';
import { AssetLibrary } from './AssetLibrary';

interface Props {
  productId: number;
  hasDiagnosis: boolean;
  isService?: boolean;
  onChanged: () => void;
  onGoDiagnosis: () => void;
}

const ACTIVE_TASK_STATUSES = ['pending', 'running'];

export function CreativeWorkspace({
  productId,
  hasDiagnosis,
  isService = false,
  onChanged,
  onGoDiagnosis,
}: Props) {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [plans, setPlans] = useState<CreativePlanInfo[]>([]);
  const [tasks, setTasks] = useState<GenerationTaskInfo[]>([]);
  const [assets, setAssets] = useState<AssetInfo[]>([]);
  const [activePlanId, setActivePlanId] = useState<number | null>(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [creatingSource, setCreatingSource] = useState<string | null>(null);
  const [focusTaskId, setFocusTaskId] = useState<number | null>(null);
  const [planWarnings, setPlanWarnings] = useState<string[]>([]);

  const loadTasks = useCallback(
    async (silent = false) => {
      try {
        setTasks(await api.tasks(productId));
      } catch (error) {
        if (!silent) message.error((error as Error).message);
      }
    },
    [productId, message],
  );

  const loadAssets = useCallback(
    async (silent = false) => {
      try {
        setAssets(await api.assets(productId));
      } catch (error) {
        if (!silent) message.error((error as Error).message);
      }
    },
    [productId, message],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setPlanWarnings([]);
    setFocusTaskId(null);
    Promise.all([api.creativePlans(productId), api.tasks(productId), api.assets(productId)])
      .then(([planItems, taskItems, assetItems]) => {
        if (cancelled) return;
        setPlans(planItems);
        setTasks(taskItems);
        setAssets(assetItems);
        setActivePlanId(planItems[0]?.id ?? null);
      })
      .catch((error) => {
        if (!cancelled) message.error((error as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [productId, message]);

  const hasActiveTasks = tasks.some((task) => ACTIVE_TASK_STATUSES.includes(task.status));

  useEffect(() => {
    if (!hasActiveTasks) return;
    const timer = window.setInterval(() => {
      loadTasks(true);
      loadAssets(true);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [hasActiveTasks, loadTasks, loadAssets]);

  const activePlan = useMemo(
    () => plans.find((item) => item.id === activePlanId) || plans[0] || null,
    [plans, activePlanId],
  );

  const nextVersion = plans.reduce((max, item) => Math.max(max, item.version), 0) + 1;
  const activeSchemes =
    activePlan?.image_schemes.filter((item) => item.status !== 'archived') || [];
  const activeScripts =
    activePlan?.video_scripts.filter((item) => item.status !== 'archived') || [];
  const confirmedSchemes = activeSchemes.filter((item) => item.status === 'confirmed').length;
  const confirmedScripts = activeScripts.filter((item) => item.status === 'confirmed').length;
  const activeTaskCount = tasks.filter((task) =>
    ACTIVE_TASK_STATUSES.includes(task.status),
  ).length;
  const pendingAssetCount = assets.filter((item) => item.status === 'pending_review').length;

  const generatePlan = async () => {
    setGeneratingPlan(true);
    try {
      const created = await api.generateCreativePlan(productId);
      setPlans((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
      setActivePlanId(created.id);
      setPlanWarnings(created.warnings || []);
      message.success(
        isService ? `获客素材方案 v${created.version} 已生成` : `创意方案 v${created.version} 已生成`,
      );
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setGeneratingPlan(false);
    }
  };

  const refreshPlans = async () => {
    try {
      const items = await api.creativePlans(productId);
      setPlans(items);
      setActivePlanId((prev) => (items.some((item) => item.id === prev) ? prev : items[0]?.id ?? null));
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const refreshAssets = async () => {
    await loadAssets();
    onChanged();
  };

  const generateMaterial = async (
    sourceType: 'image_scheme' | 'video_script',
    sourceId: number,
  ) => {
    const key = `${sourceType === 'image_scheme' ? 'image' : 'video'}:${sourceId}`;
    setCreatingSource(key);
    try {
      const task = await api.createTask(sourceType, sourceId);
      message.success(`已提交生成任务 #${task.id}，可在下方任务列表查看进度`);
      setFocusTaskId(task.id);
      await loadTasks();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setCreatingSource(null);
    }
  };

  const videoGeneratingId = creatingSource?.startsWith('video:')
    ? Number(creatingSource.split(':')[1])
    : null;

  if (loading) {
    return (
      <div className="page-loading">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="creative-workspace">
      <Card className="surface-card creative-hero-card">
        <div className="creative-hero">
          <div className="creative-hero-main">
            <div className="card-title">
              {isService ? '获客素材方案工作台' : '创意方案工作台'}
            </div>
            <p className="muted creative-hero-desc">
              {isService
                ? '基于当前版本诊断生成本地生活获客素材方案与短视频分镜，所有字段可在线编辑、确认与归档；素材由应用内 worker 线程异步生成，不会调用外部平台接口。'
                : '基于当前版本诊断生成主图方案与视频分镜，所有字段可在线编辑、确认与归档；素材由应用内 worker 线程异步生成，不会调用外部平台接口。'}
            </p>
            <Space wrap size={6}>
              {activePlan ? (
                <>
                  <Tag bordered={false} color={creativeStatusColor(activePlan.status)}>
                    方案 v{activePlan.version} · {creativeStatusLabel(activePlan.status)}
                  </Tag>
                  <span className="muted">
                    创建于 {dayjs(activePlan.created_at).format('YYYY-MM-DD HH:mm')} · 共{' '}
                    {plans.length} 个版本
                  </span>
                </>
              ) : (
                <Tag bordered={false}>尚未生成方案</Tag>
              )}
            </Space>
          </div>
          <Space wrap>
            {plans.length > 0 && (
              <Select
                value={activePlan?.id}
                style={{ width: 186 }}
                onChange={(value) => setActivePlanId(value)}
                options={plans.map((item) => ({
                  value: item.id,
                  label: `方案 v${item.version} · ${creativeStatusLabel(item.status)}`,
                }))}
              />
            )}
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={generatingPlan}
              disabled={!hasDiagnosis}
              onClick={generatePlan}
            >
              {plans.length
                ? `生成新版本 v${nextVersion}`
                : isService
                  ? '生成获客素材方案'
                  : '生成创意方案'}
            </Button>
          </Space>
        </div>

        {planWarnings.length > 0 && (
          <Alert
            type="warning"
            showIcon
            closable
            className="creative-inline-alert"
            message="方案生成提示"
            description={
              <ul className="creative-warning-list">
                {planWarnings.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            }
            onClose={() => setPlanWarnings([])}
          />
        )}

        {!hasDiagnosis && (
          <Alert
            type="info"
            showIcon
            className="creative-inline-alert"
            message="当前商品还没有诊断"
            description={
              isService
                ? '获客素材方案需要基于当前版本诊断生成，请先在「档案与诊断」中完成智能诊断。'
                : '创意方案需要基于当前版本诊断生成，请先在「档案与诊断」中完成智能诊断。'
            }
            action={
              <Button size="small" type="primary" onClick={onGoDiagnosis}>
                去生成诊断
              </Button>
            }
          />
        )}
      </Card>

      {activePlan ? (
        <>
          <Card
            className="surface-card"
            title={
              <div className="card-title">
                <PictureOutlined /> {isService ? '获客素材方案' : '主图方案'}
              </div>
            }
            extra={
              <span className="muted">
                {activeSchemes.length} 组 · 已确认 {confirmedSchemes}/{activeSchemes.length}
              </span>
            }
          >
            <div className="creative-card-grid">
              {activePlan.image_schemes.map((scheme: ImageSchemeInfo) => (
                <ImageSchemeCard
                  key={scheme.id}
                  scheme={scheme}
                  isService={isService}
                  onChanged={refreshPlans}
                  generating={creatingSource === `image:${scheme.id}`}
                  onGenerate={(item) => generateMaterial('image_scheme', item.id)}
                />
              ))}
            </div>
          </Card>

          <Card
            className="surface-card"
            title={
              <div className="card-title">
                <VideoCameraOutlined /> 视频分镜脚本
              </div>
            }
            extra={
              <span className="muted">
                {activeScripts.length} 套 · 已确认 {confirmedScripts}/{activeScripts.length} · 每套至少 4 镜
              </span>
            }
          >
            <VideoScriptPanel
              key={activePlan.id}
              scripts={activePlan.video_scripts}
              onChanged={refreshPlans}
              onGenerate={(script: VideoScriptInfo) =>
                generateMaterial('video_script', script.id)
              }
              generatingId={videoGeneratingId}
            />
          </Card>
        </>
      ) : (
        <Card className="surface-card">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              hasDiagnosis
                ? isService
                  ? '尚未生成获客素材方案，点击右上角「生成获客素材方案」基于当前诊断开始'
                  : '尚未生成创意方案，点击右上角「生成创意方案」基于当前诊断开始'
                : '请先在「档案与诊断」完成当前版本诊断'
            }
          >
            {!hasDiagnosis && (
              <Button type="primary" onClick={onGoDiagnosis}>
                去生成诊断
              </Button>
            )}
          </Empty>
        </Card>
      )}

      <Card
        className="surface-card"
        title={
          <div className="card-title">
            <ThunderboltOutlined /> 素材生成任务
          </div>
        }
        extra={
          <span className="muted">
            {activeTaskCount ? `${activeTaskCount} 个进行中 · ` : ''}
            worker 线程执行，进行中任务每 2 秒刷新
          </span>
        }
      >
        <TaskPanel
          tasks={tasks}
          focusTaskId={focusTaskId}
          onRefresh={() => {
            loadTasks();
            loadAssets();
          }}
        />
      </Card>

      <Card
        className="surface-card"
        title={
          <div className="card-title">
            <InboxOutlined /> 素材库
          </div>
        }
        extra={
          <span className="muted">
            {assets.length} 个素材
            {pendingAssetCount ? ` · ${pendingAssetCount} 个待审核` : ''}
          </span>
        }
      >
        <AssetLibrary assets={assets} onRefresh={refreshAssets} />
      </Card>
    </div>
  );
}
