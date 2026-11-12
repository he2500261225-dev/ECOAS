import { Card, Empty, Tag } from 'antd';

export function UnderConstruction({
  title,
  description,
  milestone,
  items,
}: {
  title: string;
  description: string;
  milestone: string;
  items: string[];
}) {
  return (
    <Card className="surface-card">
      <div className="under-construction">
        <div>
          <h2 className="page-title">{title}</h2>
          <p className="page-subtitle">{description}</p>
        </div>
        <Tag color="processing">{milestone} 开放</Tag>
      </div>
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={<span>该模块将在后续里程碑中交付，以下能力已纳入规划：</span>}
      />
      <ul className="planned-list">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </Card>
  );
}
