import { UnderConstruction } from '../components/UnderConstruction';

export function ImportCenter() {
  return (
    <UnderConstruction
      title="批量导入与数据中心"
      description="商品信息、SKU 库存与经营数据的一站式批量导入"
      milestone="M5"
      items={[
        '商品信息 / SKU 库存 / 经营数据三类模板下载（XLSX / CSV）',
        '拖拽上传、表头自动匹配与可调整字段映射',
        '逐行校验预览、错误行高亮与错误明细下载',
        '合法行局部事务提交，重复平台编码 upsert',
      ]}
    />
  );
}
