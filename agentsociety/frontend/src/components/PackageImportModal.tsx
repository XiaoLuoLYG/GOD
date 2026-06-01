import React, { useState } from 'react';
import { Alert, Button, Input, Modal, Radio, Space, Table, Tag, Upload, message } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import {
  cancelPackagePreview,
  installPackage,
  previewPackage,
  type PackageInstallResult,
  type PackagePreview,
  type PackageType,
} from './packageImport';

type PackageImportModalProps = {
  open: boolean;
  expectedType?: PackageType;
  onCancel: () => void;
  onInstalled: (result: PackageInstallResult) => void;
};

type PreviewRow = {
  id: string;
  kind: string;
  message: string;
};

const cancelPreview = async (previewToken?: string | null) => {
  if (!previewToken) return;
  try {
    await cancelPackagePreview(previewToken);
  } catch {
    // Preview cleanup is best-effort; the backend will reject expired tokens.
  }
};

const PackageImportModal: React.FC<PackageImportModalProps> = ({
  open,
  expectedType,
  onCancel,
  onInstalled,
}) => {
  const { t } = useTranslation();
  const [preview, setPreview] = useState<PackagePreview | null>(null);
  const [strategy, setStrategy] = useState<'save_as' | 'overwrite' | 'cancel'>('save_as');
  const [requestedId, setRequestedId] = useState('');
  const [loading, setLoading] = useState(false);

  const reset = () => {
    setPreview(null);
    setStrategy('save_as');
    setRequestedId('');
  };

  const close = () => {
    const previewToken = preview?.preview_token;
    reset();
    onCancel();
    void cancelPreview(previewToken);
  };

  const uploadFile = async (file: File) => {
    const previousPreviewToken = preview?.preview_token;
    setLoading(true);
    try {
      const payload = await previewPackage(file);
      void cancelPreview(previousPreviewToken);
      if (expectedType && payload.package_type !== expectedType) {
        message.warning(t('packageImport.unexpectedType', { type: payload.package_type }));
        setPreview(null);
        setRequestedId('');
        void cancelPreview(payload.preview_token);
        return false;
      }
      setPreview(payload);
      setRequestedId(payload.conflict ? `${payload.resource_id}_2` : payload.resource_id);
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
    return false;
  };

  const install = async () => {
    if (!preview) return;
    setLoading(true);
    try {
      const result = await installPackage(
        preview.preview_token,
        strategy,
        strategy === 'save_as' ? requestedId : undefined,
      );
      message.success(t('packageImport.installed', { id: result.resource_id || preview.resource_id }));
      reset();
      onInstalled(result);
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  const rows: PreviewRow[] = preview
    ? [
      ...preview.validation.errors.map((item, index) => ({
        id: `error-${index}`,
        kind: t('packageImport.error'),
        message: item,
      })),
      ...preview.validation.warnings.map((item, index) => ({
        id: `warning-${index}`,
        kind: t('packageImport.warning'),
        message: item,
      })),
      ...preview.dependencies.map((item, index) => ({ id: `dependency-${index}`, kind: item.type, message: item.id })),
    ]
    : [];

  return (
    <Modal
      title={t('packageImport.title')}
      open={open}
      onCancel={close}
      width="min(840px, 92vw)"
      destroyOnHidden
      footer={[
        <Button key="cancel" onClick={close}>{t('common.cancel')}</Button>,
        <Button
          key="install"
          type="primary"
          loading={loading}
          disabled={!preview || !preview.validation.ok || strategy === 'cancel'}
          onClick={install}
        >
          {t('packageImport.install')}
        </Button>,
      ]}
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Upload.Dragger beforeUpload={uploadFile} maxCount={1} accept=".zip" disabled={loading}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">{t('packageImport.dropZip')}</p>
        </Upload.Dragger>
        {preview && (
          <>
            <Alert
              type={preview.validation.ok ? 'success' : 'error'}
              showIcon
              message={t('packageImport.previewReady', { type: preview.package_type, id: preview.resource_id })}
              description={preview.install_path}
            />
            <Space wrap>
              <Tag>{preview.package_type}</Tag>
              <Tag>{preview.display_name || preview.resource_id}</Tag>
              {preview.conflict && <Tag color="orange">{t('packageImport.conflict')}</Tag>}
            </Space>
            {preview.conflict && (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Radio.Group value={strategy} onChange={(event) => setStrategy(event.target.value)}>
                  <Radio.Button value="save_as">{t('packageImport.saveAs')}</Radio.Button>
                  <Radio.Button value="overwrite">{t('packageImport.overwrite')}</Radio.Button>
                  <Radio.Button value="cancel">{t('packageImport.cancelImport')}</Radio.Button>
                </Radio.Group>
                {strategy === 'save_as' && (
                  <Input value={requestedId} onChange={(event) => setRequestedId(event.target.value)} />
                )}
              </Space>
            )}
            {rows.length > 0 && (
              <Table<PreviewRow>
                size="small"
                pagination={false}
                rowKey="id"
                dataSource={rows}
                scroll={{ x: true }}
                columns={[
                  { title: t('packageImport.kind'), dataIndex: 'kind', width: 120 },
                  { title: t('packageImport.message'), dataIndex: 'message' },
                ]}
              />
            )}
          </>
        )}
      </Space>
    </Modal>
  );
};

export default PackageImportModal;
