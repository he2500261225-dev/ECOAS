import { Avatar, Dropdown, Layout, Menu, Space, Tag } from 'antd';
import {
  CloudUploadOutlined,
  DashboardOutlined,
  LogoutOutlined,
  SettingOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { roleLabel, useAuth } from '../auth/AuthContext';

const { Sider, Header, Content } = Layout;

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': '运营大盘',
  '/import': '批量导入与数据中心',
  '/settings': '系统与服务配置',
};

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const selectedKey = location.pathname.startsWith('/products')
    ? '/dashboard'
    : location.pathname;

  const items = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: '运营大盘' },
    { key: '/import', icon: <CloudUploadOutlined />, label: '批量导入' },
    ...(user?.role === 'manager'
      ? [{ key: '/settings', icon: <SettingOutlined />, label: '系统配置' }]
      : []),
  ];

  const title = location.pathname.startsWith('/products')
    ? '商品智能运营工作台'
    : PAGE_TITLES[location.pathname] || '智营';

  return (
    <Layout className="app-shell">
      <Sider width={224} className="app-sider" breakpoint="lg" collapsedWidth={0}>
        <div className="brand">
          <div className="brand-mark">智</div>
          <div>
            <div className="brand-name">智营</div>
            <div className="brand-sub">ECOAs 运营助手</div>
          </div>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={items}
          onClick={({ key }) => navigate(key)}
          className="app-menu"
        />
        <div className="sider-foot">
          <span className="status-dot" /> 演示环境 · v0.1
        </div>
      </Sider>
      <Layout>
        <Header className="app-header">
          <div className="header-title">{title}</div>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: '退出登录',
                  onClick: logout,
                },
              ],
            }}
            placement="bottomRight"
          >
            <Space className="header-user" size={10}>
              <Avatar size={34} icon={<UserOutlined />} className="user-avatar" />
              <div className="user-meta">
                <div className="user-name">{user?.display_name || '未登录'}</div>
                <Tag bordered={false} color={user?.role === 'manager' ? 'gold' : 'blue'}>
                  {roleLabel(user?.role)}
                </Tag>
              </div>
            </Space>
          </Dropdown>
        </Header>
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
