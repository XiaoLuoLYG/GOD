import { useEffect, useState, useRef } from "react";

import { Col, Row, message, Table, Button, Space, Popconfirm, Modal, Dropdown, Select } from 'antd';
import { parseT } from "../../components/util";
import { useNavigate } from "react-router-dom";
import { Experiment } from "../../components/type";
import { ProColumns, ProDescriptions, ProTable } from "@ant-design/pro-components";
import { ActionType } from "@ant-design/pro-table";
import { EllipsisOutlined, ReloadOutlined, PlusOutlined } from "@ant-design/icons";
import { fetchCustom, postDownloadCustom } from "../../components/fetch";
import { useTranslation } from "react-i18next";

const Page = () => {
    const { t } = useTranslation();
    const navigate = useNavigate(); // 获取导航函数
    const [detail, setDetail] = useState<Experiment | null>(null);
    const [logVisible, setLogVisible] = useState(false);
    const [logContent, setLogContent] = useState('');
    const [logLoading, setLogLoading] = useState(false);
    const actionRef = useRef<ActionType>();
    const [currentExpId, setCurrentExpId] = useState<string>('');
    const [refreshInterval, setRefreshInterval] = useState<number>(0);
    const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

    // 清理定时器
    const clearRefreshTimer = () => {
        if (refreshTimerRef.current) {
            clearInterval(refreshTimerRef.current);
            refreshTimerRef.current = null;
        }
    };

    // 设置新的定时器
    const setupRefreshTimer = (interval: number, expId: string) => {
        clearRefreshTimer();
        if (interval > 0) {
            refreshTimerRef.current = setInterval(() => {
                fetchLog(expId);
            }, interval * 1000);
        }
    };

    // 组件卸载时清理定时器
    useEffect(() => {
        return () => clearRefreshTimer();
    }, []);

    const fetchLog = async (experimentId: string) => {
        // 不清空现有内容，只显示loading状态
        setLogLoading(true);
        const oldContent = logContent;  // 保存现有内容
        try {
            const res = await fetchCustom(`/api/run-experiments/${experimentId}/log`);
            if (res.ok) {
                const log = await res.text();
                setLogContent(log.replace(/\\n/g, '\n'));
            } else {
                throw new Error(await res.text());
            }
        } catch (err) {
            message.error('Failed to fetch log: ' + err);
            clearRefreshTimer(); // 发生错误时停止刷新
            setLogContent(oldContent);  // 发生错误时恢复原有内容
        } finally {
            setLogLoading(false);
        }
    };

    const parseExperimentIds = (record: Experiment) => {
        const parts = String(record.id || '').split('/').filter(Boolean);
        const rawHypothesis = parts[0] || record.id;
        const rawExperiment = parts[1] || '1';
        return {
            hypothesis_id: rawHypothesis.replace(/^hypothesis_/, ''),
            experiment_id: rawExperiment.replace(/^experiment_/, ''),
        };
    };

    const exportExperimentPack = async (record: Experiment) => {
        try {
            const statusResponse = await fetchCustom('/api/v1/god/setup/status');
            if (!statusResponse.ok) throw new Error(await statusResponse.text());
            const status = await statusResponse.json();
            const ids = parseExperimentIds(record);
            const response = await fetchCustom('/api/v1/god/experiment-packs/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    workspace_path: status.workspace_path,
                    ...ids,
                }),
            });
            if (!response.ok) throw new Error(await response.text());
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `${ids.hypothesis_id}-experiment-pack.zip`;
            link.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            message.error(error instanceof Error ? error.message : String(error));
        }
    };

    const columns: ProColumns<Experiment>[] = [
        { title: t('console.table.id'), dataIndex: 'id', width: '10%' },
        { title: t('console.table.name'), dataIndex: 'name', width: '5%' },
        { title: t('console.table.numDay'), dataIndex: 'num_day', width: '5%', search: false },
        {
            title: t('console.table.status'),
            dataIndex: 'status',
            width: '5%',
            render: (status: number) => {
                return t(`console.statusEnum.${status}`)
            }
        },
        { title: t('console.table.currentDay'), dataIndex: 'cur_day', width: '5%', search: false },
        { title: t('console.table.currentTime'), dataIndex: 'cur_t', width: '5%', render: (t: number) => parseT(t), search: false },
        { title: t('console.table.inputTokens'), dataIndex: 'input_tokens', width: '5%', search: false },
        { title: t('console.table.outputTokens'), dataIndex: 'output_tokens', width: '5%', search: false },
        {
            title: t('console.table.createdAt'),
            dataIndex: 'created_at',
            width: '5%',
            valueType: "dateTime",
            search: false
        },
        {
            title: t('console.table.updatedAt'),
            dataIndex: 'updated_at',
            width: '5%',
            valueType: "dateTime",
            search: false,
        },
        {
            title: t('console.table.action'),
            width: '5%',
            search: false,
            render: (_, record) => {
                record = { ...record };
                return <Space>
                    <Button
                        type="primary"
                        onClick={() => navigate(`/exp/${record.id}`)}
                        disabled={record.status === 0}
                    >{t('console.buttons.goto')}</Button>
                    {record.status === 1 && (
                        <Popconfirm
                            title={t('console.confirmations.stopExperiment')}
                            onConfirm={async () => {
                                try {
                                    const res = await fetchCustom(`/api/run-experiments/${record.id}`, {
                                        method: 'DELETE',
                                    });
                                    if (res.ok) {
                                        message.success(t('console.messages.stopSuccess'));
                                        actionRef.current?.reload();
                                    } else {
                                        const errMessage = await res.text();
                                        throw new Error(errMessage);
                                    }
                                } catch (err) {
                                    message.error(t('console.messages.stopFailed') + err);
                                }
                            }}
                        >
                            <Button danger>{t('console.buttons.stop')}</Button>
                        </Popconfirm>
                    )}
                    <Dropdown
                        menu={{
                            items: [
                                {
                                    key: 'detail',
                                    label: t('console.buttons.detail'),
                                    onClick: () => setDetail(record)
                                },
                                {
                                    key: 'log',
                                    label: t('console.buttons.viewLog'),
                                    onClick: () => {
                                        setLogVisible(true);
                                        setCurrentExpId(record.id);
                                        fetchLog(record.id);
                                    }
                                },
                                {
                                    key: 'exportArtifacts',
                                    label: t('console.buttons.exportArtifacts'),
                                    onClick: () => {
                                        postDownloadCustom(`/api/experiments/${record.id}/artifacts`)
                                    }
                                },
                                {
                                    key: 'export',
                                    label: t('console.buttons.export'),
                                    onClick: () => {
                                        postDownloadCustom(`/api/experiments/${record.id}/export`)
                                    }
                                },
                                {
                                    key: 'exportExperimentPack',
                                    label: t('console.buttons.exportExperimentPack'),
                                    onClick: () => {
                                        void exportExperimentPack(record);
                                    }
                                },
                                {
                                    key: 'delete',
                                    label: (
                                        <Popconfirm
                                            title={t('console.confirmations.deleteExperiment')}
                                            onConfirm={async () => {
                                                try {
                                                    const res = await fetchCustom(`/api/experiments/${record.id}`, {
                                                        method: 'DELETE',
                                                    })
                                                    if (res.ok) {
                                                        message.success(t('console.messages.deleteSuccess'));
                                                        actionRef.current?.reload();
                                                    } else {
                                                        const errMessage = await res.text();
                                                        throw new Error(errMessage);
                                                    }
                                                } catch (err) {
                                                    message.error(t('console.messages.deleteFailed') + err);
                                                }
                                            }}
                                        >
                                            <span style={{ color: '#ff4d4f' }}>{t('console.buttons.delete')}</span>
                                        </Popconfirm>
                                    )
                                }
                            ]
                        }}
                    >
                        <Button icon={<EllipsisOutlined />} />
                    </Dropdown>
                </Space>
            },
        },
    ];

    return (
        <>
            <Row>
                <Col span={24}>
                    <ProTable<Experiment>
                        actionRef={actionRef}
                        columns={columns}
                        request={async (params) => {
                            try {
                                const res = await fetchCustom('/api/experiments')
                                let data = await res.json()
                                data = data.data;
                                if (params.name !== undefined && params.name !== '') {
                                    console.log('params.name:', params.name)
                                    data = data.filter((d: Experiment) => d.name.includes(params.name))
                                }
                                if (params.id !== undefined && params.id !== '') {
                                    data = data.filter((d: Experiment) => d.id === params.id)
                                }
                                if (params.status !== undefined) {
                                    data = data.filter((d: Experiment) => d.status == params.status)
                                }
                                return { data, success: true };
                            } catch (err) {
                                console.error('Failed to fetch experiments:', err)
                                return { data: [], success: false }
                            }
                        }}
                        rowKey="id"
                        columnEmptyText="-"
                        search={{
                            optionRender: ({ searchText, resetText }, { form }, dom) => [
                                ...dom,
                                <Button
                                    key="create"
                                    type="primary"
                                    icon={<PlusOutlined />}
                                    onClick={() => navigate('/create-experiment')}
                                >
                                    {t('console.buttons.createExperiment')}
                                </Button>
                            ]
                        }}
                    />
                </Col>
            </Row>
            <Modal
                title={t('console.modals.experimentDetail')}
                width="60vw"
                open={detail !== null}
                onCancel={() => setDetail(null)}
                footer={null}
            >
                <ProDescriptions<Experiment>
                    column={2}
                    title={detail?.name}
                    request={async () => {
                        return {
                            success: true,
                            data: detail,
                        };
                    }}
                    columns={[
                        { title: t('console.table.id'), dataIndex: 'id' },
                        { title: t('console.table.name'), dataIndex: 'name' },
                        { title: t('console.table.createdAt'), dataIndex: 'created_at', valueType: 'dateTime' },
                        { title: t('console.table.updatedAt'), dataIndex: 'updated_at', valueType: 'dateTime' },
                        { title: t('console.table.numDay'), dataIndex: 'num_day' },
                        { title: t('console.table.status'), dataIndex: 'status', render: (status: number) => t(`console.statusEnum.${status}`) },
                        { title: t('console.table.currentDay'), dataIndex: 'cur_day' },
                        { title: t('console.table.currentTime'), dataIndex: 'cur_t', render: (t: number) => parseT(t) },
                        { title: t('console.table.config'), dataIndex: 'config', span: 2, valueType: 'jsonCode' },
                        { title: t('console.table.error'), dataIndex: 'error', span: 2, valueType: 'code' },
                    ]}
                />
            </Modal>
            <Modal
                title={t('console.modals.experimentLog')}
                width="80vw"
                open={logVisible}
                onCancel={() => {
                    setLogVisible(false);
                    setLogContent('');
                    setRefreshInterval(0);
                    clearRefreshTimer();
                }}
                footer={null}
            >
                <div style={{ marginBottom: '16px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <Button
                        icon={<ReloadOutlined />}
                        onClick={() => fetchLog(currentExpId)}
                        loading={logLoading}
                    >
                        {t('console.modals.refresh')}
                    </Button>
                    <Select
                        value={refreshInterval}
                        onChange={(value) => {
                            setRefreshInterval(value);
                            setupRefreshTimer(value, currentExpId);
                        }}
                        style={{ width: 200 }}
                        options={[
                            { value: 0, label: t('console.modals.manualRefresh') },
                            { value: 1, label: t('console.modals.refreshIntervals.oneSecond') },
                            { value: 5, label: t('console.modals.refreshIntervals.fiveSeconds') },
                            { value: 10, label: t('console.modals.refreshIntervals.tenSeconds') },
                            { value: 30, label: t('console.modals.refreshIntervals.thirtySeconds') },
                        ]}
                    />
                    {logLoading && <span style={{ color: '#1890ff' }}>{t('console.modals.refreshing')}</span>}
                </div>
                <pre style={{
                    maxHeight: '70vh',
                    overflow: 'auto',
                    padding: '12px',
                    backgroundColor: '#f5f5f5',
                    borderRadius: '4px'
                }}>
                    {logContent}
                </pre>
            </Modal>
        </>
    );
}

export default Page;
