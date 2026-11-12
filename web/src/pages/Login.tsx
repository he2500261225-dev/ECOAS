import { useState } from 'react';
import { App, Button, Card, Form, Input, Space } from 'antd';
import { LockOutlined, ThunderboltFilled, UserOutlined } from '@ant-design/icons';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export function Login() {
  const { login, token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  if (token) return <Navigate to="/dashboard" replace />;

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      await login(values.username, values.password);
      message.success('登录成功');
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from || '/dashboard', { replace: true });
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const fill = (username: string) => {
    form.setFieldsValue({ username, password: '123456' });
  };

  return (
    <div className="login-page">
      <div className="login-brand">
        <div className="login-logo">
          <div className="brand-mark large">智</div>
          <span>智营 · ECOAs</span>
        </div>
        <h1>用一个工作台，跑通单品经营闭环</h1>
        <p className="login-lead">
          从商品建档、竞品诊断，到创意方案、异步素材、投放审批与经营复盘，
          让 AI 参与每一个经营决策节点。
        </p>
        <div className="login-flow">
          {['建档诊断', '视觉创意', '异步素材', '投放实验', '闭环复盘'].map((step, i) => (
            <div className="login-flow-item" key={step}>
              <span className="flow-index">0{i + 1}</span>
              <span>{step}</span>
            </div>
          ))}
        </div>
        <div className="login-brand-foot">
          <ThunderboltFilled /> 大模型驱动 · 人工审批把关 · 素材异步生产
        </div>
      </div>

      <div className="login-panel">
        <Card className="login-card" variant="borderless">
          <h2>登录运营工作台</h2>
          <p className="login-subtitle">使用演示账号进入，体验完整经营闭环</p>
          <Form form={form} layout="vertical" onFinish={onFinish} initialValues={{ username: 'operator', password: '123456' }}>
            <Form.Item name="username" label="账号" rules={[{ required: true, message: '请输入账号' }]}>
              <Input size="large" prefix={<UserOutlined />} placeholder="operator / manager" />
            </Form.Item>
            <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password size="large" prefix={<LockOutlined />} placeholder="请输入密码" />
            </Form.Item>
            <Button type="primary" htmlType="submit" size="large" block loading={loading}>
              登录
            </Button>
          </Form>
          <div className="login-hint">
            <div className="login-hint-title">演示账号</div>
            <Space wrap>
              <Button size="small" onClick={() => fill('operator')}>
                运营人员 operator / 123456
              </Button>
              <Button size="small" onClick={() => fill('manager')}>
                运营主管 manager / 123456
              </Button>
            </Space>
          </div>
        </Card>
      </div>
    </div>
  );
}
