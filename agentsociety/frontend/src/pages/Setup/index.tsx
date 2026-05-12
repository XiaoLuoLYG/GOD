import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Button,
    Card,
    Col,
    Divider,
    Form,
    Input,
    InputNumber,
    Row,
    Select,
    Space,
    Steps,
    Table,
    Tabs,
    Tag,
    Tooltip,
    Typography,
    message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
    ApiOutlined,
    CheckCircleOutlined,
    DeleteOutlined,
    EditOutlined,
    ExperimentOutlined,
    PlayCircleOutlined,
    QuestionCircleOutlined,
    RobotOutlined,
    SaveOutlined,
    ThunderboltOutlined,
    UserAddOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { fetchCustom } from '../../components/fetch';
import { AgentEditorModal } from '../AgentBuilder/AgentEditorModal';
import {
    jsonStringify,
    parseJsonObject,
    type AgentFormValues,
    type AgentRecord,
} from '../AgentBuilder/agentEditor';
import './style.css';

const { Text, Title, Paragraph } = Typography;

type RedactedValue = {
    configured: boolean;
    value: string;
};

type MapLocation = {
    id: string;
    name: string;
    aliases?: string[];
    interaction_ids?: string[];
};

type SetupStatus = {
    workspace_path: string;
    env_file: string;
    model_config: Record<string, RedactedValue>;
    current_experiment?: {
        hypothesis_id?: string;
        experiment_id?: string;
        workspace_path?: string;
    } | null;
    default_experiment?: {
        hypothesis_id?: string;
        experiment_id?: string;
        workspace_path?: string;
        config_exists?: boolean;
    };
    needs_setup: boolean;
    map_locations: MapLocation[];
};

type DraftPayload = {
    experiment_context: Record<string, any>;
    init_config: {
        env_modules: Array<{ module_type: string; kwargs: Record<string, any> }>;
        agents: AgentRecord[];
        codegen_router?: Record<string, any>;
    };
    steps: Record<string, any>;
    readme: string;
    warnings: string[];
};

type ModelForm = {
    GOD_LLM_API_KEY?: string;
    GOD_LLM_API_BASE?: string;
    GOD_LLM_MODEL?: string;
    GOD_EMBEDDING_API_KEY?: string;
    GOD_EMBEDDING_API_BASE?: string;
    GOD_EMBEDDING_MODEL?: string;
    GOD_BACKEND_HOST?: string;
    GOD_BACKEND_PORT?: string;
    GOD_FRONTEND_PORT?: string;
};

type BasicsForm = {
    title: string;
    background: string;
    agent_count: number;
    language: string;
    start_t: string;
    num_steps: number;
    tick: number;
    movement_tiles_per_second: number;
    movement_min_steps_per_trip: number;
};

const fetchJson = async <T,>(url: string, options?: RequestInit): Promise<T> => {
    const response = await fetchCustom(url, options);
    if (!response.ok) {
        throw new Error(await response.text());
    }
    return response.json();
};

const compactJson = (value: any, length = 140) => {
    const text = JSON.stringify(value ?? {});
    return text.length > length ? `${text.slice(0, length)}...` : text;
};

const agentName = (agent: AgentRecord) => (
    String(agent.kwargs?.name || agent.kwargs?.profile?.name || `Agent ${agent.agent_id}`)
);

const help = (text: string) => (
    <Tooltip title={text}>
        <QuestionCircleOutlined className="setup-help-icon" />
    </Tooltip>
);

const formLabel = (label: string, tooltip: string) => (
    <Space size={6}>
        <span>{label}</span>
        {help(tooltip)}
    </Space>
);

const getEnvModule = (draft: DraftPayload) => draft.init_config.env_modules[0];

const cloneDraft = (draft: DraftPayload): DraftPayload => JSON.parse(JSON.stringify(draft));

const BASICS_STORAGE_KEY = 'god.setup.basics';

const defaultBasics: BasicsForm = {
    title: '斯坦福监狱实验适配模拟',
    background: '请生成一个安全、边界清晰的社会角色压力模拟：参与者被分配为管理者、观察者、普通参与者等角色，重点观察权力、规则、协作和情绪变化，不允许羞辱、伤害或强迫行为。',
    agent_count: 10,
    language: 'zh',
    start_t: '2026-05-11T08:20:00+08:00',
    num_steps: 4,
    tick: 1800,
    movement_tiles_per_second: 8,
    movement_min_steps_per_trip: 3,
};

const normalizeBasicsValues = (values: Partial<BasicsForm> = {}): BasicsForm => ({
    title: String(values.title || defaultBasics.title).trim() || defaultBasics.title,
    background: String(values.background || defaultBasics.background).trim() || defaultBasics.background,
    agent_count: Number(values.agent_count || defaultBasics.agent_count),
    language: values.language || defaultBasics.language,
    start_t: String(values.start_t || defaultBasics.start_t).trim() || defaultBasics.start_t,
    num_steps: Number(values.num_steps || defaultBasics.num_steps),
    tick: Number(values.tick || defaultBasics.tick),
    movement_tiles_per_second: Number(
        values.movement_tiles_per_second || defaultBasics.movement_tiles_per_second
    ),
    movement_min_steps_per_trip: Number(
        values.movement_min_steps_per_trip || defaultBasics.movement_min_steps_per_trip
    ),
});

const loadStoredBasics = (): BasicsForm => {
    if (typeof window === 'undefined') {
        return defaultBasics;
    }
    try {
        const raw = window.localStorage.getItem(BASICS_STORAGE_KEY);
        return raw ? normalizeBasicsValues(JSON.parse(raw)) : defaultBasics;
    } catch {
        return defaultBasics;
    }
};

const saveStoredBasics = (values: BasicsForm) => {
    if (typeof window === 'undefined') {
        return;
    }
    window.localStorage.setItem(BASICS_STORAGE_KEY, JSON.stringify(values));
};

export default function SetupPage() {
    const navigate = useNavigate();
    const [messageApi, messageContextHolder] = message.useMessage();
    const [status, setStatus] = useState<SetupStatus | null>(null);
    const [currentStep, setCurrentStep] = useState(0);
    const [draft, setDraft] = useState<DraftPayload | null>(null);
    const [loadingStatus, setLoadingStatus] = useState(true);
    const [savingModel, setSavingModel] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [publishing, setPublishing] = useState(false);
    const [startingDefault, setStartingDefault] = useState(false);
    const [agentModalOpen, setAgentModalOpen] = useState(false);
    const [editingAgentId, setEditingAgentId] = useState<number | null>(null);
    const [basicsValues, setBasicsValues] = useState<BasicsForm>(() => loadStoredBasics());
    const basicsRef = useRef<BasicsForm>(basicsValues);
    const [agentForm] = Form.useForm<AgentFormValues>();
    const [modelForm] = Form.useForm<ModelForm>();
    const [basicsForm] = Form.useForm<BasicsForm>();

    const locationOptions = useMemo(() => (
        (status?.map_locations || []).map((location) => ({
            value: location.id,
            label: `${location.name} (${location.id})`,
        }))
    ), [status?.map_locations]);

    const loadStatus = async () => {
        setLoadingStatus(true);
        try {
            const payload = await fetchJson<SetupStatus>('/api/v1/god/setup/status');
            setStatus(payload);
            modelForm.setFieldsValue({
                GOD_LLM_API_BASE: payload.model_config.GOD_LLM_API_BASE?.value || 'https://api.openai.com/v1',
                GOD_LLM_MODEL: payload.model_config.GOD_LLM_MODEL?.value || 'gpt-5.4',
                GOD_EMBEDDING_API_BASE: payload.model_config.GOD_EMBEDDING_API_BASE?.value || '',
                GOD_EMBEDDING_MODEL: payload.model_config.GOD_EMBEDDING_MODEL?.value || 'text-embedding-3-large',
                GOD_BACKEND_HOST: payload.model_config.GOD_BACKEND_HOST?.value || '127.0.0.1',
                GOD_BACKEND_PORT: payload.model_config.GOD_BACKEND_PORT?.value || '8001',
                GOD_FRONTEND_PORT: payload.model_config.GOD_FRONTEND_PORT?.value || '5174',
            });
        } catch (error) {
            messageApi.error(`读取 setup 状态失败: ${error instanceof Error ? error.message : String(error)}`);
        } finally {
            setLoadingStatus(false);
        }
    };

    useEffect(() => {
        loadStatus();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (currentStep === 1) {
            basicsForm.setFieldsValue(basicsValues);
        }
        // Only sync when entering the step; while typing, Form owns the live cursor state.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [currentStep]);

    const saveModelConfig = async () => {
        const values = await modelForm.validateFields();
        setSavingModel(true);
        try {
            const payload = await persistModelConfig(values);
            setStatus(payload);
            messageApi.success('模型配置已保存到本地 .env。');
            setCurrentStep(1);
        } catch (error) {
            messageApi.error(`保存模型配置失败: ${error instanceof Error ? error.message : String(error)}`);
        } finally {
            setSavingModel(false);
        }
    };

    const cleanModelValues = (values: ModelForm) => Object.fromEntries(
        Object.entries(values).filter(([, value]) => value !== undefined && String(value).trim() !== '')
    );

    const persistModelConfig = async (values: ModelForm) => fetchJson<SetupStatus>('/api/v1/god/setup/model-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cleanModelValues(values)),
    });

    const syncBasicsValues = (values: Partial<BasicsForm>) => {
        const normalized = normalizeBasicsValues(values);
        basicsRef.current = normalized;
        setBasicsValues(normalized);
        saveStoredBasics(normalized);
        return normalized;
    };

    const persistBasicsFromForm = async () => {
        const values = await basicsForm.validateFields();
        const normalized = syncBasicsValues(values);
        basicsForm.setFieldsValue(normalized);
        return normalized;
    };

    const goToStep = async (targetStep: number) => {
        if (currentStep === 1 && targetStep > 1) {
            try {
                await persistBasicsFromForm();
            } catch {
                return;
            }
        }
        setCurrentStep(targetStep);
    };

    const generateDraft = async () => {
        const modelValues = await modelForm.validateFields();
        const basicsPayload = currentStep === 1
            ? await persistBasicsFromForm()
            : basicsRef.current;
        setGenerating(true);
        try {
            const payload = await fetchJson<DraftPayload>('/api/v1/god/setup/generate-draft', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_config: modelValues,
                    basics: basicsPayload,
                }),
            });
            setDraft(payload);
            setCurrentStep(3);
            messageApi.success('GOD agent 已生成实验草案，可以继续编辑。');
        } catch (error) {
            messageApi.error(`生成实验草案失败: ${error instanceof Error ? error.message : String(error)}`);
        } finally {
            setGenerating(false);
        }
    };

    const startDefaultExperiment = async () => {
        const modelValues = await modelForm.validateFields();
        if (!status?.model_config.GOD_LLM_API_KEY?.configured && !String(modelValues.GOD_LLM_API_KEY || '').trim()) {
            messageApi.error('请先填写并保存 API key，或在本地 .env 中配置 GOD_LLM_API_KEY。');
            return;
        }
        setStartingDefault(true);
        try {
            const nextStatus = await persistModelConfig(modelValues);
            setStatus(nextStatus);
            const result = await fetchJson<{
                hypothesis_id: string;
                experiment_id: string;
                workspace_path: string;
            }>('/api/v1/god/setup/start-default', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            messageApi.success('默认实验已设为当前实验，并已请求 GOD 启动。');
            window.setTimeout(() => {
                navigate(`/pixel-replay/${encodeURIComponent(result.hypothesis_id)}/${encodeURIComponent(result.experiment_id)}?workspace_path=${encodeURIComponent(result.workspace_path)}`);
            }, 700);
        } catch (error) {
            messageApi.error(`启动默认实验失败: ${error instanceof Error ? error.message : String(error)}`);
        } finally {
            setStartingDefault(false);
        }
    };

    const updateContextJson = (text: string) => {
        if (!draft) return;
        try {
            const next = cloneDraft(draft);
            next.experiment_context = parseJsonObject(text, 'experiment_context');
            next.init_config.agents = next.init_config.agents.map((agent) => ({
                ...agent,
                kwargs: {
                    ...agent.kwargs,
                    experiment_context: next.experiment_context,
                    profile: {
                        ...(agent.kwargs?.profile || {}),
                        scenario: String(next.experiment_context.background || ''),
                    },
                },
            }));
            setDraft(next);
            messageApi.success('实验背景已更新。');
        } catch (error) {
            messageApi.error(error instanceof Error ? error.message : String(error));
        }
    };

    const updateStepsJson = (text: string) => {
        if (!draft) return;
        try {
            const next = cloneDraft(draft);
            next.steps = parseJsonObject(text, 'steps');
            setDraft(next);
            messageApi.success('Steps 已更新。');
        } catch (error) {
            messageApi.error(error instanceof Error ? error.message : String(error));
        }
    };

    const updateEnvField = (key: string, value: any) => {
        if (!draft) return;
        if (value === null || value === undefined) return;
        const next = cloneDraft(draft);
        const env = getEnvModule(next);
        env.kwargs[key] = value;
        setDraft(next);
    };

    const updateInitialLocation = (agentId: number, locationId: string) => {
        if (!draft) return;
        const next = cloneDraft(draft);
        const env = getEnvModule(next);
        env.kwargs.initial_locations = {
            ...(env.kwargs.initial_locations || {}),
            [String(agentId)]: locationId,
        };
        setDraft(next);
    };

    const openAgentModal = (agent?: AgentRecord) => {
        if (!draft) return;
        if (agent) {
            const { id: _id, name, profile, ...rest } = agent.kwargs || {};
            setEditingAgentId(agent.agent_id);
            agentForm.setFieldsValue({
                agent_id: agent.agent_id,
                agent_type: agent.agent_type,
                name: String(name || profile?.name || `Agent ${agent.agent_id}`),
                profile_json: jsonStringify(profile || {}),
                kwargs_json: jsonStringify(rest),
            });
        } else {
            const nextId = draft.init_config.agents.length
                ? Math.max(...draft.init_config.agents.map((item) => item.agent_id)) + 1
                : 1;
            setEditingAgentId(null);
            agentForm.setFieldsValue({
                agent_id: nextId,
                agent_type: 'JiuwenClawAgent',
                name: `Jiuwen Agent ${nextId}`,
                profile_json: jsonStringify({
                    name: `Jiuwen Agent ${nextId}`,
                    role: 'participant',
                    persona: '观察、沟通，并遵守实验边界。',
                    skills: ['observation', 'conversation'],
                    scenario: draft.experiment_context.background || '',
                    scenario_role: 'participant',
                }),
                kwargs_json: jsonStringify({
                    jiuwenclaw_ws_url: 'ws://127.0.0.1:19092',
                    session_id: `generated_agent_${nextId}`,
                    mode: 'agent.plan',
                    trusted_dirs: [],
                    enable_memory: true,
                    enable_daily_life: true,
                    enable_skill_runtime: true,
                    request_timeout: 900,
                    channel_id: 'agentsociety',
                    experiment_context: draft.experiment_context,
                }),
            });
        }
        setAgentModalOpen(true);
    };

    const saveAgent = async (baseAgent: AgentRecord) => {
        if (!draft) return;
        const profile = baseAgent.kwargs?.profile && typeof baseAgent.kwargs.profile === 'object'
            ? baseAgent.kwargs.profile
            : {};
        const agent: AgentRecord = {
            ...baseAgent,
            kwargs: {
                ...baseAgent.kwargs,
                experiment_context: draft.experiment_context,
                profile: {
                    ...profile,
                    scenario: profile.scenario || String(draft.experiment_context.background || ''),
                    scenario_role: profile.scenario_role || profile.role || 'participant',
                },
            },
        };
        const next = cloneDraft(draft);
        next.init_config.agents = editingAgentId === null
            ? [...next.init_config.agents, agent]
            : next.init_config.agents.map((item) => item.agent_id === editingAgentId ? agent : item);
        const env = getEnvModule(next);
        env.kwargs.agent_id_name_pairs = next.init_config.agents.map((item) => [item.agent_id, agentName(item)]);
        env.kwargs.initial_locations = {
            ...(env.kwargs.initial_locations || {}),
            [String(agent.agent_id)]: env.kwargs.initial_locations?.[String(agent.agent_id)] || locationOptions[0]?.value || 'park',
        };
        setDraft(next);
        setAgentModalOpen(false);
    };

    const deleteAgent = (agentId: number) => {
        if (!draft) return;
        const next = cloneDraft(draft);
        next.init_config.agents = next.init_config.agents.filter((agent) => agent.agent_id !== agentId);
        const env = getEnvModule(next);
        env.kwargs.agent_id_name_pairs = next.init_config.agents.map((agent) => [agent.agent_id, agentName(agent)]);
        if (env.kwargs.initial_locations) {
            delete env.kwargs.initial_locations[String(agentId)];
        }
        setDraft(next);
    };

    const publishAndStart = async () => {
        if (!draft) return;
        const modelValues = await modelForm.validateFields();
        setPublishing(true);
        try {
            const result = await fetchJson<{
                hypothesis_id: string;
                experiment_id: string;
                workspace_path: string;
                warnings?: string[];
            }>('/api/v1/god/setup/publish', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    draft,
                    model_config: modelValues,
                    start_immediately: true,
                }),
            });
            messageApi.success('实验已保存，并已请求 GOD 启动。');
            setCurrentStep(4);
            window.setTimeout(() => {
                navigate(`/pixel-replay/${encodeURIComponent(result.hypothesis_id)}/${encodeURIComponent(result.experiment_id)}?workspace_path=${encodeURIComponent(result.workspace_path)}`);
            }, 1000);
        } catch (error) {
            messageApi.error(`保存并启动失败: ${error instanceof Error ? error.message : String(error)}`);
        } finally {
            setPublishing(false);
        }
    };

    const agentColumns: ColumnsType<AgentRecord> = [
        { title: 'ID', dataIndex: 'agent_id', width: 70 },
        { title: 'Name', render: (_, record) => agentName(record), width: 180 },
        {
            title: 'Role',
            render: (_, record) => String(record.kwargs?.profile?.role || record.kwargs?.profile?.scenario_role || '-'),
            width: 180,
        },
        {
            title: 'Initial location',
            width: 260,
            render: (_, record) => (
                <Select
                    value={getEnvModule(draft!).kwargs.initial_locations?.[String(record.agent_id)]}
                    options={locationOptions}
                    style={{ width: '100%' }}
                    onChange={(value) => updateInitialLocation(record.agent_id, value)}
                />
            ),
        },
        {
            title: 'Profile',
            render: (_, record) => (
                <Tooltip title={<pre className="setup-json-preview">{jsonStringify(record.kwargs?.profile)}</pre>}>
                    <Text code>{compactJson(record.kwargs?.profile)}</Text>
                </Tooltip>
            ),
        },
        {
            title: 'Actions',
            width: 104,
            render: (_, record) => (
                <Space size={6}>
                    <Button size="small" icon={<EditOutlined />} onClick={() => openAgentModal(record)} />
                    <Button size="small" danger icon={<DeleteOutlined />} onClick={() => deleteAgent(record.agent_id)} />
                </Space>
            ),
        },
    ];

    const renderModelStep = () => (
        <Card className="setup-card" title={<Space><ApiOutlined />模型与端口配置</Space>}>
            <Alert
                type="info"
                showIcon
                message="API key 只会保存到本地 .env；状态接口只返回脱敏结果，不会把明文 key 传回前端。"
                style={{ marginBottom: 18 }}
            />
            <Form form={modelForm} layout="vertical">
                <Row gutter={16}>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_LLM_API_KEY"
                            label={formLabel('API key', 'OpenAI-compatible 服务的密钥；留空表示沿用本地 .env 已保存的值。')}
                        >
                            <Input.Password placeholder={status?.model_config.GOD_LLM_API_KEY?.configured ? '已配置，留空不修改' : 'sk-...'} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_LLM_API_BASE"
                            label={formLabel('API base URL', 'OpenAI-compatible /v1 地址；用于草案生成、Agent 推理和后端 summary。')}
                            rules={[{ required: true }]}
                        >
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_LLM_MODEL"
                            label={formLabel('Model', '默认主模型名；也会同步给 JiuwenClaw runtime。')}
                            rules={[{ required: true }]}
                        >
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_EMBEDDING_API_KEY"
                            label={formLabel('Embedding key', '可选；留空时复用主 API key。')}
                        >
                            <Input.Password placeholder={status?.model_config.GOD_EMBEDDING_API_KEY?.configured ? '已配置，留空不修改' : 'optional'} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_EMBEDDING_API_BASE"
                            label={formLabel('Embedding base URL', '可选；留空时复用主 API base。')}
                        >
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_EMBEDDING_MODEL"
                            label={formLabel('Embedding model', '用于长期记忆/向量检索的 embedding 模型。')}
                        >
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item name="GOD_BACKEND_HOST" label={formLabel('Backend host', '后端绑定地址，本地默认 127.0.0.1。')}>
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={8}>
                        <Form.Item name="GOD_BACKEND_PORT" label={formLabel('Backend port', 'FastAPI 后端端口。')}>
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={8}>
                        <Form.Item name="GOD_FRONTEND_PORT" label={formLabel('Frontend port', 'GOD 控制台 Vite 端口。')}>
                            <Input />
                        </Form.Item>
                    </Col>
                </Row>
            </Form>
            <Space>
                <Button type="primary" icon={<SaveOutlined />} loading={savingModel} onClick={saveModelConfig}>
                    保存模型配置
                </Button>
                <Button
                    icon={<PlayCircleOutlined />}
                    loading={startingDefault}
                    disabled={status?.default_experiment?.config_exists === false}
                    onClick={startDefaultExperiment}
                >
                    直接运行默认实验
                </Button>
                <Tag>{status?.model_config.GOD_LLM_API_KEY?.configured ? 'API key configured' : 'API key missing'}</Tag>
                <Text type="secondary">{status?.env_file}</Text>
            </Space>
        </Card>
    );

    const renderBasicsStep = () => (
        <Card className="setup-card" title={<Space><ExperimentOutlined />实验基础参数</Space>}>
            <Alert
                type="warning"
                showIcon
                message="实验参数都是可选的；留空会使用默认 GOD Town 参数。当前版本不会生成新地图，会把设定映射到 The Ville 的已知地点。"
                style={{ marginBottom: 18 }}
            />
            <Form
                form={basicsForm}
                layout="vertical"
                initialValues={basicsValues}
                onValuesChange={(_, allValues) => {
                    syncBasicsValues({ ...basicsRef.current, ...allValues });
                }}
            >
                <Row gutter={16}>
                    <Col xs={24} lg={12}>
                        <Form.Item
                            name="title"
                            label={formLabel('实验标题', '用于生成目录、README、实验背景标题。默认：斯坦福监狱实验适配模拟。格式：短标题，后端会据此生成 hypothesis 目录名。')}
                        >
                            <Input placeholder="例如：斯坦福监狱实验适配模拟" />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={4}>
                        <Form.Item
                            name="agent_count"
                            label={formLabel('Agent 个数', 'GOD agent 会生成对应数量的角色、人设和初始位置。默认：10。格式：1-50 的整数。')}
                        >
                            <InputNumber min={1} max={50} placeholder="10" style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={4}>
                        <Form.Item
                            name="num_steps"
                            label={formLabel('初始 steps', 'steps.yaml 中默认 run step 数。默认：4。格式：1-100 的整数，表示初始 run 计划包含多少步。')}
                        >
                            <InputNumber min={1} max={100} placeholder="4" style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={4}>
                        <Form.Item
                            name="tick"
                            label={formLabel('Tick 秒数', '每个 step 推进的仿真秒数。默认：1800。格式：正整数秒，1800 表示每步推进 30 分钟。')}
                        >
                            <InputNumber min={1} placeholder="1800" style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="start_t"
                            label={formLabel('开始时间', 'ISO 时间，决定 agent 的日程判断。默认：2026-05-11T08:20:00+08:00。格式：ISO 8601，包含时区。')}
                        >
                            <Input placeholder="2026-05-11T08:20:00+08:00" />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={4}>
                        <Form.Item
                            name="movement_tiles_per_second"
                            label={formLabel('移动速度', 'PixelTownSocialEnv 每秒推进的 tile 数。默认：8。格式：正数，越大地图移动越快。')}
                        >
                            <InputNumber min={0.1} step={0.5} placeholder="8" style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={4}>
                        <Form.Item
                            name="movement_min_steps_per_trip"
                            label={formLabel('最短步数', '移动路径至少分几步完成，用于避免瞬移。默认：3。格式：正整数，越大越能拉长移动过程。')}
                        >
                            <InputNumber min={1} placeholder="3" style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="language"
                            label={formLabel('输出语言', '生成 agent profile 和 README 的主要语言。默认：中文。可选：中文 / English。')}
                        >
                            <Select options={[{ value: 'zh', label: '中文' }, { value: 'en', label: 'English' }]} />
                        </Form.Item>
                    </Col>
                    <Col span={24}>
                        <Form.Item
                            name="background"
                            label={formLabel('实验背景 / 设定', '格式：自然语言。建议写清角色、场景、观察目标、禁止行为。默认会生成一个安全版权力/角色压力模拟。')}
                        >
                            <Input.TextArea
                                rows={8}
                                placeholder="例如：模拟一个安全版斯坦福监狱实验。角色包括观察者、规则维护者、普通参与者；目标是观察权力分配、规则遵守、情绪变化和合作，不允许羞辱、伤害、威胁或强迫。"
                            />
                        </Form.Item>
                    </Col>
                </Row>
            </Form>
            <Space>
                <Button onClick={() => setCurrentStep(0)}>上一步</Button>
                <Button
                    type="primary"
                    onClick={async () => {
                        try {
                            await persistBasicsFromForm();
                            setCurrentStep(2);
                        } catch {
                            // Ant Design has already marked the invalid fields.
                        }
                    }}
                >
                    继续生成
                </Button>
            </Space>
        </Card>
    );

    const renderGenerateStep = () => (
        <Card className="setup-card" title={<Space><RobotOutlined />GOD agent 生成草案</Space>}>
            <div className="setup-generate-panel">
                <div>
                    <Title level={4}>生成完整实验草案</Title>
                    <Paragraph type="secondary">
                        GOD agent 会生成实验背景、伦理边界、agent profiles、初始位置、环境参数和 steps。生成后不会立刻启动，你可以继续编辑。
                    </Paragraph>
                    <Space wrap>
                        <Tag color="blue">The Ville map only</Tag>
                        <Tag color="green">可编辑 profiles</Tag>
                        <Tag color="purple">保存为新实验副本</Tag>
                    </Space>
                </div>
                <Button
                    type="primary"
                    size="large"
                    icon={<ThunderboltOutlined />}
                    loading={generating}
                    onClick={generateDraft}
                >
                    生成实验草案
                </Button>
            </div>
            <Divider />
            <Alert
                type="info"
                showIcon
                message="本次将用于生成的参数"
                description={(
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                        <Text>标题：{basicsValues.title}</Text>
                        <Text>Agent：{basicsValues.agent_count} 个；Steps：{basicsValues.num_steps}；Tick：{basicsValues.tick} 秒；开始时间：{basicsValues.start_t}</Text>
                        <Text>移动速度：{basicsValues.movement_tiles_per_second} tiles/s；最短步数：{basicsValues.movement_min_steps_per_trip}</Text>
                        <Paragraph style={{ marginBottom: 0 }}>背景：{basicsValues.background}</Paragraph>
                    </Space>
                )}
                style={{ marginBottom: 16 }}
            />
            <Space>
                <Button onClick={() => setCurrentStep(1)}>上一步</Button>
                <Button disabled={!draft} onClick={() => setCurrentStep(3)}>查看已有草案</Button>
            </Space>
        </Card>
    );

    const renderEditStep = () => {
        if (!draft) {
            return (
                <Card className="setup-card">
                    <Alert type="info" showIcon message="还没有草案，请先让 GOD agent 生成。" />
                </Card>
            );
        }
        const env = getEnvModule(draft);
        return (
            <Card className="setup-card" title={<Space><EditOutlined />编辑草案</Space>}>
                {draft.warnings?.length > 0 && (
                    <Alert
                        type="warning"
                        showIcon
                        message="地图适配提示"
                        description={draft.warnings.join(' ')}
                        style={{ marginBottom: 16 }}
                    />
                )}
                <Tabs
                    items={[
                        {
                            key: 'context',
                            label: '实验背景',
                            children: (
                                <Space direction="vertical" style={{ width: '100%' }}>
                                    <Alert
                                        type="info"
                                        showIcon
                                        message="当前旧实验没有独立 scenario 字段；这里会保存为 init/experiment_context.json，并同步注入每个 agent profile 与 prompt。"
                                    />
                                    <Input.TextArea
                                        rows={16}
                                        defaultValue={jsonStringify(draft.experiment_context)}
                                        spellCheck={false}
                                        onBlur={(event) => updateContextJson(event.target.value)}
                                    />
                                </Space>
                            ),
                        },
                        {
                            key: 'agents',
                            label: `Agents (${draft.init_config.agents.length})`,
                            children: (
                                <>
                                    <Space style={{ marginBottom: 12 }}>
                                        <Button type="primary" icon={<UserAddOutlined />} onClick={() => openAgentModal()}>
                                            Add Agent
                                        </Button>
                                    </Space>
                                    <Table
                                        rowKey="agent_id"
                                        columns={agentColumns}
                                        dataSource={draft.init_config.agents}
                                        pagination={{ pageSize: 8 }}
                                    />
                                </>
                            ),
                        },
                        {
                            key: 'env',
                            label: '环境参数',
                            children: (
                                <Row gutter={16}>
                                    <Col xs={24} lg={8}>
                                        <Text strong>群聊名称</Text>
                                        <Input
                                            value={env.kwargs.default_group_name}
                                            onChange={(event) => updateEnvField('default_group_name', event.target.value)}
                                            style={{ marginTop: 8 }}
                                        />
                                    </Col>
                                    <Col xs={12} lg={8}>
                                        <Text strong>移动速度</Text>
                                        <InputNumber
                                            value={env.kwargs.movement_tiles_per_second}
                                            min={0.1}
                                            step={0.5}
                                            onChange={(value) => updateEnvField('movement_tiles_per_second', value)}
                                            style={{ width: '100%', marginTop: 8 }}
                                        />
                                    </Col>
                                    <Col xs={12} lg={8}>
                                        <Text strong>最短步数</Text>
                                        <InputNumber
                                            value={env.kwargs.movement_min_steps_per_trip}
                                            min={1}
                                            onChange={(value) => updateEnvField('movement_min_steps_per_trip', value)}
                                            style={{ width: '100%', marginTop: 8 }}
                                        />
                                    </Col>
                                </Row>
                            ),
                        },
                        {
                            key: 'steps',
                            label: 'Steps',
                            children: (
                                <Input.TextArea
                                    rows={16}
                                    defaultValue={jsonStringify(draft.steps)}
                                    spellCheck={false}
                                    onBlur={(event) => updateStepsJson(event.target.value)}
                                />
                            ),
                        },
                    ]}
                />
                <Divider />
                <Space>
                    <Button onClick={() => setCurrentStep(2)}>返回生成</Button>
                    <Button type="primary" onClick={() => setCurrentStep(4)}>确认启动</Button>
                </Space>
            </Card>
        );
    };

    const renderConfirmStep = () => (
        <Card className="setup-card" title={<Space><CheckCircleOutlined />保存并启动</Space>}>
            {draft ? (
                <>
                    <div className="setup-confirm-grid">
                        <div>
                            <Text type="secondary">实验标题</Text>
                            <Title level={4}>{String(draft.experiment_context.title || 'Custom GOD Experiment')}</Title>
                        </div>
                        <div>
                            <Text type="secondary">Agent 数量</Text>
                            <Title level={4}>{draft.init_config.agents.length}</Title>
                        </div>
                        <div>
                            <Text type="secondary">Workspace</Text>
                            <Paragraph copyable>{status?.workspace_path}</Paragraph>
                        </div>
                    </div>
                    <Alert
                        type="success"
                        showIcon
                        message="不会覆盖默认 GOD Town"
                        description="发布会写入新的 hypothesis_<slug>/experiment_1，并更新 .env 与 .god/current_experiment.json。"
                        style={{ marginBottom: 16 }}
                    />
                    <Space>
                        <Button onClick={() => setCurrentStep(3)}>继续编辑</Button>
                        <Button
                            type="primary"
                            icon={<PlayCircleOutlined />}
                            loading={publishing}
                            onClick={publishAndStart}
                        >
                            保存并启动
                        </Button>
                    </Space>
                </>
            ) : (
                <Alert type="info" showIcon message="还没有可发布的草案。" />
            )}
        </Card>
    );

    const stepItems = [
        { title: '模型', icon: <ApiOutlined /> },
        { title: '参数', icon: <ExperimentOutlined /> },
        { title: '生成', icon: <RobotOutlined /> },
        { title: '编辑', icon: <EditOutlined /> },
        { title: '启动', icon: <PlayCircleOutlined /> },
    ];

    const content = [
        renderModelStep,
        renderBasicsStep,
        renderGenerateStep,
        renderEditStep,
        renderConfirmStep,
    ][currentStep]();

    return (
        <div className="setup-page">
            {messageContextHolder}
            {currentStep !== 1 && <Form form={basicsForm} component={false} />}
            <div className="setup-shell">
                <div className="setup-header">
                    <div>
                        <Title level={2}>GOD 实验初始化</Title>
                        <Text type="secondary">
                            配置模型、生成实验设定、编辑 agent profiles，然后启动一个新的 live experiment。
                        </Text>
                    </div>
                    <Space>
                        {status?.current_experiment?.hypothesis_id && (
                            <Button onClick={() => navigate(`/pixel-replay/${status.current_experiment?.hypothesis_id}/${status.current_experiment?.experiment_id || '1'}?workspace_path=${encodeURIComponent(status.current_experiment?.workspace_path || status.workspace_path)}`)}>
                                打开当前实验
                            </Button>
                        )}
                        <Button onClick={loadStatus} loading={loadingStatus}>刷新状态</Button>
                    </Space>
                </div>
                <Card className="setup-step-card" variant="borderless">
                    <Steps current={currentStep} items={stepItems} onChange={(nextStep) => { void goToStep(nextStep); }} />
                </Card>
                {content}
            </div>
            <AgentEditorModal
                open={agentModalOpen}
                editingAgentId={editingAgentId}
                form={agentForm}
                width={820}
                minAgentId={1}
                onSave={saveAgent}
                onCancel={() => setAgentModalOpen(false)}
            />
        </div>
    );
}
