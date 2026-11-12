import { Result } from 'antd';
import { UnderConstruction } from '../components/UnderConstruction';
import { useAuth } from '../auth/AuthContext';

export function Settings() {
  const { user } = useAuth();

  if (user?.role !== 'manager') {
    return (
      <Result
        status="403"
        title="无权访问"
        subTitle="系统与服务配置仅对运营主管 / 管理员开放。"
      />
    );
  }

  return (
    <UnderConstruction
      title="系统与服务配置"
      description="维护大模型、多模态服务、异步队列与平台授权配置"
      milestone="M5"
      items={[
        '大语言模型参数：Mock / 真实接口切换、模型名、温度与测试连接',
        '多模态生图 / 生视频服务参数与模拟耗时、失败率',
        '异步任务并发配额、超时秒数与最大重试次数',
        '平台授权占位（仅展示脱敏状态）、高风险投放预算阈值',
        '一键重置演示数据',
      ]}
    />
  );
}
