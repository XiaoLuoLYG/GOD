import React, { useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Button,
    Card,
    Col,
    Divider,
    Form,
    Input,
    Modal,
    Popconfirm,
    Radio,
    Row,
    Space,
    Table,
    Tag,
    Tooltip,
    Typography,
    Upload,
    message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
    DeleteOutlined,
    EditOutlined,
    FolderOpenOutlined,
    ImportOutlined,
    PlusOutlined,
    SaveOutlined,
    UploadOutlined,
} from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import LanguageToggle from '../../components/LanguageToggle';
import { fetchCustom } from '../../components/fetch';
import { AgentEditorModal, type AgentEditorSaveMeta, type AgentStudioLocation } from './AgentEditorModal';
import {
    jsonStringify,
    type AgentClassInfo,
    type AgentFormValues,
    type AgentRecord,
} from './agentEditor';
import './agentStudio.css';

const { Text, Paragraph } = Typography;

type InitConfigPayload = {
    env_modules: Array<{ module_type: string; kwargs: Record<string, any> }>;
    agents: AgentRecord[];
    codegen_router?: { final_summary_enabled?: boolean };
};

type InitConfigResponse = {
    config: InitConfigPayload;
    path: string;
    experiment_context?: Record<string, any> | null;
    map_id?: string | null;
    map_locations?: AgentStudioLocation[];
};

type ImportPreviewRow = {
    row_index: number;
    valid: boolean;
    errors: string[];
    agent?: AgentRecord;
    raw?: Record<string, any>;
};

type ImportPreview = {
    rows: ImportPreviewRow[];
    valid_count: number;
    invalid_count: number;
};

type AgentBuilderPanelProps = {
    initialWorkspacePath?: string;
    initialHypothesisId?: string;
    initialExperimentId?: string;
    embedded?: boolean;
    autoLoad?: boolean;
    autoSaveOnAgentSave?: boolean;
    onSaved?: () => void | Promise<void>;
};

type DefaultProfile = {
    name: string;
    role: string;
    persona: string;
    goal: string;
};

const DEFAULT_PROFILE: DefaultProfile = {
    name: '',
    role: '小镇居民',
    persona: '主动、可靠、会根据小镇当前情况和其他居民协作',
    goal: '参与小镇日常协作，并在下一次 step 中根据环境变化做出响应。',
};

const DEFAULT_JIUWEN_KWARGS = {
    jiuwenclaw_ws_url: 'ws://127.0.0.1:19092',
    session_id: 'god_town_live_agent_1',
    mode: 'agent.plan',
    trusted_dirs: [] as string[],
    enable_memory: true,
    request_timeout: 900,
    channel_id: 'agentsociety',
};
const STORAGE_KEY = 'agentsociety.agentBuilder.workspacePath';

const getAgentName = (agent: AgentRecord) => {
    const kwargs = agent.kwargs || {};
    const profile = kwargs.profile;
    return String(kwargs.name || (profile && profile.name) || `Agent_${agent.agent_id}`);
};

const getEnvModule = (config: InitConfigPayload | null) => config?.env_modules?.[0];

const shortJson = (value: any, maxLength = 120) => {
    const text = JSON.stringify(value ?? {});
    return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
};

const getDuplicateIds = (agents: AgentRecord[]) => {
    const seen = new Set<number>();
    const duplicates = new Set<number>();
    agents.forEach((agent) => {
        if (seen.has(agent.agent_id)) {
            duplicates.add(agent.agent_id);
        }
        seen.add(agent.agent_id);
    });
    return duplicates;
};

const findDefaultAgentType = (classes: AgentClassInfo[]) => {
    if (classes.some((item) => item.type === 'JiuwenClawAgent')) {
        return 'JiuwenClawAgent';
    }
    if (classes.some((item) => item.type === 'PersonAgent')) {
        return 'PersonAgent';
    }
    return classes[0]?.type || 'JiuwenClawAgent';
};

const buildDefaultAgentValues = (
    nextId: number,
    classes: AgentClassInfo[],
    currentAgents: AgentRecord[],
    workspacePath: string,
    defaultProfile: DefaultProfile,
    experimentContext?: Record<string, any> | null,
): AgentFormValues => {
    const agentType = findDefaultAgentType(classes);
    const existing = currentAgents.find((agent) => agent.agent_type === agentType);
    const existingProfile = existing?.kwargs?.profile && typeof existing.kwargs.profile === 'object'
        ? existing.kwargs.profile
        : {};
    const { id: _id, name: _name, profile: _profile, ...existingExtra } = existing?.kwargs || {};
    const name = agentType === 'JiuwenClawAgent' ? `Jiuwen Agent ${nextId}` : `Agent_${nextId}`;
    const profile = {
        ...defaultProfile,
        ...existingProfile,
        name,
        scenario: existingProfile.scenario || String(experimentContext?.background || ''),
    };
    const kwargs = agentType === 'JiuwenClawAgent'
        ? {
            ...DEFAULT_JIUWEN_KWARGS,
            trusted_dirs: workspacePath ? [workspacePath.replace(/\/quick_experiments$/, '')] : DEFAULT_JIUWEN_KWARGS.trusted_dirs,
            experiment_context: experimentContext || existingExtra.experiment_context,
            ...existingExtra,
        }
        : { ...existingExtra };

    if (typeof kwargs.session_id === 'string') {
        kwargs.session_id = kwargs.session_id.match(/_agent_\d+$/)
            ? kwargs.session_id.replace(/_agent_\d+$/, `_agent_${nextId}`)
            : `${kwargs.session_id}_agent_${nextId}`;
    }

    return {
        agent_id: nextId,
        agent_type: agentType,
        name,
        profile_json: jsonStringify(profile),
        kwargs_json: jsonStringify(kwargs),
    };
};

export const AgentBuilderPanel: React.FC<AgentBuilderPanelProps> = ({
    initialWorkspacePath,
    initialHypothesisId,
    initialExperimentId,
    embedded = false,
    autoLoad = false,
    autoSaveOnAgentSave = false,
    onSaved,
}) => {
    const { t } = useTranslation();
    const [searchParams, setSearchParams] = useSearchParams();
    const [workspacePath, setWorkspacePath] = useState(
        initialWorkspacePath ||
        searchParams.get('workspace_path') ||
        localStorage.getItem(STORAGE_KEY) ||
        import.meta.env.VITE_WORKSPACE_PATH ||
        ''
    );
    const [hypothesisId, setHypothesisId] = useState(initialHypothesisId || searchParams.get('hypothesis_id') || '1');
    const [experimentId, setExperimentId] = useState(initialExperimentId || searchParams.get('experiment_id') || '1');
    const [configPath, setConfigPath] = useState('');
    const [config, setConfig] = useState<InitConfigPayload | null>(null);
    const [experimentContext, setExperimentContext] = useState<Record<string, any> | null>(null);
    const [mapId, setMapId] = useState('the_ville');
    const [mapLocations, setMapLocations] = useState<AgentStudioLocation[]>([]);
    const [agentClasses, setAgentClasses] = useState<AgentClassInfo[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [agentModalOpen, setAgentModalOpen] = useState(false);
    const [editingAgentId, setEditingAgentId] = useState<number | null>(null);
    const [importModalOpen, setImportModalOpen] = useState(false);
    const [importFormat, setImportFormat] = useState<'auto' | 'csv' | 'json'>('auto');
    const [importContent, setImportContent] = useState('');
    const [importMode, setImportMode] = useState<'append' | 'replace'>('append');
    const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
    const [form] = Form.useForm<AgentFormValues>();

    const agents = config?.agents || [];
    const duplicateIds = useMemo(() => getDuplicateIds(agents), [agents]);
    const hasInvalidAgents = agents.some((agent) => !agent.kwargs || agent.kwargs.id !== agent.agent_id) || duplicateIds.size > 0;
    const defaultProfile = useMemo<DefaultProfile>(() => ({
        ...DEFAULT_PROFILE,
        role: t('agentBuilder.defaults.role'),
        persona: t('agentBuilder.defaults.persona'),
        goal: t('agentBuilder.defaults.goal'),
    }), [t]);

    const endpointBase = `/api/v1/experiment-configs/${encodeURIComponent(hypothesisId)}/${encodeURIComponent(experimentId)}`;
    const query = `workspace_path=${encodeURIComponent(workspacePath)}`;

    useEffect(() => {
        fetchCustom('/api/v1/modules/agent_classes')
            .then((response) => response.ok ? response.json() : Promise.reject(response))
            .then((payload) => setAgentClasses(Object.values(payload.agents || {})))
            .catch((error) => {
                console.error(error);
                message.warning(t('agentBuilder.messages.classesLoadFailed'));
            });
    }, [t]);

    const updateUrlState = () => {
        const params = new URLSearchParams();
        if (workspacePath) params.set('workspace_path', workspacePath);
        if (hypothesisId) params.set('hypothesis_id', hypothesisId);
        if (experimentId) params.set('experiment_id', experimentId);
        if (!embedded) {
            setSearchParams(params);
        }
        if (workspacePath) {
            localStorage.setItem(STORAGE_KEY, workspacePath);
        }
    };

    const loadConfig = async () => {
        if (!workspacePath || !hypothesisId || !experimentId) {
            message.warning(t('agentBuilder.messages.requiredPath'));
            return;
        }
        setLoading(true);
        try {
            updateUrlState();
            const response = await fetchCustom(`${endpointBase}/init?${query}`);
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const payload = await response.json() as InitConfigResponse;
            setConfig(payload.config);
            setConfigPath(payload.path);
            setExperimentContext(payload.experiment_context || null);
            setMapId(payload.map_id || payload.experiment_context?.map_id || payload.config.env_modules?.[0]?.kwargs?.map_id || 'the_ville');
            setMapLocations(payload.map_locations || []);
            message.success(t('agentBuilder.messages.loaded'));
        } catch (error) {
            message.error(t('agentBuilder.messages.loadFailed', { error: error instanceof Error ? error.message : String(error) }));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (autoLoad) {
            loadConfig();
        }
        // Auto-load is only intended for the initial embedded mount.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoLoad]);

    const persistConfig = async (targetConfig: InitConfigPayload | null = config) => {
        if (!targetConfig) return false;
        setSaving(true);
        try {
            const response = await fetchCustom(`${endpointBase}/init?${query}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(targetConfig),
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const payload = await response.json() as InitConfigResponse;
            setConfig(payload.config);
            setConfigPath(payload.path);
            setExperimentContext(payload.experiment_context || experimentContext);
            setMapId(payload.map_id || mapId);
            setMapLocations(payload.map_locations || mapLocations);
            message.success(t('agentBuilder.messages.saved'));
            return true;
        } catch (error) {
            message.error(t('agentBuilder.messages.saveFailed', { error: error instanceof Error ? error.message : String(error) }));
            return false;
        } finally {
            setSaving(false);
        }
    };

    const saveConfig = async () => {
        if (await persistConfig()) {
            await onSaved?.();
        }
    };

    const openCreateAgent = () => {
        const nextId = agents.length ? Math.max(...agents.map((agent) => agent.agent_id)) + 1 : 1;
        setEditingAgentId(null);
        form.setFieldsValue(buildDefaultAgentValues(nextId, agentClasses, agents, workspacePath, defaultProfile, experimentContext));
        setAgentModalOpen(true);
    };

    const openEditAgent = (agent: AgentRecord) => {
        const profile = agent.kwargs?.profile || {};
        const { id, name, profile: _profile, ...extraKwargs } = agent.kwargs || {};
        setEditingAgentId(agent.agent_id);
        form.setFieldsValue({
            agent_id: agent.agent_id,
            agent_type: agent.agent_type,
            name: String(name || profile.name || `Agent_${agent.agent_id}`),
            profile_json: jsonStringify(profile),
            kwargs_json: jsonStringify(extraKwargs),
        });
        setAgentModalOpen(true);
    };

    const syncEnvForAgents = (
        baseConfig: InitConfigPayload,
        nextAgents: AgentRecord[],
        touchedAgent?: AgentRecord,
        meta?: AgentEditorSaveMeta,
    ): InitConfigPayload => {
        const envModules = baseConfig.env_modules.map((module, index) => {
            if (index !== 0) return module;
            const currentLocations = module.kwargs.initial_locations && typeof module.kwargs.initial_locations === 'object'
                ? module.kwargs.initial_locations
                : {};
            const nextLocations = { ...currentLocations };
            if (touchedAgent) {
                nextLocations[String(touchedAgent.agent_id)] = (
                    meta?.initial_location
                    || nextLocations[String(touchedAgent.agent_id)]
                    || mapLocations[0]?.id
                    || 'park'
                );
            }
            Object.keys(nextLocations).forEach((agentId) => {
                if (!nextAgents.some((item) => String(item.agent_id) === agentId)) {
                    delete nextLocations[agentId];
                }
            });
            return {
                ...module,
                kwargs: {
                    ...module.kwargs,
                    map_id: module.kwargs.map_id || mapId,
                    agent_id_name_pairs: nextAgents.map((item) => [item.agent_id, getAgentName(item)]),
                    initial_locations: nextLocations,
                },
            };
        });
        return { ...baseConfig, agents: nextAgents, env_modules: envModules };
    };

    const upsertAgent = async (agent: AgentRecord, meta?: AgentEditorSaveMeta) => {
        if (!config) return;
        const nextAgents = editingAgentId === null
            ? [...agents, agent]
            : agents.map((item) => item.agent_id === editingAgentId ? agent : item);
        const nextConfig = syncEnvForAgents(config, nextAgents, agent, meta);
        if (autoSaveOnAgentSave) {
            if (!(await persistConfig(nextConfig))) {
                return;
            }
            setAgentModalOpen(false);
            await onSaved?.();
            return;
        }
        setConfig(nextConfig);
        setAgentModalOpen(false);
    };

    const deleteAgent = (agentId: number) => {
        if (!config) return;
        const nextAgents = agents.filter((agent) => agent.agent_id !== agentId);
        setConfig(syncEnvForAgents(config, nextAgents));
    };

    const previewImport = async () => {
        if (!importContent.trim()) {
            message.warning(t('agentBuilder.messages.importContentRequired'));
            return;
        }
        try {
            const response = await fetchCustom(`${endpointBase}/agents/import-preview?${query}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: importContent, format: importFormat }),
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const payload = await response.json();
            setImportPreview(payload);
            message.success(t('agentBuilder.messages.previewReady', { valid: payload.valid_count, invalid: payload.invalid_count }));
        } catch (error) {
            message.error(t('agentBuilder.messages.previewFailed', { error: error instanceof Error ? error.message : String(error) }));
        }
    };

    const applyImport = async () => {
        if (!importPreview) return;
        const validAgents = importPreview.rows
            .filter((row) => row.valid && row.agent)
            .map((row) => row.agent as AgentRecord);
        if (!validAgents.length) {
            message.warning(t('agentBuilder.messages.noValidRows'));
            return;
        }
        try {
            const response = await fetchCustom(`${endpointBase}/agents/apply?${query}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agents: validAgents,
                    mode: importMode,
                    sync_agent_id_name_pairs: true,
                }),
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const payload = await response.json();
            setConfig(payload.config);
            setConfigPath(payload.path);
            setImportModalOpen(false);
            setImportPreview(null);
            setImportContent('');
            if (payload.warnings?.length) {
                message.warning(payload.warnings.join(' '));
            } else {
                message.success(t('agentBuilder.messages.imported', { count: validAgents.length }));
            }
        } catch (error) {
            message.error(t('agentBuilder.messages.applyImportFailed', { error: error instanceof Error ? error.message : String(error) }));
        }
    };

    const agentColumns: ColumnsType<AgentRecord> = [
        {
            title: 'ID',
            dataIndex: 'agent_id',
            width: 90,
            sorter: (a, b) => a.agent_id - b.agent_id,
        },
        {
            title: t('agentBuilder.columns.name'),
            render: (_, record) => getAgentName(record),
        },
        {
            title: t('agentBuilder.columns.agentType'),
            dataIndex: 'agent_type',
            render: (value: string) => <Tag color="blue">{value}</Tag>,
        },
        {
            title: t('agentBuilder.columns.profile'),
            render: (_, record) => (
                <Tooltip title={<pre style={{ margin: 0 }}>{jsonStringify(record.kwargs?.profile)}</pre>}>
                    <Text code>{shortJson(record.kwargs?.profile)}</Text>
                </Tooltip>
            ),
        },
        {
            title: t('agentBuilder.columns.kwargs'),
            render: (_, record) => {
                const { profile, ...rest } = record.kwargs || {};
                return (
                    <Tooltip title={<pre style={{ margin: 0 }}>{jsonStringify(rest)}</pre>}>
                        <Text code>{shortJson(rest)}</Text>
                    </Tooltip>
                );
            },
        },
        {
            title: t('agentBuilder.columns.status'),
            width: 130,
            render: (_, record) => {
                if (duplicateIds.has(record.agent_id)) {
                    return <Tag color="red">{t('agentBuilder.status.duplicateId')}</Tag>;
                }
                if (record.kwargs?.id !== record.agent_id) {
                    return <Tag color="orange">{t('agentBuilder.status.idMismatch')}</Tag>;
                }
                return <Tag color="green">{t('agentBuilder.status.valid')}</Tag>;
            },
        },
        {
            title: t('agentBuilder.columns.actions'),
            width: 110,
            render: (_, record) => (
                <Space size="small">
                    <Tooltip title={t('agentBuilder.actions.edit')}>
                        <Button size="small" icon={<EditOutlined />} onClick={() => openEditAgent(record)} />
                    </Tooltip>
                    <Popconfirm title={t('agentBuilder.messages.deleteConfirm')} onConfirm={() => deleteAgent(record.agent_id)}>
                        <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                </Space>
            ),
        },
    ];

    const previewColumns: ColumnsType<ImportPreviewRow> = [
        { title: t('agentBuilder.columns.row'), dataIndex: 'row_index', width: 80 },
        {
            title: t('agentBuilder.columns.status'),
            width: 110,
            render: (_, row) => row.valid
                ? <Tag color="green">{t('agentBuilder.status.valid')}</Tag>
                : <Tag color="red">{t('agentBuilder.status.invalid')}</Tag>,
        },
        {
            title: t('agentBuilder.columns.agent'),
            render: (_, row) => row.agent ? `${row.agent.agent_id} · ${getAgentName(row.agent)} · ${row.agent.agent_type}` : '-',
        },
        {
            title: t('agentBuilder.columns.errors'),
            render: (_, row) => row.errors.length ? row.errors.join('; ') : '-',
        },
    ];

    const content = (
        <>
            <Card
                    title={t('agentBuilder.title')}
                    extra={
                        <Space wrap>
                            <LanguageToggle />
                            <Button icon={<FolderOpenOutlined />} onClick={loadConfig} loading={loading}>
                                {t('agentBuilder.actions.load')}
                            </Button>
                            <Button
                                type="primary"
                                icon={<SaveOutlined />}
                                onClick={saveConfig}
                                disabled={!config || hasInvalidAgents}
                                loading={saving}
                            >
                                {t('agentBuilder.actions.save')}
                            </Button>
                        </Space>
                    }
                >
                    <Row gutter={[12, 12]}>
                        <Col xs={24} lg={12}>
                            <Input
                                addonBefore={t('agentBuilder.fields.workspace')}
                                value={workspacePath}
                                onChange={(event) => setWorkspacePath(event.target.value)}
                                placeholder="/path/to/workspace"
                            />
                        </Col>
                        <Col xs={12} lg={6}>
                            <Input
                                addonBefore={t('agentBuilder.fields.hypothesis')}
                                value={hypothesisId}
                                onChange={(event) => setHypothesisId(event.target.value)}
                            />
                        </Col>
                        <Col xs={12} lg={6}>
                            <Input
                                addonBefore={t('agentBuilder.fields.experiment')}
                                value={experimentId}
                                onChange={(event) => setExperimentId(event.target.value)}
                            />
                        </Col>
                    </Row>

                    {configPath && (
                        <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
                            {t('agentBuilder.messages.loadedFrom')} <Text code>{configPath}</Text>
                        </Paragraph>
                    )}

                    <Divider />

                    <Space wrap style={{ marginBottom: 12 }}>
                        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateAgent} disabled={!config}>
                            {t('agentBuilder.actions.addAgent')}
                        </Button>
                        <Button icon={<ImportOutlined />} onClick={() => setImportModalOpen(true)} disabled={!config}>
                            {t('agentBuilder.actions.batchImport')}
                        </Button>
                        <Tag>{t('agentBuilder.messages.agentCount', { count: agents.length })}</Tag>
                    </Space>

                    {hasInvalidAgents && (
                        <Alert
                            type="warning"
                            showIcon
                            message={t('agentBuilder.messages.invalidAgents')}
                            style={{ marginBottom: 12 }}
                        />
                    )}

                    <Table
                        rowKey={(record) => `${record.agent_id}-${record.agent_type}-${getAgentName(record)}`}
                        columns={agentColumns}
                        dataSource={agents}
                        loading={loading}
                        pagination={{ pageSize: 10, showSizeChanger: true }}
                        scroll={{ x: 900 }}
                    />
            </Card>

            <AgentEditorModal
                open={agentModalOpen}
                editingAgentId={editingAgentId}
                form={form}
                agentClasses={agentClasses}
                experimentContext={experimentContext || agents[0]?.kwargs?.experiment_context || agents[0]?.kwargs?.profile?.experiment_context || {}}
                mapId={mapId}
                mapLocations={mapLocations}
                existingAgents={agents}
                initialLocation={editingAgentId === null ? undefined : getEnvModule(config)?.kwargs?.initial_locations?.[String(editingAgentId)]}
                defaultInitialLocation={mapLocations[0]?.id || 'park'}
                onSave={upsertAgent}
                onCancel={() => setAgentModalOpen(false)}
            />

            <Modal
                title={t('agentBuilder.import.title')}
                open={importModalOpen}
                onCancel={() => setImportModalOpen(false)}
                footer={[
                    <Button key="cancel" onClick={() => setImportModalOpen(false)}>{t('agentBuilder.actions.cancel')}</Button>,
                    <Button key="preview" onClick={previewImport}>{t('agentBuilder.actions.preview')}</Button>,
                    <Button key="apply" type="primary" disabled={!importPreview?.valid_count} onClick={applyImport}>
                        {t('agentBuilder.actions.applyValidRows')}
                    </Button>,
                ]}
                width="82vw"
                destroyOnHidden
            >
                <Space direction="vertical" style={{ width: '100%' }} size={12}>
                    <Alert
                        type="info"
                        showIcon
                        message={t('agentBuilder.import.help')}
                    />
                    <Row gutter={12}>
                        <Col span={12}>
                            <Radio.Group value={importFormat} onChange={(event) => setImportFormat(event.target.value)}>
                                <Radio.Button value="auto">{t('agentBuilder.import.auto')}</Radio.Button>
                                <Radio.Button value="csv">CSV</Radio.Button>
                                <Radio.Button value="json">JSON</Radio.Button>
                            </Radio.Group>
                        </Col>
                        <Col span={12} style={{ textAlign: 'right' }}>
                            <Radio.Group value={importMode} onChange={(event) => setImportMode(event.target.value)}>
                                <Radio.Button value="append">{t('agentBuilder.import.append')}</Radio.Button>
                                <Radio.Button value="replace">{t('agentBuilder.import.replace')}</Radio.Button>
                            </Radio.Group>
                        </Col>
                    </Row>
                    <Upload.Dragger
                        beforeUpload={(file) => {
                            file.text().then(setImportContent);
                            return false;
                        }}
                        maxCount={1}
                        accept=".csv,.json"
                    >
                        <p className="ant-upload-drag-icon"><UploadOutlined /></p>
                        <p className="ant-upload-text">{t('agentBuilder.import.dropText')}</p>
                    </Upload.Dragger>
                    <Input.TextArea
                        rows={10}
                        value={importContent}
                        onChange={(event) => setImportContent(event.target.value)}
                        placeholder={t('agentBuilder.import.contentPlaceholder')}
                        spellCheck={false}
                    />
                    {importPreview && (
                        <Table
                            rowKey="row_index"
                            size="small"
                            columns={previewColumns}
                            dataSource={importPreview.rows}
                            pagination={{ pageSize: 8 }}
                            scroll={{ x: 720 }}
                            title={() => (
                                <Space>
                                    <Tag color="green">{t('agentBuilder.import.validCount', { count: importPreview.valid_count })}</Tag>
                                    <Tag color={importPreview.invalid_count ? 'red' : 'default'}>
                                        {t('agentBuilder.import.invalidCount', { count: importPreview.invalid_count })}
                                    </Tag>
                                </Space>
                            )}
                        />
                    )}
                </Space>
            </Modal>
        </>
    );

    if (embedded) {
        return content;
    }

    return (
        <div className="agent-builder-page">
            {content}
        </div>
    );
};

const AgentBuilder: React.FC = () => <AgentBuilderPanel />;

export default AgentBuilder;
