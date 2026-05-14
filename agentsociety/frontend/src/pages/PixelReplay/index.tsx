import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Phaser from 'phaser';
import {
    Alert,
    Button,
    Card,
    Drawer,
    Empty,
    message,
    Mentions,
    Segmented,
    Select,
    Space,
    Spin,
    Tag,
    Tooltip,
    Typography,
} from 'antd';
import {
    AimOutlined,
    CaretRightOutlined,
    PauseOutlined,
    SendOutlined,
    SettingOutlined,
    StepBackwardOutlined,
    StepForwardOutlined,
    ThunderboltOutlined,
    UserAddOutlined,
    ZoomInOutlined,
    ZoomOutOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { fetchCustom } from '../../components/fetch';
import { AgentBuilderPanel } from '../AgentBuilder';
import './style.css';

const { Text, Title } = Typography;

const TILE_SIZE = 32;
const CHARACTER_ROOT = '/pixel-town/characters';
const DEFAULT_HYPOTHESIS_ID = import.meta.env.VITE_DEFAULT_REPLAY_HYPOTHESIS_ID ?? 'god_town';
const DEFAULT_EXPERIMENT_ID = import.meta.env.VITE_DEFAULT_REPLAY_EXPERIMENT_ID ?? '1';
const DEFAULT_WORKSPACE_PATH = import.meta.env.VITE_REPLAY_WORKSPACE_PATH ?? '';
const INITIAL_REPLAY_READY_TIMEOUT_MS = 60_000;
const INITIAL_REPLAY_RETRY_INTERVAL_MS = 1500;
const HIDDEN_TILE_LAYER_NAMES = new Set([
    'AgentSociety Scene Footprints',
    'Collisions',
    'Object Interaction Blocks',
    'Arena Blocks',
    'Sector Blocks',
    'World Blocks',
    'Spawning Blocks',
    'Special Blocks Registry',
]);

const CHARACTER_NAMES = [
    'Isabella_Rodriguez',
    'Maria_Lopez',
    'Klaus_Mueller',
    'Sam_Moore',
    'Yuriko_Yamamoto',
    'Ryan_Park',
    'Abigail_Chen',
    'Eddy_Lin',
    'Mei_Lin',
    'Rajiv_Patel',
    'Ayesha_Khan',
    'Giorgio_Rossi',
    'Tamara_Taylor',
    'Wolfgang_Schulz',
    'John_Lin',
    'Jennifer_Moore',
    'Carlos_Gomez',
    'Francisco_Lopez',
    'Adam_Smith',
    'Carmen_Ortiz',
    'Jane_Moreno',
    'Tom_Moreno',
    'Latoya_Williams',
    'Arthur_Burton',
    'Hailey_Johnson',
];

type AgentProfile = {
    id: number;
    name?: string;
    profile?: Record<string, unknown>;
};

type TokenUsage = {
    call_count: number;
    input_tokens: number;
    output_tokens: number;
};

type AgentRuntimeState = {
    agent_id: number;
    work_dir?: string | null;
    agent_config?: Record<string, unknown>;
    session_state?: Record<string, unknown>;
    agent_state_snapshot?: Record<string, unknown>;
    token_usage?: Record<string, TokenUsage>;
    state_files?: Record<string, unknown>;
    recent_messages?: Record<string, unknown>[];
    recent_tool_calls?: Record<string, unknown>[];
    recent_step_replays?: Record<string, unknown>[];
    compact_state?: Record<string, unknown>;
    agent_markdown?: string | null;
};

type TimelinePoint = {
    step: number;
    t: string;
};

type ReplayInfo = {
    hypothesis_id: string;
    experiment_id: string;
    total_steps: number;
    agent_count: number;
};

type ReplayMapTileset = {
    name: string;
    image_url: string;
};

type ReplayMapLocation = {
    id: string;
    name: string;
    aliases: string[];
    anchor_tile: Tile;
    scene_type?: string;
    bounds?: { x: number; y: number; w: number; h: number };
    interaction_ids: string[];
    visual_asset_url?: string;
    visual_note?: string;
};

type ReplayMapInteraction = {
    id: string;
    name: string;
    description?: string;
    allowed_location_ids: string[];
};

type ReplayMapInfo = {
    map_id: string;
    display_name: string;
    tile_size: number;
    width: number;
    height: number;
    tiled_map_url: string;
    tilesets: ReplayMapTileset[];
    locations: ReplayMapLocation[];
    interactions: ReplayMapInteraction[];
};

type ReplayStepBundle = {
    step: number;
    t?: string | null;
    agent_state_rows?: Record<string, {
        rows_by_agent_id?: Record<string, Record<string, unknown>>;
    }>;
    env_state_rows?: Record<string, {
        row?: Record<string, unknown> | null;
    }>;
};

type LiveStatusValue = 'initializing'
    | 'waiting'
    | 'running_step'
    | 'asking'
    | 'intervening'
    | 'auto'
    | 'stopped'
    | 'failed';

type LiveStatus = {
    hypothesis_id: string;
    experiment_id: string;
    workspace_path: string;
    status: LiveStatusValue;
    step_count: number;
    simulation_time?: string | null;
    auto_running: boolean;
    default_tick: number;
    current_command?: string | null;
    error?: string | null;
};

type LiveEvent = {
    type: string;
    command?: {
        type: 'ask' | 'intervene';
        result?: string;
        artifact_name?: string;
        target?: AskTarget;
    };
    status?: LiveStatus;
    message?: string;
    result?: string;
    artifact_name?: string;
};

type AskTargetType = 'society' | 'agent' | 'agents' | 'all_agents';

type AskTarget = {
    type: AskTargetType;
    agent_id?: number;
    agent_ids?: number[];
};

type LiveTargetMention = {
    value: string;
    label: string;
    target: AskTarget;
};

type LiveInteraction = {
    id: string;
    type: 'ask' | 'intervene';
    prompt: string;
    result?: string;
    artifactName?: string;
    targetLabel?: string;
};

type Tile = {
    x: number;
    y: number;
};

type WalkableMap = {
    mapId: string;
    displayName: string;
    tileSize: number;
    tiledMapUrl: string;
    tilesets: ReplayMapTileset[];
    locations: ReplayMapLocation[];
    interactions: ReplayMapInteraction[];
    width: number;
    height: number;
    walkable: Tile[];
    walkableKeys: Set<string>;
};

type AgentMessage = {
    type?: string;
    sender_id?: number;
    sender_name?: string;
    receiver_id?: number;
    receiver_name?: string;
    group_id?: number;
    group_name?: string;
    recipient_count?: number;
    content?: string;
    timestamp?: string;
};

type PixelAgent = {
    id: number;
    name: string;
    spriteKey: string;
    tile: Tile;
    action: string;
    status?: string;
    location: string;
    locationId?: string;
    movementStatus?: string;
    targetLocationId?: string;
    hasReplayTile: boolean;
    emotion?: string;
    lastMessage?: string;
    messageCount: number;
    currentPhase?: string;
    latestEvent?: string;
    sentMessages: AgentMessage[];
    stepCommunications: Communication[];
    availableInteractions: ReplayMapInteraction[];
};

type PixelFrame = {
    step: number;
    t?: string | null;
    map: WalkableMap;
    agents: PixelAgent[];
};

type AgentHoverState = {
    agentId: number;
    x: number;
    y: number;
};

type AgentScreenPosition = {
    x: number;
    y: number;
};

type CanvasSize = {
    width: number;
    height: number;
};

type PhaserBridge = {
    scene?: Phaser.Scene;
    mapWidthPixels?: number;
    mapHeightPixels?: number;
    sprites: Map<number, Phaser.GameObjects.Sprite>;
    labels: Map<number, Phaser.GameObjects.Text>;
    hitZones: Map<number, Phaser.GameObjects.Zone>;
    locationMarkers?: Phaser.GameObjects.GameObject[];
    selectedId?: number;
};

type Communication = {
    type?: string;
    sender_id?: number;
    sender_name?: string;
    receiver_id?: number;
    receiver_name?: string;
    group_id?: number;
    group_name?: string;
    recipient_count?: number;
    content?: string;
};

const PHASE_LABELS: Record<string, string> = {
    opening: '开场协调',
    mapping: '路线梳理',
    inventory: '物资清点',
    risk_review: '风险评估',
    route_choice: '路线决策',
    assignments: '任务分配',
    field_check: '现场检查',
    adjustment: '方案调整',
    broadcast: '公开通知',
    confirmation: '确认准备',
    final_walkthrough: '最终走查',
    wrap_up: '收尾归档',
};

function formatPhase(value: unknown): string {
    if (typeof value !== 'string' || value.trim() === '') {
        return '暂无阶段';
    }
    return PHASE_LABELS[value] ?? value;
}

function stableHash(input: string): number {
    let hash = 2166136261;
    for (let i = 0; i < input.length; i += 1) {
        hash ^= input.charCodeAt(i);
        hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
}

function tileKey(tile: Tile): string {
    return `${tile.x},${tile.y}`;
}

function getAgentName(profile: AgentProfile): string {
    if (profile.name && profile.name.trim() !== '') {
        return profile.name;
    }
    const profileName = profile.profile?.name;
    return typeof profileName === 'string' && profileName.trim() !== ''
        ? profileName
        : `Agent_${profile.id}`;
}

function getAgentOptionLabel(profile: AgentProfile): string {
    return `${getAgentName(profile)} · #${profile.id}`;
}

function describeAskTarget(target: AskTarget, profiles: AgentProfile[]): string {
    const byId = new Map(profiles.map((profile) => [profile.id, profile]));
    if (target.type === 'society') {
        return '问系统';
    }
    if (target.type === 'all_agents') {
        return `问所有居民（${profiles.length} 个）`;
    }
    const ids = target.type === 'agent'
        ? (target.agent_id === undefined ? [] : [target.agent_id])
        : target.agent_ids ?? [];
    if (ids.length === 0) {
        return '未选择居民';
    }
    return ids
        .map((id) => {
            const profile = byId.get(id);
            return profile ? getAgentOptionLabel(profile) : `Agent #${id}`;
        })
        .join('，');
}

function describeInteractionTarget(
    target: AskTarget,
    profiles: AgentProfile[],
    mode: 'ask' | 'intervene',
): string {
    const label = describeAskTarget(target, profiles);
    return mode === 'intervene' ? label.replace(/^问/, '干预') : label;
}

function escapeRegExp(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function mentionPattern(value: string, flags = ''): RegExp {
    return new RegExp(`@${escapeRegExp(value)}(?=\\s|$|[，。,.!?；;])`, flags);
}

function stripTargetMentions(text: string, mentions: LiveTargetMention[]): string {
    return mentions.reduce((current, mention) => (
        current.replace(mentionPattern(mention.value, 'g'), '')
    ), text).replace(/\s+/g, ' ').trim();
}

function resolveTargetFromPrompt(
    text: string,
    mentions: LiveTargetMention[],
    fallback: AskTarget,
): AskTarget {
    const selected = mentions.filter((mention) => (
        mentionPattern(mention.value).test(text)
    ));
    const systemTarget = selected.find((mention) => mention.target.type === 'society');
    if (systemTarget) {
        return { type: 'society' };
    }
    const allTarget = selected.find((mention) => mention.target.type === 'all_agents');
    if (allTarget) {
        return { type: 'all_agents' };
    }
    const agentIds = selected
        .map((mention) => mention.target.agent_id)
        .filter((agentId): agentId is number => typeof agentId === 'number');
    const uniqueAgentIds = Array.from(new Set(agentIds));
    if (uniqueAgentIds.length === 1) {
        return { type: 'agent', agent_id: uniqueAgentIds[0] };
    }
    if (uniqueAgentIds.length > 1) {
        return { type: 'agents', agent_ids: uniqueAgentIds };
    }
    return fallback;
}

function pickDisplayValue(row: Record<string, unknown>, keys: string[]): string | undefined {
    for (const key of keys) {
        const value = row[key];
        if (typeof value === 'string' && value.trim() !== '') {
            return value;
        }
        if (typeof value === 'number' || typeof value === 'boolean') {
            return String(value);
        }
        if (value && typeof value === 'object') {
            return JSON.stringify(value);
        }
    }
    return undefined;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
        return value as Record<string, unknown>;
    }
    return undefined;
}

function formatValue(value: unknown): string {
    if (value === undefined || value === null || value === '') {
        return '暂无';
    }
    return typeof value === 'string'
        ? value
        : typeof value === 'number' || typeof value === 'boolean'
            ? String(value)
            : JSON.stringify(value, null, 2);
}

function formatInlineFields(data: Record<string, unknown> | undefined, emptyText = '暂无数据'): string {
    if (!data || Object.keys(data).length === 0) {
        return emptyText;
    }
    const entries = Object.entries(data).filter(([, value]) => value !== undefined && value !== null && value !== '');
    if (entries.length === 0) {
        return emptyText;
    }
    return entries
        .map(([key, value]) => `${key}: ${formatValue(value)}`)
        .join('\n');
}

function formatTokenUsage(tokenUsage: Record<string, TokenUsage> | undefined): string {
    if (!tokenUsage || Object.keys(tokenUsage).length === 0) {
        return '未记录 token 消耗。需要新版本运行写入 session_state，或 run/output.log 中包含 token usage 日志。';
    }
    return Object.entries(tokenUsage)
        .map(([model, usage]) => (
            `${model}: 调用 ${usage.call_count}，输入 ${usage.input_tokens}，输出 ${usage.output_tokens}，总计 ${usage.input_tokens + usage.output_tokens}`
        ))
        .join('；');
}

function joinDetailBlocks(blocks: Array<[string, string]>): string {
    return blocks
        .map(([label, value]) => `${label}:\n${value}`)
        .join('\n\n');
}

function renderPlainDetail(label: string, value: string) {
    return (
        <div className="pixel-agent-detail-line">
            <Text strong className="pixel-agent-detail-label">{label}</Text>
            <Text className="pixel-agent-detail-text">{value}</Text>
        </div>
    );
}

function buildAgentSummary(agent: PixelAgent | undefined): Record<string, unknown> | undefined {
    if (!agent) {
        return undefined;
    }
    return {
        action: agent.action,
        status: agent.status,
        location: agent.location,
        location_id: agent.locationId,
        movement_status: agent.movementStatus,
        target_location_id: agent.targetLocationId,
        tile: `(${agent.tile.x}, ${agent.tile.y})`,
        emotion: agent.emotion,
        last_message: agent.lastMessage,
        message_count: agent.messageCount,
        current_phase: agent.currentPhase,
        latest_event: agent.latestEvent,
    };
}

function pickNumberValue(row: Record<string, unknown> | undefined, key: string): number {
    const value = row?.[key];
    if (typeof value === 'number') {
        return value;
    }
    if (typeof value === 'string') {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    }
    return 0;
}

function pickOptionalNumberValue(row: Record<string, unknown> | undefined, key: string): number | undefined {
    const value = row?.[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === 'string') {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : undefined;
    }
    return undefined;
}

function parseInteractionList(value: unknown): ReplayMapInteraction[] {
    if (Array.isArray(value)) {
        return value.filter((item): item is ReplayMapInteraction => (
            Boolean(item)
            && typeof item === 'object'
            && typeof (item as ReplayMapInteraction).id === 'string'
        ));
    }
    if (typeof value !== 'string' || value.trim() === '') {
        return [];
    }
    try {
        const parsed = JSON.parse(value);
        return parseInteractionList(parsed);
    } catch {
        return [];
    }
}

function normalizeAgentId(value: unknown): number | undefined {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === 'string') {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : undefined;
    }
    return undefined;
}

function normalizeAgentMessage(value: unknown): AgentMessage | undefined {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        return undefined;
    }
    const row = value as Record<string, unknown>;
    const content = pickDisplayValue(row, ['content', 'message', 'text']);
    if (!content) {
        return undefined;
    }
    return {
        type: pickDisplayValue(row, ['type', 'message_type']),
        sender_id: normalizeAgentId(row.sender_id),
        sender_name: pickDisplayValue(row, ['sender_name']),
        receiver_id: normalizeAgentId(row.receiver_id),
        receiver_name: pickDisplayValue(row, ['receiver_name']),
        group_id: normalizeAgentId(row.group_id),
        group_name: pickDisplayValue(row, ['group_name']),
        recipient_count: normalizeAgentId(row.recipient_count),
        content,
        timestamp: pickDisplayValue(row, ['timestamp', 't', 'time']),
    };
}

function parseAgentMessages(value: unknown): AgentMessage[] {
    if (Array.isArray(value)) {
        return value
            .map(normalizeAgentMessage)
            .filter((item): item is AgentMessage => Boolean(item));
    }
    if (typeof value !== 'string' || value.trim() === '') {
        return [];
    }
    try {
        return parseAgentMessages(JSON.parse(value));
    } catch {
        return [];
    }
}

function firstEnvRow(bundle: ReplayStepBundle | undefined): Record<string, unknown> | undefined {
    const datasets = bundle?.env_state_rows ?? {};
    for (const dataset of Object.values(datasets)) {
        if (dataset.row) {
            return dataset.row;
        }
    }
    return undefined;
}

function parseCommunications(row: Record<string, unknown> | undefined): Communication[] {
    const raw = row?.latest_communications;
    if (typeof raw !== 'string' || raw.trim() === '') {
        return [];
    }
    try {
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) {
            return [];
        }
        return parsed
            .slice(0, 8)
            .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
            .map((item) => ({
                type: pickDisplayValue(item, ['type', 'message_type']),
                sender_id: normalizeAgentId(item.sender_id),
                sender_name: pickDisplayValue(item, ['sender_name']),
                receiver_id: normalizeAgentId(item.receiver_id),
                receiver_name: pickDisplayValue(item, ['receiver_name']),
                group_id: normalizeAgentId(item.group_id),
                group_name: pickDisplayValue(item, ['group_name']),
                recipient_count: normalizeAgentId(item.recipient_count),
                content: pickDisplayValue(item, ['content', 'message', 'text']),
            }));
    } catch {
        return [];
    }
}

function filterAgentSentMessages(agentId: number, messages: AgentMessage[]): AgentMessage[] {
    return messages.filter((item) => item.sender_id === agentId).slice(-3);
}

function filterAgentStepCommunications(agentId: number, communications: Communication[]): Communication[] {
    return communications.filter((item) => item.sender_id === agentId).slice(0, 3);
}

function findAgentRow(bundle: ReplayStepBundle | undefined, agentId: number): Record<string, unknown> | undefined {
    const datasets = bundle?.agent_state_rows ?? {};
    for (const dataset of Object.values(datasets)) {
        const row = dataset.rows_by_agent_id?.[String(agentId)];
        if (row) {
            return row;
        }
    }
    return undefined;
}

function nextWalkableTile(current: Tile, agentId: number, step: number, walkableKeys: Set<string>): Tile {
    const moves = [
        { x: 0, y: 0 },
        { x: 1, y: 0 },
        { x: -1, y: 0 },
        { x: 0, y: 1 },
        { x: 0, y: -1 },
    ];
    const offset = stableHash(`${agentId}:${step}`) % moves.length;
    for (let i = 0; i < moves.length; i += 1) {
        const move = moves[(offset + i) % moves.length];
        const candidate = { x: current.x + move.x, y: current.y + move.y };
        if (walkableKeys.has(tileKey(candidate))) {
            return candidate;
        }
    }
    return current;
}

function getAutoTile(agentId: number, step: number, walkableMap: WalkableMap): Tile {
    if (walkableMap.walkable.length === 0) {
        return { x: 1, y: 1 };
    }
    let tile = walkableMap.walkable[stableHash(String(agentId)) % walkableMap.walkable.length];
    for (let i = 1; i <= step; i += 1) {
        tile = nextWalkableTile(tile, agentId, i, walkableMap.walkableKeys);
    }
    return tile;
}

function buildPixelFrame(
    profiles: AgentProfile[],
    bundle: ReplayStepBundle | undefined,
    step: number,
    walkableMap: WalkableMap,
): PixelFrame {
    const envRow = firstEnvRow(bundle);
    const stepCommunications = parseCommunications(envRow);
    return {
        step,
        t: bundle?.t,
        map: walkableMap,
        agents: profiles.map((profile, index) => {
            const row = findAgentRow(bundle, profile.id);
            const rawDescription = row ? pickDisplayValue(row, ['description', 'action', 'activity', 'state', 'status']) : undefined;
            const status = row ? pickDisplayValue(row, ['status']) : undefined;
            const location = row ? pickDisplayValue(row, ['location', 'target_address', 'place', 'address']) : undefined;
            const lastMessage = row ? pickDisplayValue(row, ['last_message']) : undefined;
            const emotion = row ? pickDisplayValue(row, ['emotion']) : undefined;
            const currentPhase = row ? pickDisplayValue(row, ['current_phase']) : undefined;
            const latestEvent = row ? pickDisplayValue(row, ['latest_event']) : undefined;
            const tileX = pickOptionalNumberValue(row, 'tile_x');
            const tileY = pickOptionalNumberValue(row, 'tile_y');
            const hasReplayTile = tileX !== undefined && tileY !== undefined;
            const fallbackTile = getAutoTile(profile.id, step, walkableMap);
            const sentMessages = row
                ? filterAgentSentMessages(profile.id, parseAgentMessages(row.recent_messages))
                : [];
            const availableInteractions = row
                ? parseInteractionList(row.available_interactions_json)
                : [];
            return {
                id: profile.id,
                name: getAgentName(profile),
                spriteKey: CHARACTER_NAMES[index % CHARACTER_NAMES.length],
                tile: hasReplayTile ? { x: tileX, y: tileY } : fallbackTile,
                action: rawDescription ?? 'idle',
                status,
                location: location ?? '小镇',
                locationId: row ? pickDisplayValue(row, ['location_id']) : undefined,
                movementStatus: row ? pickDisplayValue(row, ['movement_status']) : undefined,
                targetLocationId: row ? pickDisplayValue(row, ['target_location_id']) : undefined,
                hasReplayTile,
                emotion,
                lastMessage,
                messageCount: pickNumberValue(row, 'message_count'),
                currentPhase: currentPhase ?? pickDisplayValue(envRow ?? {}, ['current_phase']),
                latestEvent: latestEvent ?? pickDisplayValue(envRow ?? {}, ['latest_event']),
                sentMessages,
                stepCommunications: filterAgentStepCommunications(profile.id, stepCommunications),
                availableInteractions,
            };
        }),
    };
}

async function fetchJson<T>(url: string): Promise<T> {
    const response = await fetchCustom(url);
    if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}: ${await response.text()}`);
    }
    return response.json();
}

async function postJson<T>(url: string, body: Record<string, unknown> = {}): Promise<T> {
    const response = await fetchCustom(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}: ${await response.text()}`);
    }
    return response.json();
}

const sleep = (ms: number) => new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
});

const toErrorMessage = (error: unknown) => (error instanceof Error ? error.message : String(error));

async function waitForInitialReplay<T>(
    operation: () => Promise<T>,
    onRetry: (error: unknown, attempt: number) => void,
    shouldCancel: () => boolean,
): Promise<T> {
    const deadline = Date.now() + INITIAL_REPLAY_READY_TIMEOUT_MS;
    let attempt = 0;
    let lastError: unknown;
    while (!shouldCancel()) {
        try {
            return await operation();
        } catch (error) {
            lastError = error;
            if (Date.now() >= deadline) {
                break;
            }
            attempt += 1;
            onRetry(error, attempt);
            await sleep(INITIAL_REPLAY_RETRY_INTERVAL_MS);
        }
    }
    throw lastError ?? new Error('Replay loading was cancelled');
}

async function loadWalkableMap(mapInfo: ReplayMapInfo): Promise<WalkableMap> {
    const response = await fetchCustom(mapInfo.tiled_map_url);
    if (!response.ok) {
        throw new Error(`小镇地图加载失败：${response.status} ${response.statusText}`);
    }
    const map = await response.json() as {
        width: number;
        height: number;
        layers?: Array<{
            name?: string;
            data?: number[];
        }>;
    };
    const collisions = map.layers?.find((layer) => layer.name === 'Collisions');
    if (!collisions?.data) {
        throw new Error('小镇地图缺少 Collisions 图层。');
    }
    const width = Number(map.width);
    const height = Number(map.height);
    const walkable: Tile[] = [];
    collisions.data.forEach((gid: number, index: number) => {
        if (gid === 0) {
            walkable.push({ x: index % width, y: Math.floor(index / width) });
        }
    });
    return {
        mapId: mapInfo.map_id,
        displayName: mapInfo.display_name,
        tileSize: mapInfo.tile_size || TILE_SIZE,
        tiledMapUrl: mapInfo.tiled_map_url,
        tilesets: mapInfo.tilesets,
        locations: mapInfo.locations,
        interactions: mapInfo.interactions,
        width,
        height,
        walkable,
        walkableKeys: new Set(walkable.map(tileKey)),
    };
}

function formatTime(value?: string | null): string {
    if (!value) {
        return '-';
    }
    return value.replace('T', ' ').replace(/\.\d+$/, '');
}

function fitCameraToMap(scene: Phaser.Scene, bridge: PhaserBridge) {
    const camera = scene.cameras.main;
    const mapWidth = bridge.mapWidthPixels;
    const mapHeight = bridge.mapHeightPixels;
    if (!mapWidth || !mapHeight) {
        return;
    }
    const nextZoom = Phaser.Math.Clamp(
        Math.min(camera.width / mapWidth, camera.height / mapHeight) * 0.88,
        0.16,
        0.92,
    );
    camera.setZoom(nextZoom);
    camera.centerOn(mapWidth / 2, mapHeight / 2);
}

function zoomCameraAtCenter(scene: Phaser.Scene, delta: number) {
    const camera = scene.cameras.main;
    const centerX = camera.width / 2;
    const centerY = camera.height / 2;
    const before = camera.getWorldPoint(centerX, centerY);
    const nextZoom = Phaser.Math.Clamp(camera.zoom + delta, 0.16, 1.8);
    camera.setZoom(nextZoom);
    const after = camera.getWorldPoint(centerX, centerY);
    camera.scrollX += before.x - after.x;
    camera.scrollY += before.y - after.y;
}

function getFitScreenPosition(agent: PixelAgent, map: WalkableMap, canvasSize: CanvasSize): AgentScreenPosition | undefined {
    if (canvasSize.width <= 0 || canvasSize.height <= 0) {
        return undefined;
    }
    const tileSize = map.tileSize || TILE_SIZE;
    const mapWidth = map.width * tileSize;
    const mapHeight = map.height * tileSize;
    if (mapWidth <= 0 || mapHeight <= 0) {
        return undefined;
    }
    const zoom = Phaser.Math.Clamp(
        Math.min(canvasSize.width / mapWidth, canvasSize.height / mapHeight) * 0.88,
        0.16,
        0.92,
    );
    const scrollX = mapWidth / 2 - canvasSize.width / (2 * zoom);
    const scrollY = mapHeight / 2 - canvasSize.height / (2 * zoom);
    const worldX = agent.tile.x * tileSize + tileSize / 2;
    const worldY = agent.tile.y * tileSize + tileSize / 2;
    return {
        x: (worldX - scrollX) * zoom,
        y: (worldY - scrollY) * zoom,
    };
}

function formatSentMessageTarget(item: AgentMessage | Communication): string {
    if (item.type === 'direct') {
        return `发给 ${item.receiver_name ?? `Agent ${item.receiver_id ?? ''}`.trim()}`;
    }
    if (item.type === 'group') {
        return `发到 ${item.group_name ?? '群组'}${item.recipient_count ? `（${item.recipient_count} 人）` : ''}`;
    }
    if (item.type === 'system_event') {
        return '发布系统事件';
    }
    return item.type ?? '发出消息';
}

function PixelAgentHoverCard({
    agent,
    frame,
}: {
    agent: PixelAgent;
    frame: PixelFrame;
}) {
    const outgoingItems = agent.stepCommunications.length > 0
        ? agent.stepCommunications
        : agent.sentMessages;
    const hasOutgoingItems = outgoingItems.length > 0;

    return (
        <div className="pixel-agent-hover-card">
            <div className="pixel-agent-hover-header">
                <div className="pixel-agent-hover-title">
                    <Text strong>{agent.name}</Text>
                    <Text type="secondary">#{agent.id} · 第 {frame.step + 1} 步</Text>
                </div>
                <Tag className="pixel-agent-hover-status" color={agent.movementStatus === 'moving' ? 'blue' : 'green'}>
                    {agent.movementStatus ?? agent.status ?? 'idle'}
                </Tag>
            </div>

            <div className="pixel-agent-hover-grid">
                <Text type="secondary">时间</Text>
                <Text>{formatTime(frame.t)}</Text>
                <Text type="secondary">动作</Text>
                <Text>{agent.action}</Text>
                <Text type="secondary">位置</Text>
                <Text>
                    {agent.location}
                    {agent.locationId ? ` · ${agent.locationId}` : ''}
                </Text>
                {agent.targetLocationId && (
                    <>
                        <Text type="secondary">目标</Text>
                        <Text>{agent.targetLocationId}</Text>
                    </>
                )}
                {agent.emotion && (
                    <>
                        <Text type="secondary">情绪</Text>
                        <Text>{agent.emotion}</Text>
                    </>
                )}
                {agent.currentPhase && (
                    <>
                        <Text type="secondary">阶段</Text>
                        <Text>{formatPhase(agent.currentPhase)}</Text>
                    </>
                )}
                {agent.latestEvent && (
                    <>
                        <Text type="secondary">事件</Text>
                        <Text className="pixel-agent-hover-text">{agent.latestEvent}</Text>
                    </>
                )}
                <Text type="secondary">交互</Text>
                {agent.availableInteractions.length === 0 ? (
                    <Text className="pixel-agent-hover-muted">暂无可交互动作</Text>
                ) : (
                    <div className="pixel-agent-hover-tags">
                        {agent.availableInteractions.slice(0, 4).map((interaction) => (
                            <Tag color="cyan" key={interaction.id}>{interaction.name}</Tag>
                        ))}
                    </div>
                )}
                <Text type="secondary">
                    {agent.stepCommunications.length > 0 ? '本步发言' : '最近发言'}
                </Text>
                {!hasOutgoingItems ? (
                    <Text className="pixel-agent-hover-muted">暂无该居民发出的消息</Text>
                ) : (
                    <div className="pixel-agent-hover-message-list">
                        {outgoingItems.slice(0, 3).map((item, index) => (
                            <div className="pixel-agent-hover-message" key={`${item.content}-${index}`}>
                                <Text type="secondary">{formatSentMessageTarget(item)}</Text>
                                <Text className="pixel-agent-hover-text">{item.content ?? ''}</Text>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function PixelTownCanvas({
    frame,
    map,
    selectedAgentId,
    onSelectAgent,
}: {
    frame?: PixelFrame;
    map: WalkableMap;
    selectedAgentId?: number;
    onSelectAgent: (agentId: number) => void;
}) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const gameRef = useRef<Phaser.Game | null>(null);
    const bridgeRef = useRef<PhaserBridge>({
        sprites: new Map(),
        labels: new Map(),
        hitZones: new Map(),
        locationMarkers: [],
    });
    const frameRef = useRef<PixelFrame | undefined>(frame);
    const onSelectAgentRef = useRef(onSelectAgent);
    const [hoverState, setHoverState] = useState<AgentHoverState | undefined>();
    const [agentScreenPositions, setAgentScreenPositions] = useState<Record<number, AgentScreenPosition>>({});
    const [canvasSize, setCanvasSize] = useState<CanvasSize>({ width: 0, height: 0 });
    const hoveredAgent = frame?.agents.find((agent) => agent.id === hoverState?.agentId);

    const clampHoverPosition = useCallback((rawX: number, rawY: number): [number, number] => {
        const width = containerRef.current?.clientWidth ?? 0;
        const height = containerRef.current?.clientHeight ?? 0;
        const cardWidth = 270;
        const cardHeight = 230;
        const gap = 10;
        const maxX = Math.max(gap, width - cardWidth - gap);
        const maxY = Math.max(gap, height - cardHeight - gap);
        return [
            Phaser.Math.Clamp(rawX + 16, gap, maxX),
            Phaser.Math.Clamp(rawY + 16, gap, maxY),
        ];
    }, []);

    const syncAgentScreenPositions = useCallback(() => {
        const scene = bridgeRef.current.scene;
        const currentFrame = frameRef.current;
        if (!scene || !currentFrame) {
            setAgentScreenPositions({});
            return;
        }
        const camera = scene.cameras.main;
        const tileSize = currentFrame.map.tileSize || TILE_SIZE;
        const next: Record<number, AgentScreenPosition> = {};
        currentFrame.agents.forEach((agent) => {
            const worldX = agent.tile.x * tileSize + tileSize / 2;
            const worldY = agent.tile.y * tileSize + tileSize / 2;
            next[agent.id] = {
                x: (worldX - camera.scrollX) * camera.zoom + camera.x,
                y: (worldY - camera.scrollY) * camera.zoom + camera.y,
            };
        });
        setAgentScreenPositions(next);
    }, []);

    useEffect(() => {
        frameRef.current = frame;
    }, [frame]);

    useEffect(() => {
        onSelectAgentRef.current = onSelectAgent;
    }, [onSelectAgent]);

    useEffect(() => {
        const element = containerRef.current;
        if (!element) {
            return undefined;
        }
        const updateSize = () => {
            setCanvasSize({
                width: element.clientWidth,
                height: element.clientHeight,
            });
        };
        updateSize();
        const observer = new ResizeObserver(updateSize);
        observer.observe(element);
        return () => observer.disconnect();
    }, []);

    const handleHoverAgent = useCallback((agentId: number | undefined, pointer?: Phaser.Input.Pointer) => {
        if (agentId === undefined || !pointer) {
            setHoverState(undefined);
            return;
        }
        const [x, y] = clampHoverPosition(pointer.x, pointer.y);
        setHoverState({ agentId, x, y });
    }, [clampHoverPosition]);

    const handleDomHoverAgent = useCallback((agentId: number, event: React.MouseEvent<HTMLDivElement>) => {
        const bounds = containerRef.current?.getBoundingClientRect();
        if (!bounds) {
            return;
        }
        const [x, y] = clampHoverPosition(
            event.clientX - bounds.left,
            event.clientY - bounds.top,
        );
        setHoverState({ agentId, x, y });
    }, [clampHoverPosition]);

    useEffect(() => {
        if (!containerRef.current || gameRef.current) {
            return;
        }

        class PixelTownScene extends Phaser.Scene {
            preload() {
                this.load.tilemapTiledJSON('smallville-map', map.tiledMapUrl);
                map.tilesets.forEach((tileset) => {
                    this.load.image(tileset.name, tileset.image_url);
                });
                map.locations.forEach((location) => {
                    if (location.visual_asset_url) {
                        this.load.image(`location-${location.id}`, location.visual_asset_url);
                    }
                });
                CHARACTER_NAMES.forEach((name) => {
                    this.load.spritesheet(name, `${CHARACTER_ROOT}/${name}.png`, {
                        frameWidth: TILE_SIZE,
                        frameHeight: TILE_SIZE,
                    });
                });
            }

            create() {
                bridgeRef.current.scene = this;
                const tilemap = this.make.tilemap({ key: 'smallville-map' });
                const tilesets = map.tilesets
                    .map((tileset) => tilemap.addTilesetImage(tileset.name, tileset.name))
                    .filter((tileset): tileset is Phaser.Tilemaps.Tileset => Boolean(tileset));

                tilemap.layers.forEach((layerData) => {
                    const rawLayer = layerData as Phaser.Tilemaps.LayerData & { type?: string };
                    if (rawLayer.type && rawLayer.type !== 'tilelayer') {
                        return;
                    }
                    if (HIDDEN_TILE_LAYER_NAMES.has(layerData.name)) {
                        return;
                    }
                    const layer = tilemap.createLayer(layerData.name, tilesets, 0, 0);
                    if (layerData.name.startsWith('Foreground')) {
                        layer?.setDepth(20);
                    }
                });

                bridgeRef.current.mapWidthPixels = tilemap.widthInPixels;
                bridgeRef.current.mapHeightPixels = tilemap.heightInPixels;
                renderLocationMarkers(this, map, bridgeRef.current);
                this.cameras.main.setBounds(0, 0, tilemap.widthInPixels, tilemap.heightInPixels);
                fitCameraToMap(this, bridgeRef.current);

                let dragStart: { x: number; y: number; scrollX: number; scrollY: number } | undefined;
                this.input.on('pointerdown', (pointer: Phaser.Input.Pointer) => {
                    if (pointer.leftButtonDown()) {
                        dragStart = {
                            x: pointer.x,
                            y: pointer.y,
                            scrollX: this.cameras.main.scrollX,
                            scrollY: this.cameras.main.scrollY,
                        };
                    }
                });
                this.input.on('pointermove', (pointer: Phaser.Input.Pointer) => {
                    if (!dragStart || !pointer.isDown) {
                        return;
                    }
                    this.cameras.main.scrollX = dragStart.scrollX - (pointer.x - dragStart.x) / this.cameras.main.zoom;
                    this.cameras.main.scrollY = dragStart.scrollY - (pointer.y - dragStart.y) / this.cameras.main.zoom;
                    syncAgentScreenPositions();
                });
                this.input.on('pointerup', () => {
                    dragStart = undefined;
                });
                this.input.on('pointerout', () => {
                    dragStart = undefined;
                    handleHoverAgent(undefined);
                });
                this.input.on('wheel', (pointer: Phaser.Input.Pointer, _objects: unknown[], _dx: number, dy: number) => {
                    const before = this.cameras.main.getWorldPoint(pointer.x, pointer.y);
                    const nextZoom = Phaser.Math.Clamp(this.cameras.main.zoom + (dy > 0 ? -0.06 : 0.06), 0.16, 1.8);
                    this.cameras.main.setZoom(nextZoom);
                    const after = this.cameras.main.getWorldPoint(pointer.x, pointer.y);
                    this.cameras.main.scrollX += before.x - after.x;
                    this.cameras.main.scrollY += before.y - after.y;
                    syncAgentScreenPositions();
                });
                this.scale.on('resize', () => {
                    fitCameraToMap(this, bridgeRef.current);
                    syncAgentScreenPositions();
                });
                this.input.keyboard?.createCursorKeys();
                renderFrame(this, frameRef.current, bridgeRef.current, onSelectAgentRef.current, handleHoverAgent);
                syncAgentScreenPositions();
            }
        }

        gameRef.current = new Phaser.Game({
            type: Phaser.CANVAS,
            parent: containerRef.current,
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight,
            backgroundColor: '#111827',
            pixelArt: true,
            physics: {
                default: 'arcade',
                arcade: { gravity: { x: 0, y: 0 } },
            },
            scale: {
                mode: Phaser.Scale.RESIZE,
                autoCenter: Phaser.Scale.CENTER_BOTH,
            },
            scene: PixelTownScene,
        });

        return () => {
            gameRef.current?.destroy(true);
            gameRef.current = null;
            bridgeRef.current = {
                sprites: new Map(),
                labels: new Map(),
                hitZones: new Map(),
                locationMarkers: [],
            };
        };
    }, [handleHoverAgent, map, syncAgentScreenPositions]);

    useEffect(() => {
        if (bridgeRef.current.scene) {
            renderFrame(bridgeRef.current.scene, frame, bridgeRef.current, onSelectAgentRef.current, handleHoverAgent);
            syncAgentScreenPositions();
        }
    }, [frame, handleHoverAgent, syncAgentScreenPositions]);

    useEffect(() => {
        if (hoverState && !hoveredAgent) {
            setHoverState(undefined);
        }
    }, [hoverState, hoveredAgent]);

    useEffect(() => {
        if (!frame) {
            setAgentScreenPositions({});
            return undefined;
        }
        let attempts = 0;
        const timer = window.setInterval(() => {
            if (bridgeRef.current.scene) {
                renderFrame(
                    bridgeRef.current.scene,
                    frame,
                    bridgeRef.current,
                    onSelectAgentRef.current,
                    handleHoverAgent,
                );
            }
            syncAgentScreenPositions();
            attempts += 1;
            if (attempts >= 10 && (frameRef.current?.agents.length ?? 0) > 0) {
                window.clearInterval(timer);
            }
        }, 120);
        return () => window.clearInterval(timer);
    }, [frame, handleHoverAgent, syncAgentScreenPositions]);

    useEffect(() => {
        bridgeRef.current.selectedId = selectedAgentId;
        updateSelection(bridgeRef.current);
    }, [selectedAgentId]);

    return (
        <div className="pixel-town-canvas" ref={containerRef}>
            <div className="pixel-canvas-controls">
                <Tooltip title={`适配整张地图：${map.displayName}`}>
                    <Button
                        shape="circle"
                        icon={<AimOutlined />}
                        onClick={() => {
                            if (bridgeRef.current.scene) {
                                fitCameraToMap(bridgeRef.current.scene, bridgeRef.current);
                                syncAgentScreenPositions();
                            }
                        }}
                    />
                </Tooltip>
                <Tooltip title="放大地图">
                    <Button
                        shape="circle"
                        icon={<ZoomInOutlined />}
                        onClick={() => {
                            if (bridgeRef.current.scene) {
                                zoomCameraAtCenter(bridgeRef.current.scene, 0.1);
                                syncAgentScreenPositions();
                            }
                        }}
                    />
                </Tooltip>
                <Tooltip title="缩小地图">
                    <Button
                        shape="circle"
                        icon={<ZoomOutOutlined />}
                        onClick={() => {
                            if (bridgeRef.current.scene) {
                                zoomCameraAtCenter(bridgeRef.current.scene, -0.1);
                                syncAgentScreenPositions();
                            }
                        }}
                    />
                </Tooltip>
            </div>
            {frame?.agents.map((agent) => {
                const position = agentScreenPositions[agent.id] ?? getFitScreenPosition(agent, map, canvasSize);
                if (!position) {
                    return null;
                }
                return (
                    <div
                        aria-label={`${agent.name} hover target`}
                        className="pixel-agent-hover-target"
                        key={agent.id}
                        role="button"
                        tabIndex={-1}
                        style={{
                            left: position.x,
                            top: position.y,
                        }}
                        onClick={() => onSelectAgent(agent.id)}
                        onMouseEnter={(event) => handleDomHoverAgent(agent.id, event)}
                        onMouseMove={(event) => handleDomHoverAgent(agent.id, event)}
                        onMouseLeave={() => setHoverState(undefined)}
                    />
                );
            })}
            {hoverState && hoveredAgent && frame && (
                <div
                    className="pixel-agent-hover-layer"
                    style={{ left: hoverState.x, top: hoverState.y }}
                >
                    <PixelAgentHoverCard agent={hoveredAgent} frame={frame} />
                </div>
            )}
        </div>
    );
}

function renderLocationMarkers(scene: Phaser.Scene, map: WalkableMap, bridge: PhaserBridge) {
    bridge.locationMarkers?.forEach((marker) => marker.destroy());
    bridge.locationMarkers = [];
    const tileSize = map.tileSize || TILE_SIZE;

    map.locations
        .filter((location) => Boolean(location.visual_asset_url))
        .forEach((location) => {
            const x = location.anchor_tile.x * tileSize + tileSize / 2;
            const y = location.anchor_tile.y * tileSize + tileSize / 2;
            const marker = scene.add.image(x, y - tileSize * 0.25, `location-${location.id}`);
            marker.setOrigin(0.5, 1);
            marker.setDepth(9);
            marker.setAlpha(0.95);
            marker.setScale(Math.max(1, tileSize / TILE_SIZE));

            const label = scene.add.text(x, y - tileSize * 1.25, location.name, {
                fontFamily: 'monospace',
                fontSize: '10px',
                color: '#f8fafc',
                backgroundColor: 'rgba(15, 23, 42, 0.68)',
                padding: { x: 3, y: 1 },
            });
            label.setOrigin(0.5, 1);
            label.setDepth(22);
            label.setAlpha(0.82);

            bridge.locationMarkers?.push(marker, label);
        });
}

function renderFrame(
    scene: Phaser.Scene,
    frame: PixelFrame | undefined,
    bridge: PhaserBridge,
    onSelectAgent: (agentId: number) => void,
    onHoverAgent: (agentId: number | undefined, pointer?: Phaser.Input.Pointer) => void,
) {
    if (!frame) {
        return;
    }

    const activeIds = new Set(frame.agents.map((agent) => agent.id));
    for (const [agentId, sprite] of bridge.sprites.entries()) {
        if (!activeIds.has(agentId)) {
            sprite.destroy();
            bridge.sprites.delete(agentId);
            bridge.labels.get(agentId)?.destroy();
            bridge.labels.delete(agentId);
            bridge.hitZones.get(agentId)?.destroy();
            bridge.hitZones.delete(agentId);
        }
    }

    frame.agents.forEach((agent) => {
        const tileSize = frame.map.tileSize || TILE_SIZE;
        const x = agent.tile.x * tileSize + tileSize / 2;
        const y = agent.tile.y * tileSize + tileSize / 2;
        let sprite = bridge.sprites.get(agent.id);
        let label = bridge.labels.get(agent.id);
        let hitZone = bridge.hitZones.get(agent.id);

        if (!sprite) {
            sprite = scene.add.sprite(x, y, agent.spriteKey, 1);
            sprite.setDepth(10);
            bridge.sprites.set(agent.id, sprite);
        }
        if (!hitZone) {
            hitZone = scene.add.zone(x, y, tileSize * 5, tileSize * 5);
            hitZone.setDepth(40);
            hitZone.setInteractive({ useHandCursor: true });
            hitZone.on('pointerdown', () => onSelectAgent(agent.id));
            hitZone.on('pointerover', (pointer: Phaser.Input.Pointer) => onHoverAgent(agent.id, pointer));
            hitZone.on('pointermove', (pointer: Phaser.Input.Pointer) => onHoverAgent(agent.id, pointer));
            hitZone.on('pointerout', () => onHoverAgent(undefined));
            bridge.hitZones.set(agent.id, hitZone);
        }
        if (!label) {
            label = scene.add.text(x, y - tileSize * 0.75, agent.name, {
                fontFamily: 'monospace',
                fontSize: '11px',
                color: '#ffffff',
                backgroundColor: 'rgba(17, 24, 39, 0.72)',
                padding: { x: 4, y: 2 },
            });
            label.setOrigin(0.5, 1);
            label.setDepth(30);
            bridge.labels.set(agent.id, label);
        }

        const duration = Math.hypot(sprite.x - x, sprite.y - y) > 1 ? 240 : 0;
        scene.tweens.killTweensOf([sprite, label, hitZone]);
        scene.tweens.add({
            targets: sprite,
            x,
            y,
            duration,
            ease: 'Linear',
        });
        scene.tweens.add({
            targets: label,
            x,
            y: y - tileSize * 0.75,
            duration,
            ease: 'Linear',
        });
        scene.tweens.add({
            targets: hitZone,
            x,
            y,
            duration,
            ease: 'Linear',
        });
        label.setText(agent.name);
    });

    updateSelection(bridge);
}

function updateSelection(bridge: PhaserBridge) {
    for (const [agentId, sprite] of bridge.sprites.entries()) {
        const selected = agentId === bridge.selectedId;
        sprite.setTint(selected ? 0xfff1a8 : 0xffffff);
        sprite.setScale(selected ? 1.18 : 1);
        bridge.labels.get(agentId)?.setAlpha(selected ? 1 : 0.82);
    }
    if (bridge.selectedId && bridge.scene) {
        const sprite = bridge.sprites.get(bridge.selectedId);
        if (sprite) {
            bridge.scene.cameras.main.pan(sprite.x, sprite.y, 360, 'Sine.easeInOut');
        }
    }
}

export default function PixelReplay() {
    const [messageApi, messageContextHolder] = message.useMessage();
    const navigate = useNavigate();
    const { hypothesisId, experimentId } = useParams();
    const [searchParams] = useSearchParams();
    const effectiveHypothesisId = hypothesisId ?? DEFAULT_HYPOTHESIS_ID;
    const effectiveExperimentId = experimentId ?? DEFAULT_EXPERIMENT_ID;
    const workspacePath = searchParams.get('workspace_path') ?? DEFAULT_WORKSPACE_PATH;
    const [info, setInfo] = useState<ReplayInfo | undefined>();
    const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
    const [profiles, setProfiles] = useState<AgentProfile[]>([]);
    const [walkableMap, setWalkableMap] = useState<WalkableMap | undefined>();
    const [bundle, setBundle] = useState<ReplayStepBundle | undefined>();
    const [currentIndex, setCurrentIndex] = useState(0);
    const [selectedAgentId, setSelectedAgentId] = useState<number | undefined>();
    const [playing, setPlaying] = useState(false);
    const [intervalMs, setIntervalMs] = useState(1000);
    const [loading, setLoading] = useState(true);
    const [stepLoading, setStepLoading] = useState(false);
    const [error, setError] = useState<string | undefined>();
    const [liveStatus, setLiveStatus] = useState<LiveStatus | undefined>();
    const [liveBusy, setLiveBusy] = useState(false);
    const [liveMode, setLiveMode] = useState<'ask' | 'intervene'>('ask');
    const [askTargetType, setAskTargetType] = useState<AskTargetType>('all_agents');
    const [askTargetAgentIds, setAskTargetAgentIds] = useState<number[]>([]);
    const [livePrompt, setLivePrompt] = useState('');
    const [liveInteractions, setLiveInteractions] = useState<LiveInteraction[]>([]);
    const [followLatest, setFollowLatest] = useState(true);
    const [agentBuilderOpen, setAgentBuilderOpen] = useState(false);
    const [agentDetailOpen, setAgentDetailOpen] = useState(false);
    const [agentRuntimeById, setAgentRuntimeById] = useState<Record<number, AgentRuntimeState>>({});
    const [agentRuntimeLoadingId, setAgentRuntimeLoadingId] = useState<number | undefined>();
    const [loadingDetail, setLoadingDetail] = useState<string | undefined>();

    const replayBaseUrl = useMemo(() => {
        if (!effectiveHypothesisId || !effectiveExperimentId || !workspacePath) {
            return undefined;
        }
        return `/api/v1/replay/${encodeURIComponent(effectiveHypothesisId)}/${encodeURIComponent(effectiveExperimentId)}`;
    }, [effectiveExperimentId, effectiveHypothesisId, workspacePath]);

    const withWorkspace = useCallback((path: string) => {
        return `${replayBaseUrl}${path}?workspace_path=${encodeURIComponent(workspacePath)}`;
    }, [replayBaseUrl, workspacePath]);

    const liveBaseUrl = useMemo(() => {
        if (!effectiveHypothesisId || !effectiveExperimentId || !workspacePath) {
            return undefined;
        }
        return `/api/v1/live-experiments/${encodeURIComponent(effectiveHypothesisId)}/${encodeURIComponent(effectiveExperimentId)}`;
    }, [effectiveExperimentId, effectiveHypothesisId, workspacePath]);

    const withLiveWorkspace = useCallback((path = '') => {
        return `${liveBaseUrl}${path}?workspace_path=${encodeURIComponent(workspacePath)}`;
    }, [liveBaseUrl, workspacePath]);

    const refreshReplayData = useCallback(async (jumpToLatest = false) => {
        if (!replayBaseUrl) {
            return;
        }
        const [nextInfo, nextTimeline, nextProfiles] = await Promise.all([
            fetchJson<ReplayInfo>(withWorkspace('/info')),
            fetchJson<TimelinePoint[]>(withWorkspace('/timeline')),
            fetchJson<AgentProfile[]>(withWorkspace('/agents/profiles')),
            fetchJson(withWorkspace('/panel-schema')),
        ]);
        setInfo(nextInfo);
        setTimeline(nextTimeline);
        setProfiles(nextProfiles);
        if (jumpToLatest && nextTimeline.length > 0) {
            setCurrentIndex(nextTimeline.length - 1);
        }
    }, [replayBaseUrl, withWorkspace]);

    useEffect(() => {
        let cancelled = false;

        async function init() {
            if (!workspacePath) {
                setError('Missing workspace_path query parameter.');
                setLoading(false);
                return;
            }
            if (!replayBaseUrl) {
                return;
            }

            setLoading(true);
            setError(undefined);
            setLoadingDetail(undefined);
            setCurrentIndex(0);
            try {
                const { nextMap, nextLiveStatus } = await waitForInitialReplay(
                    async () => {
                        const mapInfo = await fetchJson<ReplayMapInfo>(withWorkspace('/map'));
                        const loadedMap = await loadWalkableMap(mapInfo);
                        let loadedLiveStatus: LiveStatus | undefined;
                        if (liveBaseUrl) {
                            try {
                                loadedLiveStatus = await postJson<LiveStatus>(withLiveWorkspace('/sessions'));
                            } catch (err) {
                                console.info('Live session unavailable; falling back to replay-only mode.', err);
                            }
                        }
                        await refreshReplayData(true);
                        return { nextMap: loadedMap, nextLiveStatus: loadedLiveStatus };
                    },
                    (err, attempt) => {
                        if (!cancelled) {
                            setLoadingDetail(`GOD 正在准备小镇回放，等待服务和第一帧数据就绪... 第 ${attempt} 次重试：${toErrorMessage(err)}`);
                        }
                    },
                    () => cancelled,
                );
                if (cancelled) {
                    return;
                }
                if (nextLiveStatus) {
                    setLiveStatus(nextLiveStatus);
                } else {
                    setLiveStatus(undefined);
                }
                setWalkableMap(nextMap);
                setSelectedAgentId(undefined);
                setAgentDetailOpen(false);
                setAgentRuntimeById({});
                setFollowLatest(true);
            } catch (err) {
                if (!cancelled) {
                    setError(toErrorMessage(err));
                }
            } finally {
                if (!cancelled) {
                    setLoadingDetail(undefined);
                    setLoading(false);
                }
            }
        }

        init();
        return () => {
            cancelled = true;
        };
    }, [liveBaseUrl, refreshReplayData, replayBaseUrl, withLiveWorkspace, workspacePath]);

    const liveSessionReady = Boolean(liveStatus);

    useEffect(() => {
        if (!liveBaseUrl || !workspacePath || !liveSessionReady) {
            return;
        }
        const url = new URL(withLiveWorkspace('/ws'), window.location.origin);
        url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
        const socket = new WebSocket(url.toString());
        socket.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data) as LiveEvent;
                if (payload.status) {
                    setLiveStatus(payload.status);
                }
                if (payload.type === 'step_completed') {
                    refreshReplayData(followLatest).catch((err) => {
                        setError(err instanceof Error ? err.message : String(err));
                    });
                }
                if (payload.type === 'command_completed') {
                    const command = payload.command;
                    const result = command?.result ?? payload.result;
                    const artifactName = command?.artifact_name ?? payload.artifact_name;
                    setLiveInteractions((items) => {
                        const next = [...items];
                        const index = next.findIndex((item) => (
                            item.result === undefined
                            && (!command?.type || item.type === command.type)
                        ));
                        if (index >= 0) {
                            next[index] = {
                                ...next[index],
                                result,
                                artifactName,
                            };
                        }
                        return next;
                    });
                }
                if (payload.type === 'command_failed') {
                    setLiveInteractions((items) => {
                        const next = [...items];
                        const index = next.findIndex((item) => item.result === undefined);
                        if (index >= 0) {
                            next[index] = {
                                ...next[index],
                                result: `调用失败：${payload.message ?? '实时命令未完成'}`,
                            };
                        }
                        return next;
                    });
                }
                if (payload.type === 'error') {
                    messageApi.error(payload.message ?? '实时实验执行失败');
                }
            } catch (err) {
                console.error('Failed to parse live event:', err);
            }
        };
        socket.onerror = () => {
            console.error('Live experiment WebSocket error');
        };
        return () => socket.close();
    }, [followLatest, liveBaseUrl, liveSessionReady, messageApi, refreshReplayData, withLiveWorkspace, workspacePath]);

    const currentStep = timeline[currentIndex]?.step ?? Math.max(0, (liveStatus?.step_count ?? 1) - 1);

    useEffect(() => {
        let cancelled = false;
        async function fetchStep() {
            if (!replayBaseUrl) {
                return;
            }
            if (timeline.length === 0) {
                setBundle(undefined);
                return;
            }
            setStepLoading(true);
            try {
                const nextBundle = await fetchJson<ReplayStepBundle>(withWorkspace(`/steps/${currentStep}/bundle`));
                if (!cancelled) {
                    setBundle(nextBundle);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err instanceof Error ? err.message : String(err));
                }
            } finally {
                if (!cancelled) {
                    setStepLoading(false);
                }
            }
        }
        fetchStep();
        return () => {
            cancelled = true;
        };
    }, [currentStep, replayBaseUrl, timeline.length, withWorkspace]);

    useEffect(() => {
        let cancelled = false;
        async function fetchAgentRuntime() {
            if (!selectedAgentId || !replayBaseUrl || agentRuntimeById[selectedAgentId]) {
                return;
            }
            setAgentRuntimeLoadingId(selectedAgentId);
            try {
                const runtime = await fetchJson<AgentRuntimeState>(
                    withWorkspace(`/agents/${selectedAgentId}/runtime-state`),
                );
                if (!cancelled) {
                    setAgentRuntimeById((items) => ({
                        ...items,
                        [selectedAgentId]: runtime,
                    }));
                }
            } catch (err) {
                if (!cancelled) {
                    messageApi.error(err instanceof Error ? err.message : String(err));
                }
            } finally {
                if (!cancelled) {
                    setAgentRuntimeLoadingId(undefined);
                }
            }
        }
        fetchAgentRuntime();
        return () => {
            cancelled = true;
        };
    }, [agentRuntimeById, messageApi, replayBaseUrl, selectedAgentId, withWorkspace]);

    useEffect(() => {
        if (!playing || timeline.length <= 1) {
            return;
        }
        const timer = window.setInterval(() => {
            setCurrentIndex((index) => {
                if (index >= timeline.length - 1) {
                    setPlaying(false);
                    return index;
                }
                return index + 1;
            });
        }, intervalMs);
        return () => window.clearInterval(timer);
    }, [intervalMs, playing, timeline.length]);

    const liveWaiting = liveStatus?.status === 'waiting';
    const liveAuto = liveStatus?.status === 'auto' || liveStatus?.auto_running;
    const liveTargetMentions = useMemo<LiveTargetMention[]>(() => [
        {
            value: '系统',
            label: '@系统',
            target: { type: 'society' },
        },
        {
            value: '所有居民',
            label: '@所有居民',
            target: { type: 'all_agents' },
        },
        ...profiles.map((profile) => {
            const name = getAgentName(profile);
            return {
                value: `${name}#${profile.id}`,
                label: `@${name} #${profile.id}`,
                target: { type: 'agent', agent_id: profile.id } as AskTarget,
            };
        }),
    ], [profiles]);

    const askTarget = useMemo<AskTarget>(() => {
        if (askTargetType === 'agent') {
            return { type: 'agent', agent_id: askTargetAgentIds[0] };
        }
        if (askTargetType === 'agents') {
            return { type: 'agents', agent_ids: askTargetAgentIds };
        }
        return { type: askTargetType };
    }, [askTargetAgentIds, askTargetType]);

    const promptTarget = useMemo(() => (
        resolveTargetFromPrompt(livePrompt, liveTargetMentions, askTarget)
    ), [askTarget, livePrompt, liveTargetMentions]);

    const promptTargetReady = promptTarget.type === 'society'
        || promptTarget.type === 'all_agents'
        || Boolean(promptTarget.agent_id)
        || Boolean(promptTarget.agent_ids?.length);

    const promptTargetLabel = describeInteractionTarget(promptTarget, profiles, liveMode);

    const applyMentionTarget = useCallback((value: string) => {
        const mention = liveTargetMentions.find((item) => item.value === value);
        if (!mention) {
            return;
        }
        if (mention.target.type === 'society' || mention.target.type === 'all_agents') {
            setAskTargetType(mention.target.type);
            setAskTargetAgentIds([]);
            return;
        }
        if (mention.target.agent_id !== undefined) {
            setAskTargetType('agent');
            setAskTargetAgentIds([mention.target.agent_id]);
        }
    }, [liveTargetMentions]);

    const runLiveStep = useCallback(async () => {
        if (!liveBaseUrl) {
            return;
        }
        setLiveBusy(true);
        try {
            const status = await postJson<LiveStatus>(withLiveWorkspace('/run-step'), {
                tick: liveStatus?.default_tick,
            });
            setLiveStatus(status);
            await refreshReplayData(true);
        } catch (err) {
            messageApi.error(err instanceof Error ? err.message : String(err));
        } finally {
            setLiveBusy(false);
        }
    }, [liveBaseUrl, liveStatus?.default_tick, messageApi, refreshReplayData, withLiveWorkspace]);

    const toggleLiveAuto = useCallback(async () => {
        if (!liveBaseUrl) {
            return;
        }
        setLiveBusy(true);
        try {
            if (liveAuto) {
                const status = await postJson<LiveStatus>(withLiveWorkspace('/pause'));
                setLiveStatus(status);
            } else {
                const status = await postJson<LiveStatus>(withLiveWorkspace('/auto'), {
                    enabled: true,
                    tick: liveStatus?.default_tick,
                    interval_ms: intervalMs,
                });
                setLiveStatus(status);
                setFollowLatest(true);
            }
        } catch (err) {
            messageApi.error(err instanceof Error ? err.message : String(err));
        } finally {
            setLiveBusy(false);
        }
    }, [intervalMs, liveAuto, liveBaseUrl, liveStatus?.default_tick, messageApi, withLiveWorkspace]);

    const submitLiveInteraction = useCallback(async () => {
        const rawPrompt = livePrompt.trim();
        const prompt = stripTargetMentions(rawPrompt, liveTargetMentions) || rawPrompt;
        const target = resolveTargetFromPrompt(rawPrompt, liveTargetMentions, askTarget);
        if (!liveBaseUrl || !prompt || !promptTargetReady) {
            return;
        }
        const pending: LiveInteraction = {
            id: `${Date.now()}`,
            type: liveMode,
            prompt: rawPrompt,
            targetLabel: describeInteractionTarget(target, profiles, liveMode),
        };
        setLiveInteractions((items) => [...items, pending]);
        setLivePrompt('');
        setLiveBusy(true);
        try {
            const response = await postJson<{
                result: string;
                artifact_name?: string;
                status: LiveStatusValue;
                step_count: number;
                simulation_time?: string;
            }>(
                withLiveWorkspace(liveMode === 'ask' ? '/ask' : '/intervene'),
                liveMode === 'ask'
                    ? { question: prompt, target }
                    : { instruction: prompt, target },
            );
            setLiveStatus((status) => status ? {
                ...status,
                status: response.status,
                step_count: response.step_count,
                simulation_time: response.simulation_time,
                auto_running: false,
                current_command: null,
            } : status);
            setLiveInteractions((items) => {
                const next = [...items];
                const exactIndex = next.findIndex((item) => item.id === pending.id);
                const fallbackIndex = next.findIndex((item) => (
                    item.result === undefined && item.type === pending.type
                ));
                const index = exactIndex >= 0 ? exactIndex : fallbackIndex;
                if (index >= 0) {
                    next[index] = {
                        ...next[index],
                        result: response.result,
                        artifactName: response.artifact_name,
                    };
                }
                return next;
            });
            messageApi.success(response.artifact_name ? `结果已保存：${response.artifact_name}` : '命令已完成');
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : String(err);
            setLiveInteractions((items) => items.map((item) => (
                item.id === pending.id
                    ? { ...item, result: `调用失败：${errorMessage}` }
                    : item
            )));
            setLiveStatus((status) => status ? {
                ...status,
                status: 'waiting',
                auto_running: false,
                current_command: null,
                error: errorMessage,
            } : status);
            messageApi.error(errorMessage);
        } finally {
            setLiveBusy(false);
        }
    }, [askTarget, liveBaseUrl, liveMode, livePrompt, liveTargetMentions, messageApi, profiles, promptTargetReady, withLiveWorkspace]);

    const frame = useMemo(() => {
        if (!walkableMap) {
            return undefined;
        }
        return buildPixelFrame(profiles, bundle, currentStep, walkableMap);
    }, [bundle, currentStep, profiles, walkableMap]);

    const selectedAgent = frame?.agents.find((agent) => agent.id === selectedAgentId);
    const selectedProfile = profiles.find((profile) => profile.id === selectedAgentId);
    const selectedAgentRow = selectedAgentId === undefined ? undefined : findAgentRow(bundle, selectedAgentId);
    const selectedAgentRuntime = selectedAgentId === undefined ? undefined : agentRuntimeById[selectedAgentId];
    const selectedAgentSummary = selectedAgentRow ?? buildAgentSummary(selectedAgent);
    const selectedAgentSnapshot = selectedAgentRuntime?.agent_state_snapshot;
    const selectedSnapshotProfile = asRecord(selectedAgentSnapshot?.profile);
    const selectedSkillStates = asRecord(selectedAgentSnapshot?.skill_states);
    const selectedSkillRuntimeSummary = selectedAgentSnapshot ? {
        mounted_skill_ids: selectedAgentSnapshot.mounted_skill_ids,
        last_skill_decision: selectedAgentSnapshot.last_skill_decision,
        last_skill_result: selectedAgentSnapshot.last_skill_result,
        last_environment_effects: selectedAgentSnapshot.last_environment_effects,
    } : undefined;
    const envSnapshot = firstEnvRow(bundle);
    const communications = parseCommunications(envSnapshot);
    const missingReplayTileCount = frame?.agents.filter((agent) => !agent.hasReplayTile).length ?? 0;

    const toggleSelectedAgent = useCallback((agentId: number) => {
        setSelectedAgentId((current) => {
            if (current === agentId) {
                setAgentDetailOpen(false);
                return undefined;
            }
            return agentId;
        });
    }, []);

    const clearSelectedAgent = useCallback(() => {
        setSelectedAgentId(undefined);
        setAgentDetailOpen(false);
    }, []);

    if (loading) {
        return (
            <div className="pixel-replay-loading">
                <Spin size="large" />
                <Space direction="vertical" size={4} align="center">
                    <Text>正在加载小镇回放...</Text>
                    {loadingDetail && <Text type="secondary">{loadingDetail}</Text>}
                </Space>
            </div>
        );
    }

    if (error) {
        return (
            <div className="pixel-replay-error">
                <Alert
                    type="error"
                    showIcon
                    message="小镇回放无法启动"
                    description={error}
                />
            </div>
        );
    }

    if (!frame) {
        return (
            <div className="pixel-replay-error">
                <Empty description="这个实验还没有可回放画面。" />
            </div>
        );
    }

    return (
        <div className="pixel-replay-page">
            {messageContextHolder}
            <PixelTownCanvas
                frame={frame}
                map={frame.map}
                selectedAgentId={selectedAgentId}
                onSelectAgent={setSelectedAgentId}
            />

            <Card className="pixel-replay-topbar" variant="borderless">
                <Space align="center" wrap>
                    <Button
                        icon={playing ? <PauseOutlined /> : <CaretRightOutlined />}
                        type="primary"
                        onClick={() => setPlaying((value) => !value)}
                    >
                        {playing ? '暂停' : '播放'}
                    </Button>
                    <Button
                        icon={<StepBackwardOutlined />}
                        disabled={timeline.length <= 1}
                        onClick={() => {
                            setFollowLatest(false);
                            setCurrentIndex((index) => Math.max(0, index - 1));
                        }}
                    />
                    <Button
                        icon={<StepForwardOutlined />}
                        disabled={timeline.length <= 1}
                        onClick={() => {
                            setFollowLatest(false);
                            setCurrentIndex((index) => Math.min(timeline.length - 1, index + 1));
                        }}
                    />
                    <Space.Compact className="pixel-live-control-cluster">
                        <Button
                            className="pixel-run-step-button"
                            type="primary"
                            icon={<StepForwardOutlined />}
                            loading={liveBusy && liveStatus?.status === 'running_step'}
                            disabled={!liveWaiting || liveBusy}
                            onClick={runLiveStep}
                        >
                            Run Step
                        </Button>
                        <Button
                            icon={liveAuto ? <PauseOutlined /> : <CaretRightOutlined />}
                            loading={liveBusy && !liveAuto}
                            disabled={liveBusy || (!liveAuto && !liveWaiting)}
                            onClick={toggleLiveAuto}
                        >
                            {liveAuto ? 'Pause Auto' : 'Auto'}
                        </Button>
                        <Button
                            disabled
                            className={`pixel-live-status-button status-${liveStatus?.status ?? 'offline'}`}
                        >
                            {liveStatus?.status ?? 'offline'}
                        </Button>
                    </Space.Compact>
                    <Select
                        value={intervalMs}
                        style={{ width: 116 }}
                        onChange={setIntervalMs}
                        options={[
                            { value: 1500, label: '0.7x' },
                            { value: 1000, label: '1x' },
                            { value: 500, label: '2x' },
                            { value: 250, label: '4x' },
                        ]}
                    />
                    <Tag color="blue">回放第 {currentStep + 1} 步</Tag>
                    {liveStatus && <Tag color="geekblue">Live 已执行 {liveStatus.step_count} 步</Tag>}
                    <Text>{formatTime(bundle?.t ?? timeline[currentIndex]?.t)}</Text>
                    {stepLoading && <Spin size="small" />}
                    <Tooltip title="创建或配置一个新的实验副本">
                        <Button icon={<SettingOutlined />} onClick={() => navigate('/setup')}>
                            新实验
                        </Button>
                    </Tooltip>
                    <Tooltip title="查看和创建真实可执行 Skills">
                        <Button icon={<ThunderboltOutlined />} onClick={() => navigate('/skills')}>
                            Skills
                        </Button>
                    </Tooltip>
                </Space>
                <input
                    className="pixel-replay-range"
                    type="range"
                    min={0}
                    max={Math.max(0, timeline.length - 1)}
                    value={Math.min(currentIndex, Math.max(0, timeline.length - 1))}
                    disabled={timeline.length === 0}
                    onChange={(event) => {
                        setFollowLatest(false);
                        setCurrentIndex(Number(event.target.value));
                    }}
                />
            </Card>

            <div className="pixel-dashboard">
                <Card className="pixel-panel pixel-overview-card" variant="borderless">
                    <Title level={4}>小镇实验回放</Title>
                    <Text type="secondary">
                        假设 {effectiveHypothesisId} · 实验 {effectiveExperimentId}
                    </Text>
                    <div className="pixel-replay-stats">
                        <Tag>{info?.agent_count ?? profiles.length}居民</Tag>
                        <Tag>{info?.total_steps ?? timeline.length}步</Tag>
                        <Tag color="geekblue">{frame.map.displayName}</Tag>
                        {envSnapshot?.total_messages_sent !== undefined && (
                            <Tag color="green">累计{String(envSnapshot.total_messages_sent)}消息</Tag>
                        )}
                        <Tag color={communications.length > 0 ? 'blue' : undefined}>
                            本步{communications.length}通信
                        </Tag>
                        {missingReplayTileCount > 0 && (
                            <Tag color="orange">{missingReplayTileCount}人缺少地图坐标</Tag>
                        )}
                    </div>
                </Card>

                <Card className="pixel-panel pixel-step-card" variant="borderless">
                    <div className="pixel-panel-content pixel-step-content">
                        <div className="pixel-section-heading">
                            <Text strong>发生了什么</Text>
                            <Tag color="blue">第 {currentStep + 1} 步</Tag>
                        </div>
                        <div className="pixel-step-summary">
                            <Text type="secondary">阶段</Text>
                            <Text strong>{formatPhase(envSnapshot?.current_phase)}</Text>
                        </div>
                        {envSnapshot?.latest_event !== undefined && (
                            <Text className="pixel-step-event">
                                {String(envSnapshot.latest_event)}
                            </Text>
                        )}
                    </div>
                </Card>

                <Card className="pixel-panel pixel-chat-card" variant="borderless">
                    <div className="pixel-section-heading">
                        <Text strong>Agent 间聊天</Text>
                        <Tag color={communications.length > 0 ? 'blue' : undefined}>
                            本步 {communications.length} 条
                        </Tag>
                    </div>
                    <div className="pixel-communication-list">
                        {communications.length === 0 ? (
                            <Text type="secondary">这一小步没有新的 agent 间通信。请切换上一/下一步查看。</Text>
                        ) : communications.map((item, index) => (
                            <div className="pixel-communication-row" key={`${item.sender_name}-${index}`}>
                                <div className="pixel-communication-meta">
                                    <Text strong>{item.sender_name ?? '居民'}</Text>
                                    <Tag color={item.type === 'direct' ? 'purple' : 'cyan'}>
                                        {item.type === 'direct' ? '私信' : '群聊'}
                                    </Tag>
                                </div>
                                <Text type="secondary">
                                    {item.type === 'direct'
                                        ? `发给 ${item.receiver_name ?? '居民'}`
                                        : `发到 ${item.group_name ?? '群组'}${item.recipient_count ? `（${item.recipient_count} 人）` : ''}`}
                                </Text>
                                <Text className="pixel-message-text">{item.content ?? ''}</Text>
                            </div>
                        ))}
                    </div>
                </Card>

                <Card className="pixel-panel pixel-residents-card" variant="borderless">
                    <div className="pixel-section-heading">
                        <Space direction="vertical" size={0}>
                            <Text strong>居民状态</Text>
                            <Text type="secondary">点击选中，再次点击取消</Text>
                        </Space>
                        <Button
                            size="small"
                            type="primary"
                            ghost
                            icon={<UserAddOutlined />}
                            onClick={() => setAgentBuilderOpen(true)}
                        >
                            Add Agent
                        </Button>
                    </div>
                    {selectedAgent && (
                        <div className="pixel-replay-selected">
                            <Text type="secondary">选中的居民</Text>
                            <Text strong>{selectedAgent.name}</Text>
                            <Text>{selectedAgent.action}</Text>
                            <Text type="secondary">位置：{selectedAgent.location}</Text>
                            <Space size={4} wrap>
                                {selectedAgent.locationId && <Tag>{selectedAgent.locationId}</Tag>}
                                {selectedAgent.movementStatus && (
                                    <Tag color={selectedAgent.movementStatus === 'moving' ? 'blue' : 'green'}>
                                        {selectedAgent.movementStatus}
                                    </Tag>
                                )}
                                <Tag color={selectedAgent.hasReplayTile ? 'geekblue' : 'orange'}>
                                    tile {selectedAgent.tile.x}, {selectedAgent.tile.y}
                                </Tag>
                            </Space>
                            {selectedAgent.availableInteractions.length > 0 && (
                                <div className="pixel-interaction-list">
                                    {selectedAgent.availableInteractions.map((interaction) => (
                                        <Tooltip title={interaction.description} key={interaction.id}>
                                            <Tag color="cyan">{interaction.name}</Tag>
                                        </Tooltip>
                                    ))}
                                </div>
                            )}
                            {selectedAgent.emotion && <Text type="secondary">情绪：{selectedAgent.emotion}</Text>}
                            {selectedAgent.lastMessage && (
                                <Text className="pixel-message-text">最近收到：{selectedAgent.lastMessage}</Text>
                            )}
                            <Space size={8} wrap>
                                <Button
                                    size="small"
                                    type="link"
                                    onClick={() => setAgentDetailOpen(true)}
                                >
                                    查看完整详情
                                </Button>
                                <Button
                                    size="small"
                                    type="link"
                                    onClick={clearSelectedAgent}
                                >
                                    取消选中
                                </Button>
                            </Space>
                        </div>
                    )}
                    <div className="pixel-agent-list">
                        {frame.agents.map((agent) => (
                            <div
                                key={agent.id}
                                role="button"
                                tabIndex={0}
                                aria-pressed={agent.id === selectedAgentId}
                                className={`pixel-agent-row ${agent.id === selectedAgentId ? 'selected' : ''}`}
                                onClick={() => toggleSelectedAgent(agent.id)}
                                onKeyDown={(event) => {
                                    if (event.key === 'Enter' || event.key === ' ') {
                                        event.preventDefault();
                                        toggleSelectedAgent(agent.id);
                                    }
                                }}
                            >
                                <span className="pixel-agent-name">{agent.name}</span>
                                <span className="pixel-agent-action">{agent.action}</span>
                                <span className="pixel-agent-location">{agent.location}</span>
                                <span className="pixel-agent-location">
                                    {agent.hasReplayTile ? `tile ${agent.tile.x},${agent.tile.y}` : '缺少地图坐标，使用兼容定位'}
                                </span>
                                {agent.lastMessage && <span className="pixel-agent-location">最近收到：{agent.lastMessage}</span>}
                            </div>
                        ))}
                    </div>
                </Card>
            </div>
            <Card className="pixel-live-console" variant="borderless">
                <div className="pixel-live-console-header">
                    <Space size={8} wrap>
                        <Text strong>Live Console</Text>
                        <Tag color={liveMode === 'ask' ? 'blue' : 'orange'}>
                            {liveMode === 'ask' ? 'Ask' : 'Intervene'}
                        </Tag>
                        <Tag>{promptTargetLabel}</Tag>
                    </Space>
                    <Text type="secondary">
                        {liveWaiting ? '输入 @ 选择对象' : `当前状态：${liveStatus?.status ?? 'offline'}`}
                    </Text>
                </div>
                <div className="pixel-live-result-stream">
                    {liveInteractions.length === 0 ? (
                        <div className="pixel-live-empty">
                            <Text type="secondary">还没有实时交互记录。</Text>
                        </div>
                    ) : liveInteractions.slice().reverse().slice(0, 4).map((item) => (
                        <div className="pixel-live-result-card" key={item.id}>
                            <div className="pixel-communication-meta">
                                <Space size={6} wrap>
                                    <Tag color={item.type === 'ask' ? 'blue' : 'orange'}>
                                        {item.type === 'ask' ? 'Ask' : 'Intervene'}
                                    </Tag>
                                    {item.targetLabel && <Tag>{item.targetLabel}</Tag>}
                                </Space>
                                {item.artifactName && <Text type="secondary">{item.artifactName}</Text>}
                            </div>
                            <Text strong className="pixel-live-prompt">{item.prompt}</Text>
                            <Text className="pixel-live-result-text">
                                {item.result ?? '等待结果...'}
                            </Text>
                        </div>
                    ))}
                </div>
                <div className="pixel-live-composer">
                    <div className="pixel-live-mode-rail">
                        <Segmented
                            block
                            value={liveMode}
                            onChange={(value) => setLiveMode(value as 'ask' | 'intervene')}
                            options={[
                                { label: 'Ask', value: 'ask' },
                                { label: 'Intervene', value: 'intervene' },
                            ]}
                        />
                        <Text type="secondary" className="pixel-live-target-hint">
                            {liveMode === 'ask'
                                ? describeAskTarget(promptTarget, profiles)
                                : `${describeInteractionTarget(promptTarget, profiles, 'intervene')}；下一次 Run Step/Auto 生效`}
                        </Text>
                    </div>
                    <Mentions
                        className="pixel-live-input"
                        value={livePrompt}
                        onChange={setLivePrompt}
                        onSelect={(option) => applyMentionTarget(String(option.value ?? ''))}
                        disabled={!liveWaiting || liveBusy}
                        rows={3}
                        placeholder={liveMode === 'ask'
                            ? '@系统 当前小镇发生了什么？'
                            : '@Jiuwen Alice#1 火山爆发了，通知其他人撤离'}
                        options={liveTargetMentions.map((mention) => ({
                            value: mention.value,
                            label: mention.label,
                        }))}
                    />
                    <Button
                        className="pixel-live-send"
                        type="primary"
                        icon={<SendOutlined />}
                        loading={liveBusy && (liveStatus?.status === 'asking' || liveStatus?.status === 'intervening')}
                        disabled={!liveWaiting || liveBusy || livePrompt.trim() === '' || !promptTargetReady}
                        onClick={submitLiveInteraction}
                    >
                        发送
                    </Button>
                </div>
            </Card>
            <Drawer
                title={selectedAgent ? `${selectedAgent.name} · 居民详情` : '居民详情'}
                open={agentDetailOpen && Boolean(selectedAgent)}
                onClose={() => setAgentDetailOpen(false)}
                width="min(520px, 92vw)"
                mask={false}
                destroyOnHidden
            >
                {selectedAgent && (
                    <div className="pixel-agent-detail-drawer-content">
                        <div className="pixel-replay-selected compact">
                            <Text type="secondary">选中的居民</Text>
                            <Text strong>{selectedAgent.name}</Text>
                            <Text>{selectedAgent.action}</Text>
                            <Text type="secondary">位置：{selectedAgent.location}</Text>
                            <Space size={4} wrap>
                                {selectedAgent.locationId && <Tag>{selectedAgent.locationId}</Tag>}
                                {selectedAgent.movementStatus && (
                                    <Tag color={selectedAgent.movementStatus === 'moving' ? 'blue' : 'green'}>
                                        {selectedAgent.movementStatus}
                                    </Tag>
                                )}
                                <Tag color={selectedAgent.hasReplayTile ? 'geekblue' : 'orange'}>
                                    tile {selectedAgent.tile.x}, {selectedAgent.tile.y}
                                </Tag>
                            </Space>
                        </div>
                        {agentRuntimeLoadingId === selectedAgent.id && (
                            <Space>
                                <Spin size="small" />
                                <Text type="secondary">正在读取 agent 状态...</Text>
                            </Space>
                        )}
                        {renderPlainDetail('Token 消耗', formatTokenUsage(selectedAgentRuntime?.token_usage))}
                        {renderPlainDetail('当前状态', formatInlineFields(selectedAgentSummary, '暂无状态'))}
                        {renderPlainDetail(
                            '当前位置可交互',
                            selectedAgent.availableInteractions.length > 0
                                ? selectedAgent.availableInteractions.map((interaction) => `${interaction.name} (${interaction.id}): ${interaction.description ?? ''}`).join('\n')
                                : '暂无可交互动作',
                        )}
                        {renderPlainDetail('人物背景设定', formatInlineFields(selectedProfile?.profile ?? selectedSnapshotProfile, '暂无人物背景'))}
                        {renderPlainDetail('Skill Runtime', formatInlineFields(selectedSkillRuntimeSummary, '暂无 skill runtime'))}
                        {renderPlainDetail('会话状态', joinDetailBlocks([
                            ['session_state', formatInlineFields(selectedAgentRuntime?.session_state, '暂无会话状态')],
                            ['agent_state_snapshot', formatInlineFields(selectedAgentSnapshot, '暂无快照状态')],
                            ['skill_states', formatInlineFields(selectedSkillStates, '暂无 skill states')],
                        ]))}
                    </div>
                )}
            </Drawer>
            <Drawer
                title="Agent 配置"
                open={agentBuilderOpen}
                onClose={() => setAgentBuilderOpen(false)}
                width="min(1180px, 96vw)"
                destroyOnHidden
            >
                {liveStatus && liveStatus.status !== 'stopped' && liveStatus.status !== 'failed' && (
                    <Alert
                        type={liveStatus.status === 'waiting' ? 'success' : 'info'}
                        showIcon
                        message={liveStatus.status === 'waiting'
                            ? '当前 Live 支持热加载新 Agent'
                            : 'Agent 配置已支持热加载；等待 Live 回到 waiting 后同步'}
                        description={liveStatus.status === 'waiting'
                            ? '保存新增或批量导入的 Agent 后，会同步到当前 Live session；下一个 Run Step/Auto 就会参与响应。已完成的 replay 不会被原地改写。'
                            : '当前 Live 正在处理 step/ask/intervene/auto。配置可先保存，回到 waiting 后再次保存或同步即可在下一步生效。'}
                        style={{ marginBottom: 12 }}
                    />
                )}
                <AgentBuilderPanel
                    embedded
                    autoLoad
                    initialWorkspacePath={workspacePath}
                    initialHypothesisId={effectiveHypothesisId}
                    initialExperimentId={effectiveExperimentId}
                    onSaved={async () => {
                        if (liveBaseUrl && liveStatus?.status === 'waiting') {
                            const result = await postJson<{
                                added_agent_ids: number[];
                                status: LiveStatus;
                            }>(withLiveWorkspace('/sync-agents'));
                            setLiveStatus(result.status);
                            if (result.added_agent_ids.length > 0) {
                                messageApi.success(`已热加载 ${result.added_agent_ids.length} 个 Agent，下一个 step 会参与响应。`);
                            }
                        } else if (liveStatus && liveStatus.status !== 'waiting') {
                            messageApi.warning('配置已保存；当前 Live 不在 waiting 状态，需恢复到 waiting 后才能热加载新 Agent。');
                        }
                        await refreshReplayData(true);
                    }}
                />
            </Drawer>
        </div>
    );
}
