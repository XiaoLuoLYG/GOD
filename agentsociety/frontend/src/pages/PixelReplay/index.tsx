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
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { fetchCustom } from '../../components/fetch';
import LanguageToggle from '../../components/LanguageToggle';
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
const PHASER_TEXT_FONT_FAMILY = 'Arial, "PingFang SC", "Microsoft YaHei", sans-serif';
const AGENT_NAME_LABEL_HEIGHT = 17;
const SPEECH_BUBBLE_LABEL_GAP = 6;
const CAMERA_MIN_ZOOM_FLOOR = 0.01;
const CAMERA_MAX_ZOOM = 1.8;
const AGENT_OVERLAP_SINGLE_RING_LIMIT = 8;
const AGENT_OVERLAP_FIRST_RING_CAPACITY = 6;
const AGENT_OVERLAP_RING_CAPACITY_STEP = 6;
const AGENT_OVERLAP_TARGET_SPACING_TILES = 2.05;
const AGENT_OVERLAP_MIN_RADIUS_TILES = 1.4;
const AGENT_OVERLAP_RING_SPACING_TILES = 2.85;
const AGENT_SPRITE_BASE_SCALE = 1.22;
const AGENT_SPRITE_SELECTED_SCALE = 1.42;
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

type ReplayMapCharacter = {
    name: string;
    image_url: string;
    frame_width?: number;
    frame_height?: number;
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
    character_root_url?: string | null;
    character_sprites?: ReplayMapCharacter[];
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

type VisualOffset = {
    x: number;
    y: number;
};

type WalkableMap = {
    mapId: string;
    displayName: string;
    tileSize: number;
    tiledMapUrl: string;
    tilesets: ReplayMapTileset[];
    characterSprites: ReplayMapCharacter[];
    locations: ReplayMapLocation[];
    interactions: ReplayMapInteraction[];
    width: number;
    height: number;
    walkable: Tile[];
    walkableKeys: Set<string>;
};

type PixelAgent = {
    id: number;
    name: string;
    spriteKey: string;
    tile: Tile;
    visualOffset: VisualOffset;
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
    spriteSize: number;
    labelX: number;
    labelY: number;
    speechX: number;
    speechY: number;
};

type CanvasSize = {
    width: number;
    height: number;
};

type PhaserSpeechBubble = {
    bubble: Phaser.GameObjects.Graphics;
    text: Phaser.GameObjects.Text;
    hitZone: Phaser.GameObjects.Zone;
};

type PhaserBridge = {
    scene?: Phaser.Scene;
    mapWidthPixels?: number;
    mapHeightPixels?: number;
    sprites: Map<number, Phaser.GameObjects.Sprite>;
    labels: Map<number, Phaser.GameObjects.Text>;
    hitZones: Map<number, Phaser.GameObjects.Zone>;
    speechBubbles: Map<number, PhaserSpeechBubble>;
    hoveredSpeechAgentId?: number;
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

function formatPhase(value: unknown, t: TFunction): string {
    if (typeof value !== 'string' || value.trim() === '') {
        return t('replay.pixel.phase.empty');
    }
    return t(`replay.pixel.phase.${value}`, { defaultValue: value });
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

function ringCapacityForIndex(ringIndex: number): number {
    return AGENT_OVERLAP_FIRST_RING_CAPACITY + ringIndex * AGENT_OVERLAP_RING_CAPACITY_STEP;
}

function overlapRadiusForRing(countInRing: number, ringIndex: number): number {
    const spacingRadius = countInRing > 1
        ? AGENT_OVERLAP_TARGET_SPACING_TILES / (2 * Math.sin(Math.PI / countInRing))
        : 0;
    return Math.max(
        AGENT_OVERLAP_MIN_RADIUS_TILES + ringIndex * AGENT_OVERLAP_RING_SPACING_TILES,
        spacingRadius,
    );
}

function overlapRingSlot(index: number, count: number): {
    countInRing: number;
    indexInRing: number;
    ringIndex: number;
} {
    if (count <= AGENT_OVERLAP_SINGLE_RING_LIMIT) {
        return {
            countInRing: count,
            indexInRing: index,
            ringIndex: 0,
        };
    }

    let ringIndex = 0;
    let consumed = 0;
    while (consumed < count) {
        const countInRing = Math.min(ringCapacityForIndex(ringIndex), count - consumed);
        if (index < consumed + countInRing) {
            return {
                countInRing,
                indexInRing: index - consumed,
                ringIndex,
            };
        }
        consumed += countInRing;
        ringIndex += 1;
    }

    return {
        countInRing: 1,
        indexInRing: 0,
        ringIndex,
    };
}

function visualOffsetForOverlap(index: number, count: number): VisualOffset {
    if (count <= 1) {
        return { x: 0, y: 0 };
    }
    const { countInRing, indexInRing, ringIndex } = overlapRingSlot(index, count);
    const ringAngleOffset = ringIndex > 0 ? Math.PI / countInRing : 0;
    const angle = (countInRing === 2 ? 0 : -Math.PI / 2)
        + ringAngleOffset
        + (Math.PI * 2 * indexInRing) / countInRing;
    const radius = overlapRadiusForRing(countInRing, ringIndex);
    return {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
    };
}

function applyAgentVisualOffsets(agents: PixelAgent[]): PixelAgent[] {
    const groups = new Map<string, PixelAgent[]>();
    for (const agent of agents) {
        const key = tileKey(agent.tile);
        groups.set(key, [...(groups.get(key) ?? []), agent]);
    }

    const offsets = new Map<number, VisualOffset>();
    for (const group of groups.values()) {
        const sorted = [...group].sort((a, b) => a.id - b.id);
        sorted.forEach((agent, index) => {
            offsets.set(agent.id, visualOffsetForOverlap(index, sorted.length));
        });
    }

    return agents.map((agent) => ({
        ...agent,
        visualOffset: offsets.get(agent.id) ?? { x: 0, y: 0 },
    }));
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

function describeTargetSubject(target: AskTarget, profiles: AgentProfile[], t: TFunction): string {
    const byId = new Map(profiles.map((profile) => [profile.id, profile]));
    if (target.type === 'society') {
        return t('replay.pixel.target.system');
    }
    if (target.type === 'all_agents') {
        return t('replay.pixel.target.allResidents', { count: profiles.length });
    }
    const ids = target.type === 'agent'
        ? (target.agent_id === undefined ? [] : [target.agent_id])
        : target.agent_ids ?? [];
    if (ids.length === 0) {
        return t('replay.pixel.target.none');
    }
    return ids
        .map((id) => {
            const profile = byId.get(id);
            return profile ? getAgentOptionLabel(profile) : t('replay.pixel.target.agentFallback', { id });
        })
        .join('，');
}

function describeInteractionTarget(
    target: AskTarget,
    profiles: AgentProfile[],
    mode: 'ask' | 'intervene',
    t: TFunction,
): string {
    const targetLabel = describeTargetSubject(target, profiles, t);
    return t(`replay.pixel.target.${mode}`, { target: targetLabel });
}

function escapeRegExp(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const mentionBoundary = '(?=\\s|$|[，。,.!?；;:：])';

function mentionPattern(value: string, flags = ''): RegExp {
    return new RegExp(`@${escapeRegExp(value)}${mentionBoundary}`, flags);
}

function systemMentionPattern(flags = ''): RegExp {
    return new RegExp(`@(?:系统|system)${mentionBoundary}`, flags.includes('i') ? flags : `${flags}i`);
}

function allAgentsMentionPattern(flags = ''): RegExp {
    return new RegExp(`@(?:所有居民|all_residents|all)${mentionBoundary}`, flags.includes('i') ? flags : `${flags}i`);
}

function agentIdMentionPattern(flags = ''): RegExp {
    return new RegExp(`@[^@\\n，。,.!?；;:：]*?#\\s*(\\d+)${mentionBoundary}`, flags);
}

function stripTargetMentions(text: string, mentions: LiveTargetMention[]): string {
    const withoutKnownMentions = mentions.reduce((current, mention) => (
        current.replace(mentionPattern(mention.value, 'g'), '')
    ), text);
    return withoutKnownMentions
        .replace(systemMentionPattern('gi'), '')
        .replace(allAgentsMentionPattern('gi'), '')
        .replace(agentIdMentionPattern('g'), '')
        .replace(/\s+/g, ' ')
        .trim();
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
    if (systemTarget || systemMentionPattern('i').test(text)) {
        return { type: 'society' };
    }
    const allTarget = selected.find((mention) => mention.target.type === 'all_agents');
    if (allTarget || allAgentsMentionPattern('i').test(text)) {
        return { type: 'all_agents' };
    }
    const selectedAgentIds = selected
        .map((mention) => mention.target.agent_id)
        .filter((agentId): agentId is number => typeof agentId === 'number');
    const genericAgentIds = Array.from(text.matchAll(agentIdMentionPattern('g')))
        .map((match) => Number(match[1]))
        .filter((agentId) => Number.isInteger(agentId));
    const agentIds = [...selectedAgentIds, ...genericAgentIds];
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

function formatValue(value: unknown, emptyText = '-'): string {
    if (value === undefined || value === null || value === '') {
        return emptyText;
    }
    return typeof value === 'string'
        ? value
        : typeof value === 'number' || typeof value === 'boolean'
            ? String(value)
            : JSON.stringify(value, null, 2);
}

function formatInlineFields(data: Record<string, unknown> | undefined, emptyText = '-', emptyValue = '-'): string {
    if (!data || Object.keys(data).length === 0) {
        return emptyText;
    }
    const entries = Object.entries(data).filter(([, value]) => value !== undefined && value !== null && value !== '');
    if (entries.length === 0) {
        return emptyText;
    }
    return entries
        .map(([key, value]) => `${key}: ${formatValue(value, emptyValue)}`)
        .join('\n');
}

function formatTokenUsage(tokenUsage: Record<string, TokenUsage> | undefined, t: TFunction): string {
    if (!tokenUsage || Object.keys(tokenUsage).length === 0) {
        return t('replay.pixel.drawer.tokenEmpty');
    }
    return Object.entries(tokenUsage)
        .map(([model, usage]) => (
            `${model}: ${t('replay.pixel.drawer.tokenCall')} ${usage.call_count}，${t('replay.pixel.drawer.tokenInput')} ${usage.input_tokens}，${t('replay.pixel.drawer.tokenOutput')} ${usage.output_tokens}，${t('replay.pixel.drawer.tokenTotal')} ${usage.input_tokens + usage.output_tokens}`
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

function formatStatusLabel(value: string | undefined, t: TFunction, fallback = 'idle') {
    const status = value || fallback;
    return t(`replay.pixel.status.${status}`, { defaultValue: status });
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

function spriteForAgent(index: number, walkableMap: WalkableMap): string {
    if (walkableMap.characterSprites.length > 0) {
        return walkableMap.characterSprites[index % walkableMap.characterSprites.length].name;
    }
    return CHARACTER_NAMES[index % CHARACTER_NAMES.length];
}

function buildPixelFrame(
    profiles: AgentProfile[],
    bundle: ReplayStepBundle | undefined,
    step: number,
    walkableMap: WalkableMap,
    labels: { idleAction: string; defaultLocation: string },
): PixelFrame {
    const envRow = firstEnvRow(bundle);
    const stepCommunications = parseCommunications(envRow);
    const agents = profiles.map((profile, index) => {
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
        const availableInteractions = row
            ? parseInteractionList(row.available_interactions_json)
            : [];
        return {
            id: profile.id,
            name: getAgentName(profile),
            spriteKey: spriteForAgent(index, walkableMap),
            tile: hasReplayTile ? { x: tileX, y: tileY } : fallbackTile,
            visualOffset: { x: 0, y: 0 },
            action: rawDescription ?? labels.idleAction,
            status,
            location: location ?? labels.defaultLocation,
            locationId: row ? pickDisplayValue(row, ['location_id']) : undefined,
            movementStatus: row ? pickDisplayValue(row, ['movement_status']) : undefined,
            targetLocationId: row ? pickDisplayValue(row, ['target_location_id']) : undefined,
            hasReplayTile,
            emotion,
            lastMessage,
            messageCount: pickNumberValue(row, 'message_count'),
            currentPhase: currentPhase ?? pickDisplayValue(envRow ?? {}, ['current_phase']),
            latestEvent: latestEvent ?? pickDisplayValue(envRow ?? {}, ['latest_event']),
            stepCommunications: filterAgentStepCommunications(profile.id, stepCommunications),
            availableInteractions,
        };
    });
    return {
        step,
        t: bundle?.t,
        map: walkableMap,
        agents: applyAgentVisualOffsets(agents),
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

async function loadWalkableMap(mapInfo: ReplayMapInfo, t: TFunction): Promise<WalkableMap> {
    const response = await fetchCustom(mapInfo.tiled_map_url);
    if (!response.ok) {
        throw new Error(t('replay.pixel.error.mapLoadFailed', { status: response.status, statusText: response.statusText }));
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
        throw new Error(t('replay.pixel.error.missingCollisions'));
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
        characterSprites: mapInfo.character_sprites || [],
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

function getMapZoomBounds(viewportWidth: number, viewportHeight: number, mapWidth: number, mapHeight: number) {
    const containZoom = Math.min(viewportWidth / mapWidth, viewportHeight / mapHeight);
    const coverZoom = Math.max(viewportWidth / mapWidth, viewportHeight / mapHeight);
    const minZoom = Math.max(CAMERA_MIN_ZOOM_FLOOR, containZoom);
    return {
        coverZoom,
        minZoom,
        maxZoom: Math.max(CAMERA_MAX_ZOOM, coverZoom, minZoom),
    };
}

function clampZoom(value: number, viewportWidth: number, viewportHeight: number, mapWidth: number, mapHeight: number) {
    const { minZoom, maxZoom } = getMapZoomBounds(viewportWidth, viewportHeight, mapWidth, mapHeight);
    return Phaser.Math.Clamp(value, minZoom, maxZoom);
}

function clampCameraScroll(scene: Phaser.Scene, bridge: PhaserBridge) {
    const camera = scene.cameras.main;
    if (!bridge.mapWidthPixels || !bridge.mapHeightPixels) {
        return;
    }
    camera.scrollX = camera.clampX(camera.scrollX);
    camera.scrollY = camera.clampY(camera.scrollY);
}

function fitCameraToMap(scene: Phaser.Scene, bridge: PhaserBridge) {
    const camera = scene.cameras.main;
    const mapWidth = bridge.mapWidthPixels;
    const mapHeight = bridge.mapHeightPixels;
    if (!mapWidth || !mapHeight) {
        return;
    }
    const { coverZoom } = getMapZoomBounds(camera.width, camera.height, mapWidth, mapHeight);
    const nextZoom = clampZoom(coverZoom, camera.width, camera.height, mapWidth, mapHeight);
    camera.setZoom(nextZoom);
    camera.centerOn(mapWidth / 2, mapHeight / 2);
    clampCameraScroll(scene, bridge);
}

function zoomCameraAtScreenPoint(
    scene: Phaser.Scene,
    bridge: PhaserBridge,
    screenX: number,
    screenY: number,
    delta: number,
) {
    const camera = scene.cameras.main;
    const mapWidth = bridge.mapWidthPixels;
    const mapHeight = bridge.mapHeightPixels;
    if (!mapWidth || !mapHeight) {
        return;
    }
    const before = camera.getWorldPoint(screenX, screenY);
    const nextZoom = clampZoom(camera.zoom + delta, camera.width, camera.height, mapWidth, mapHeight);
    camera.setZoom(nextZoom);
    const after = camera.getWorldPoint(screenX, screenY);
    camera.scrollX += before.x - after.x;
    camera.scrollY += before.y - after.y;
    clampCameraScroll(scene, bridge);
}

function zoomCameraAtCenter(scene: Phaser.Scene, bridge: PhaserBridge, delta: number) {
    zoomCameraAtScreenPoint(scene, bridge, scene.cameras.main.width / 2, scene.cameras.main.height / 2, delta);
}

function getAgentWorldPosition(agent: PixelAgent, tileSize: number): { x: number; y: number } {
    return {
        x: agent.tile.x * tileSize + tileSize / 2 + agent.visualOffset.x * tileSize,
        y: agent.tile.y * tileSize + tileSize / 2 + agent.visualOffset.y * tileSize,
    };
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
    const { coverZoom } = getMapZoomBounds(canvasSize.width, canvasSize.height, mapWidth, mapHeight);
    const zoom = clampZoom(coverZoom, canvasSize.width, canvasSize.height, mapWidth, mapHeight);
    const originX = canvasSize.width / 2;
    const originY = canvasSize.height / 2;
    const displayWidth = canvasSize.width / zoom;
    const displayHeight = canvasSize.height / zoom;
    const minScrollX = (displayWidth - canvasSize.width) / 2;
    const minScrollY = (displayHeight - canvasSize.height) / 2;
    const maxScrollX = Math.max(minScrollX, minScrollX + mapWidth - displayWidth);
    const maxScrollY = Math.max(minScrollY, minScrollY + mapHeight - displayHeight);
    const scrollX = Phaser.Math.Clamp(mapWidth / 2 - originX, minScrollX, maxScrollX);
    const scrollY = Phaser.Math.Clamp(mapHeight / 2 - originY, minScrollY, maxScrollY);
    const { x: worldX, y: worldY } = getAgentWorldPosition(agent, tileSize);
    const speechOffsetY = getCompactSpeechBubbleMetrics(tileSize, zoom).offsetY * zoom;
    const screenX = originX + (worldX - scrollX - originX) * zoom;
    const screenY = originY + (worldY - scrollY - originY) * zoom;
    return {
        x: screenX,
        y: screenY,
        spriteSize: tileSize * zoom,
        labelX: screenX,
        labelY: screenY - tileSize * 0.75 * zoom,
        speechX: screenX,
        speechY: screenY - speechOffsetY,
    };
}

function areAgentScreenPositionsEqual(
    current: Record<number, AgentScreenPosition>,
    next: Record<number, AgentScreenPosition>,
) {
    const currentKeys = Object.keys(current);
    const nextKeys = Object.keys(next);
    if (currentKeys.length !== nextKeys.length) {
        return false;
    }
    return nextKeys.every((key) => {
        const agentId = Number(key);
        const previous = current[agentId];
        const position = next[agentId];
        if (!previous || !position) {
            return false;
        }
        return Math.abs(previous.x - position.x) < 0.5
            && Math.abs(previous.y - position.y) < 0.5
            && Math.abs(previous.spriteSize - position.spriteSize) < 0.5
            && Math.abs(previous.labelX - position.labelX) < 0.5
            && Math.abs(previous.labelY - position.labelY) < 0.5
            && Math.abs(previous.speechX - position.speechX) < 0.5
            && Math.abs(previous.speechY - position.speechY) < 0.5;
    });
}

function projectWorldToContainer(
    scene: Phaser.Scene,
    container: HTMLDivElement,
    worldX: number,
    worldY: number,
) {
    const camera = scene.cameras.main;
    const canvasRect = scene.game.canvas.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const scaleX = canvasRect.width / Math.max(camera.width, 1);
    const scaleY = canvasRect.height / Math.max(camera.height, 1);
    const originX = camera.width * camera.originX;
    const originY = camera.height * camera.originY;
    const screenX = camera.x + originX + (worldX - camera.scrollX - originX) * camera.zoomX;
    const screenY = camera.y + originY + (worldY - camera.scrollY - originY) * camera.zoomY;
    return {
        x: canvasRect.left - containerRect.left + screenX * scaleX,
        y: canvasRect.top - containerRect.top + screenY * scaleY,
        scaleX,
        scaleY,
    };
}

function getAgentSpeechItems(agent: PixelAgent): Communication[] {
    return agent.stepCommunications;
}

function PixelAgentHoverCard({
    agent,
    frame,
}: {
    agent: PixelAgent;
    frame: PixelFrame;
}) {
    const { t } = useTranslation();
    return (
        <div className="pixel-agent-hover-card">
            <div className="pixel-agent-hover-header">
                <div className="pixel-agent-hover-title">
                    <Text strong>{agent.name}</Text>
                    <Text type="secondary">#{agent.id} · {t('replay.pixel.hover.step', { step: frame.step + 1 })}</Text>
                </div>
                <Tag className="pixel-agent-hover-status" color={agent.movementStatus === 'moving' ? 'blue' : 'green'}>
                    {formatStatusLabel(agent.movementStatus ?? agent.status, t)}
                </Tag>
            </div>

            <div className="pixel-agent-hover-grid">
                <Text type="secondary">{t('replay.pixel.hover.time')}</Text>
                <Text>{formatTime(frame.t)}</Text>
                <Text type="secondary">{t('replay.pixel.hover.action')}</Text>
                <Text>{agent.action}</Text>
                <Text type="secondary">{t('replay.pixel.hover.location')}</Text>
                <Text>
                    {agent.location}
                    {agent.locationId ? ` · ${agent.locationId}` : ''}
                </Text>
                {agent.targetLocationId && (
                    <>
                        <Text type="secondary">{t('replay.pixel.hover.target')}</Text>
                        <Text>{agent.targetLocationId}</Text>
                    </>
                )}
                {agent.emotion && (
                    <>
                        <Text type="secondary">{t('replay.pixel.hover.emotion')}</Text>
                        <Text>{agent.emotion}</Text>
                    </>
                )}
                {agent.currentPhase && (
                    <>
                        <Text type="secondary">{t('replay.pixel.hover.phase')}</Text>
                        <Text>{formatPhase(agent.currentPhase, t)}</Text>
                    </>
                )}
                {agent.latestEvent && (
                    <>
                        <Text type="secondary">{t('replay.pixel.hover.event')}</Text>
                        <Text className="pixel-agent-hover-text">{agent.latestEvent}</Text>
                    </>
                )}
                <Text type="secondary">{t('replay.pixel.hover.interactions')}</Text>
                {agent.availableInteractions.length === 0 ? (
                    <Text className="pixel-agent-hover-muted">{t('replay.pixel.hover.noInteractions')}</Text>
                ) : (
                    <div className="pixel-agent-hover-tags">
                        {agent.availableInteractions.slice(0, 4).map((interaction) => (
                            <Tag color="cyan" key={interaction.id}>{interaction.name}</Tag>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function PixelAgentSpeechBubble({
    text,
    position,
}: {
    text: string;
    position: AgentScreenPosition;
}) {
    const bubbleBottom = position.labelY - AGENT_NAME_LABEL_HEIGHT - SPEECH_BUBBLE_LABEL_GAP;

    return (
        <div
            className="pixel-agent-speech-bubble expanded"
            style={{
                left: Math.round(position.speechX),
                top: Math.round(bubbleBottom),
            }}
        >
            {text.split('\n').slice(0, 3).map((line, index) => (
                <div className="pixel-agent-speech-line" key={`${index}-${line}`}>
                    {line}
                </div>
            ))}
        </div>
    );
}

function PixelTownCanvas({
    frame,
    map,
    selectedAgentId,
    onSelectAgent,
    onOpenSetup,
    onOpenSkills,
}: {
    frame?: PixelFrame;
    map: WalkableMap;
    selectedAgentId?: number;
    onSelectAgent: (agentId: number) => void;
    onOpenSetup: () => void;
    onOpenSkills: () => void;
}) {
    const { t } = useTranslation();
    const containerRef = useRef<HTMLDivElement | null>(null);
    const gameRef = useRef<Phaser.Game | null>(null);
    const bridgeRef = useRef<PhaserBridge>({
        sprites: new Map(),
        labels: new Map(),
        hitZones: new Map(),
        speechBubbles: new Map(),
        locationMarkers: [],
    });
    const frameRef = useRef<PixelFrame | undefined>(frame);
    const onSelectAgentRef = useRef(onSelectAgent);
    const agentScreenPositionsRef = useRef<Record<number, AgentScreenPosition>>({});
    const [hoverState, setHoverState] = useState<AgentHoverState | undefined>();
    const [speechHoverAgentId, setSpeechHoverAgentId] = useState<number | undefined>();
    const [agentScreenPositions, setAgentScreenPositions] = useState<Record<number, AgentScreenPosition>>({});
    const [canvasSize, setCanvasSize] = useState<CanvasSize>({ width: 0, height: 0 });
    const hoveredAgent = frame?.agents.find((agent) => agent.id === hoverState?.agentId);
    const hoveredAgentSpeechItems = hoveredAgent ? getAgentSpeechItems(hoveredAgent) : [];
    const speechHoverAgent = frame?.agents.find((agent) => agent.id === speechHoverAgentId);
    const speechHoverText = speechHoverAgent ? getSpeechText(speechHoverAgent) : '';
    const speechHoverPosition = speechHoverAgent
        ? agentScreenPositions[speechHoverAgent.id] ?? getFitScreenPosition(speechHoverAgent, map, canvasSize)
        : undefined;

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

    const readAgentScreenPosition = useCallback((agentId: number): AgentScreenPosition | undefined => {
        const scene = bridgeRef.current.scene;
        const currentFrame = frameRef.current;
        const container = containerRef.current;
        if (!scene || !currentFrame || !container) {
            return undefined;
        }
        const agent = currentFrame.agents.find((item) => item.id === agentId);
        if (!agent) {
            return undefined;
        }
        const camera = scene.cameras.main;
        const tileSize = currentFrame.map.tileSize || TILE_SIZE;
        const sprite = bridgeRef.current.sprites.get(agentId);
        const agentPosition = getAgentWorldPosition(agent, tileSize);
        const worldX = sprite?.x ?? agentPosition.x;
        const worldY = sprite?.y ?? agentPosition.y;
        const label = bridgeRef.current.labels.get(agentId);
        const speechBubble = bridgeRef.current.speechBubbles.get(agentId);
        const { offsetY } = getCompactSpeechBubbleMetrics(tileSize, camera.zoom);
        const screenPosition = projectWorldToContainer(scene, container, worldX, worldY);
        const labelPosition = projectWorldToContainer(
            scene,
            container,
            label?.x ?? worldX,
            label?.y ?? worldY - tileSize * 0.75,
        );
        const speechPosition = projectWorldToContainer(
            scene,
            container,
            speechBubble?.bubble.x ?? worldX,
            speechBubble?.bubble.y ?? worldY - offsetY,
        );
        return {
            x: screenPosition.x,
            y: screenPosition.y,
            spriteSize: (sprite?.displayHeight ?? tileSize) * camera.zoom * screenPosition.scaleY,
            labelX: labelPosition.x,
            labelY: labelPosition.y,
            speechX: speechPosition.x,
            speechY: speechPosition.y,
        };
    }, []);

    const syncAgentScreenPositions = useCallback(() => {
        const scene = bridgeRef.current.scene;
        const currentFrame = frameRef.current;
        if (!scene || !currentFrame) {
            if (Object.keys(agentScreenPositionsRef.current).length > 0) {
                agentScreenPositionsRef.current = {};
                setAgentScreenPositions({});
            }
            return;
        }
        syncCompactSpeechBubbles(bridgeRef.current, currentFrame);
        const next: Record<number, AgentScreenPosition> = {};
        currentFrame.agents.forEach((agent) => {
            const position = readAgentScreenPosition(agent.id);
            if (position) {
                next[agent.id] = position;
            }
        });
        if (!areAgentScreenPositionsEqual(agentScreenPositionsRef.current, next)) {
            agentScreenPositionsRef.current = next;
            setAgentScreenPositions(next);
        }
    }, [readAgentScreenPosition]);

    const showSpeechBubbleForAgent = useCallback((agentId: number | undefined) => {
        const bridge = bridgeRef.current;
        if (bridge.hoveredSpeechAgentId !== undefined && bridge.hoveredSpeechAgentId !== agentId) {
            setCompactSpeechBubbleVisible(bridge.speechBubbles.get(bridge.hoveredSpeechAgentId), true);
        }
        bridge.hoveredSpeechAgentId = agentId;
        if (agentId === undefined) {
            return;
        }
        setCompactSpeechBubbleVisible(bridge.speechBubbles.get(agentId), false);
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
            setSpeechHoverAgentId(undefined);
            showSpeechBubbleForAgent(undefined);
            return;
        }
        const immediatePosition = readAgentScreenPosition(agentId);
        if (immediatePosition) {
            setAgentScreenPositions((current) => ({
                ...current,
                [agentId]: immediatePosition,
            }));
        }
        syncAgentScreenPositions();
        showSpeechBubbleForAgent(agentId);
        const [x, y] = clampHoverPosition(pointer.x, pointer.y);
        setSpeechHoverAgentId(agentId);
        setHoverState({ agentId, x, y });
    }, [clampHoverPosition, readAgentScreenPosition, showSpeechBubbleForAgent, syncAgentScreenPositions]);

    const handleDomHoverAgent = useCallback((agentId: number, event: React.MouseEvent<HTMLDivElement>) => {
        const bounds = containerRef.current?.getBoundingClientRect();
        if (!bounds) {
            return;
        }
        const immediatePosition = readAgentScreenPosition(agentId);
        if (immediatePosition) {
            setAgentScreenPositions((current) => ({
                ...current,
                [agentId]: immediatePosition,
            }));
        }
        syncAgentScreenPositions();
        showSpeechBubbleForAgent(agentId);
        const [x, y] = clampHoverPosition(
            event.clientX - bounds.left,
            event.clientY - bounds.top,
        );
        setSpeechHoverAgentId(agentId);
        setHoverState({ agentId, x, y });
    }, [clampHoverPosition, readAgentScreenPosition, showSpeechBubbleForAgent, syncAgentScreenPositions]);

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
                if (map.characterSprites.length > 0) {
                    map.characterSprites.forEach((sprite) => {
                        this.load.spritesheet(sprite.name, sprite.image_url, {
                            frameWidth: sprite.frame_width || map.tileSize || TILE_SIZE,
                            frameHeight: sprite.frame_height || map.tileSize || TILE_SIZE,
                        });
                    });
                } else {
                    CHARACTER_NAMES.forEach((name) => {
                        this.load.spritesheet(name, `${CHARACTER_ROOT}/${name}.png`, {
                            frameWidth: TILE_SIZE,
                            frameHeight: TILE_SIZE,
                        });
                    });
                }
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
                    clampCameraScroll(this, bridgeRef.current);
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
                    zoomCameraAtScreenPoint(this, bridgeRef.current, pointer.x, pointer.y, dy > 0 ? -0.06 : 0.06);
                    syncAgentScreenPositions();
                });
                this.scale.on('resize', () => {
                    fitCameraToMap(this, bridgeRef.current);
                    syncAgentScreenPositions();
                });
                this.input.keyboard?.createCursorKeys();
                renderFrame(this, frameRef.current, bridgeRef.current, onSelectAgentRef.current, handleHoverAgent);
                syncAgentScreenPositions();
                this.events.on(Phaser.Scenes.Events.POST_UPDATE, syncAgentScreenPositions);
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
            agentScreenPositionsRef.current = {};
            bridgeRef.current = {
                sprites: new Map(),
                labels: new Map(),
                hitZones: new Map(),
                speechBubbles: new Map(),
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
        if (speechHoverAgentId !== undefined && !frame?.agents.some((agent) => agent.id === speechHoverAgentId)) {
            setSpeechHoverAgentId(undefined);
            showSpeechBubbleForAgent(undefined);
        }
    }, [frame, showSpeechBubbleForAgent, speechHoverAgentId]);

    useEffect(() => {
        if (!frame) {
            agentScreenPositionsRef.current = {};
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
        let attempts = 0;
        const timer = window.setInterval(() => {
            syncAgentScreenPositions();
            attempts += 1;
            if (attempts >= 8) {
                window.clearInterval(timer);
            }
        }, 80);
        return () => window.clearInterval(timer);
    }, [selectedAgentId, syncAgentScreenPositions]);

    return (
        <div className="pixel-town-canvas" ref={containerRef}>
            <div className="pixel-canvas-controls">
                <Tooltip title={t('replay.pixel.canvas.resetFit', { map: map.displayName })}>
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
                <Tooltip title={t('replay.pixel.canvas.zoomIn')}>
                    <Button
                        shape="circle"
                        icon={<ZoomInOutlined />}
                        onClick={() => {
                            if (bridgeRef.current.scene) {
                                zoomCameraAtCenter(bridgeRef.current.scene, bridgeRef.current, 0.1);
                                syncAgentScreenPositions();
                            }
                        }}
                    />
                </Tooltip>
                <Tooltip title={t('replay.pixel.canvas.zoomOut')}>
                    <Button
                        shape="circle"
                        icon={<ZoomOutOutlined />}
                        onClick={() => {
                            if (bridgeRef.current.scene) {
                                zoomCameraAtCenter(bridgeRef.current.scene, bridgeRef.current, -0.1);
                                syncAgentScreenPositions();
                            }
                        }}
                    />
                </Tooltip>
            </div>
            <div className="pixel-canvas-actions">
                <Tooltip title={t('replay.pixel.canvas.newExperimentTooltip')}>
                    <Button icon={<SettingOutlined />} onClick={onOpenSetup}>
                        {t('replay.pixel.canvas.newExperiment')}
                    </Button>
                </Tooltip>
                <Tooltip title={t('replay.pixel.canvas.skillsTooltip')}>
                    <Button icon={<ThunderboltOutlined />} onClick={onOpenSkills}>
                        {t('replay.pixel.canvas.skills')}
                    </Button>
                </Tooltip>
            </div>
            {frame?.agents.map((agent) => {
                const position = agentScreenPositions[agent.id] ?? getFitScreenPosition(agent, map, canvasSize);
                if (!position) {
                    return null;
                }
                return (
                    <div
                        className="pixel-agent-name-label"
                        key={`label-${agent.id}`}
                        style={{
                            left: Math.round(position.labelX),
                            top: Math.round(position.labelY),
                        }}
                    >
                        {agent.name}
                    </div>
                );
            })}
            {speechHoverAgent
                && speechHoverText
                && speechHoverPosition ? (
                <PixelAgentSpeechBubble text={speechHoverText} position={speechHoverPosition} />
            ) : null}
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
                        onMouseLeave={() => {
                            setHoverState(undefined);
                            setSpeechHoverAgentId(undefined);
                            showSpeechBubbleForAgent(undefined);
                        }}
                    />
                );
            })}
            {hoverState && hoveredAgent && frame && hoveredAgentSpeechItems.length === 0 && (
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

function destroySpeechBubble(bridge: PhaserBridge, agentId: number) {
    const speechBubble = bridge.speechBubbles.get(agentId);
    if (!speechBubble) {
        return;
    }
    speechBubble.bubble.destroy();
    speechBubble.text.destroy();
    speechBubble.hitZone.destroy();
    bridge.speechBubbles.delete(agentId);
}

function setCompactSpeechBubbleVisible(speechBubble: PhaserSpeechBubble | undefined, visible: boolean) {
    speechBubble?.bubble.setVisible(visible);
    speechBubble?.text.setVisible(visible);
}

function drawCompactSpeechBubble(bubble: Phaser.GameObjects.Graphics, tileSize: number) {
    const width = tileSize * 0.9;
    const height = tileSize * 0.52;
    const radius = height / 2;
    const tailWidth = tileSize * 0.18;
    const tailHeight = tileSize * 0.16;
    const tailY = height / 2 - 1;

    bubble.clear();
    bubble.fillStyle(0xffffff, 0.96);
    bubble.lineStyle(Math.max(1, tileSize * 0.045), 0x111827, 0.95);
    bubble.fillRoundedRect(-width / 2, -height / 2, width, height, radius);
    bubble.strokeRoundedRect(-width / 2, -height / 2, width, height, radius);
    bubble.fillTriangle(-tailWidth / 2, tailY, 0, tailY + tailHeight, tailWidth / 2, tailY);
    bubble.strokeTriangle(-tailWidth / 2, tailY, 0, tailY + tailHeight, tailWidth / 2, tailY);
}

function getCompactSpeechBubbleMetrics(tileSize: number, zoom: number) {
    const baseWidth = tileSize * 0.9;
    const baseHeight = tileSize * 0.52;
    const tailHeight = tileSize * 0.16;
    const desiredScreenWidth = Phaser.Math.Clamp(tileSize * zoom * 1.25, 14, 26);
    const scale = desiredScreenWidth / Math.max(1, baseWidth * zoom);
    const safeZoom = Math.max(zoom, 0.01);
    const bubbleBottomOffset = ((baseHeight / 2 - 1) + tailHeight) * scale;
    const labelTopOffset = tileSize * 0.75 + (AGENT_NAME_LABEL_HEIGHT + SPEECH_BUBBLE_LABEL_GAP) / safeZoom;
    const offsetY = labelTopOffset + bubbleBottomOffset;
    return { scale, offsetY };
}

function getTextResolution() {
    return typeof window === 'undefined'
        ? 4
        : Phaser.Math.Clamp((window.devicePixelRatio || 2) * 2, 4, 6);
}

function snapWorldToScreenPixel(scene: Phaser.Scene, x: number, y: number): { x: number; y: number } {
    const camera = scene.cameras.main;
    const zoom = Math.max(camera.zoom, 0.01);
    const originX = camera.width * camera.originX;
    const originY = camera.height * camera.originY;
    const screenX = camera.x + originX + (x - camera.scrollX - originX) * zoom;
    const screenY = camera.y + originY + (y - camera.scrollY - originY) * zoom;
    return {
        x: (Math.round(screenX) - camera.x - originX) / zoom + camera.scrollX + originX,
        y: (Math.round(screenY) - camera.y - originY) / zoom + camera.scrollY + originY,
    };
}

function applyReadableAgentLabelStyle(label: Phaser.GameObjects.Text, zoom: number) {
    const safeZoom = Math.max(zoom, 0.01);
    label.setStyle({
        fontFamily: PHASER_TEXT_FONT_FAMILY,
        fontSize: `${10.5 / safeZoom}px`,
        color: '#ffffff',
        backgroundColor: 'rgba(17, 24, 39, 0.9)',
        stroke: '#111827',
        strokeThickness: 0.75 / safeZoom,
        padding: { x: 4 / safeZoom, y: 2 / safeZoom },
        resolution: getTextResolution(),
    });
}

function applyCompactSpeechBubbleMetrics(
    speechBubble: PhaserSpeechBubble,
    tileSize: number,
    zoom: number,
) {
    const { scale } = getCompactSpeechBubbleMetrics(tileSize, zoom);
    speechBubble.bubble.setScale(scale);
    speechBubble.text.setScale(scale);
    speechBubble.hitZone.setScale(scale);
}

function syncCompactSpeechBubbles(bridge: PhaserBridge, frame: PixelFrame) {
    const scene = bridge.scene;
    if (!scene) {
        return;
    }
    const tileSize = frame.map.tileSize || TILE_SIZE;
    const zoom = scene.cameras.main.zoom;
    for (const agent of frame.agents) {
        const label = bridge.labels.get(agent.id);
        const speechBubble = bridge.speechBubbles.get(agent.id);
        const sprite = bridge.sprites.get(agent.id);
        if (!sprite) {
            continue;
        }
        if (label) {
            applyReadableAgentLabelStyle(label, zoom);
            const labelPosition = snapWorldToScreenPixel(scene, sprite.x, sprite.y - tileSize * 0.75);
            label.setPosition(labelPosition.x, labelPosition.y);
        }
        if (!speechBubble) {
            continue;
        }
        const { offsetY } = getCompactSpeechBubbleMetrics(tileSize, zoom);
        applyCompactSpeechBubbleMetrics(speechBubble, tileSize, zoom);
        const speechPosition = snapWorldToScreenPixel(scene, sprite.x, sprite.y - offsetY);
        speechBubble.bubble.setPosition(speechPosition.x, speechPosition.y);
        speechBubble.text.setPosition(speechPosition.x, speechPosition.y - tileSize * 0.02);
        speechBubble.hitZone.setPosition(speechPosition.x, speechPosition.y);
    }
    if (bridge.hoveredSpeechAgentId !== undefined) {
        setCompactSpeechBubbleVisible(bridge.speechBubbles.get(bridge.hoveredSpeechAgentId), false);
    }
}

function getSpeechText(agent: PixelAgent): string {
    return getAgentSpeechItems(agent)
        .slice(0, 3)
        .map((item) => item.content?.trim())
        .filter((content): content is string => Boolean(content))
        .join('\n');
}

function ensureCompactSpeechBubble(
    scene: Phaser.Scene,
    bridge: PhaserBridge,
    agent: PixelAgent,
    x: number,
    y: number,
    tileSize: number,
    onSelectAgent: (agentId: number) => void,
    onHoverAgent: (agentId: number | undefined, pointer?: Phaser.Input.Pointer) => void,
): PhaserSpeechBubble {
    let speechBubble = bridge.speechBubbles.get(agent.id);
    if (speechBubble) {
        return speechBubble;
    }
    const bubble = scene.add.graphics({ x, y });
    bubble.setDepth(34);
    drawCompactSpeechBubble(bubble, tileSize);

    const text = scene.add.text(x, y - tileSize * 0.02, '...', {
        fontFamily: PHASER_TEXT_FONT_FAMILY,
        fontSize: `${Math.max(7, tileSize * 0.24)}px`,
        color: '#111827',
        resolution: getTextResolution(),
    });
    text.setOrigin(0.5, 0.5);
    text.setDepth(35);

    const hitZone = scene.add.zone(x, y, tileSize * 1.1, tileSize * 0.9);
    hitZone.setDepth(46);
    hitZone.setInteractive({ useHandCursor: true });
    hitZone.on('pointerdown', () => onSelectAgent(agent.id));
    hitZone.on('pointerover', (pointer: Phaser.Input.Pointer) => onHoverAgent(agent.id, pointer));
    hitZone.on('pointermove', (pointer: Phaser.Input.Pointer) => onHoverAgent(agent.id, pointer));
    hitZone.on('pointerout', () => onHoverAgent(undefined));

    speechBubble = { bubble, text, hitZone };
    bridge.speechBubbles.set(agent.id, speechBubble);
    return speechBubble;
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
            destroySpeechBubble(bridge, agentId);
        }
    }

    frame.agents.forEach((agent) => {
        const tileSize = frame.map.tileSize || TILE_SIZE;
        const { x, y } = getAgentWorldPosition(agent, tileSize);
        let sprite = bridge.sprites.get(agent.id);
        let label = bridge.labels.get(agent.id);
        let hitZone = bridge.hitZones.get(agent.id);
        let speechBubble: PhaserSpeechBubble | undefined;
        const hasSpeech = getAgentSpeechItems(agent).length > 0;
        const speechMetrics = getCompactSpeechBubbleMetrics(tileSize, scene.cameras.main.zoom);
        const speechY = y - speechMetrics.offsetY;

        if (!sprite) {
            sprite = scene.add.sprite(x, y, agent.spriteKey, 1);
            sprite.setDepth(10);
            bridge.sprites.set(agent.id, sprite);
        }
        sprite.setDepth(10 + y / 10000);
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
                fontFamily: PHASER_TEXT_FONT_FAMILY,
                fontSize: '10.5px',
                color: '#ffffff',
                backgroundColor: 'rgba(17, 24, 39, 0.9)',
                padding: { x: 4, y: 2 },
                resolution: getTextResolution(),
            });
            label.setOrigin(0.5, 1);
            label.setDepth(30);
            bridge.labels.set(agent.id, label);
        }
        applyReadableAgentLabelStyle(label, scene.cameras.main.zoom);
        label.setVisible(false);
        if (hasSpeech) {
            speechBubble = ensureCompactSpeechBubble(
                scene,
                bridge,
                agent,
                x,
                speechY,
                tileSize,
                onSelectAgent,
                onHoverAgent,
            );
            drawCompactSpeechBubble(speechBubble.bubble, tileSize);
            applyCompactSpeechBubbleMetrics(speechBubble, tileSize, scene.cameras.main.zoom);
        } else {
            destroySpeechBubble(bridge, agent.id);
        }

        const duration = Math.hypot(sprite.x - x, sprite.y - y) > 1 ? 240 : 0;
        scene.tweens.killTweensOf([
            sprite,
            label,
            hitZone,
            speechBubble?.bubble,
            speechBubble?.text,
            speechBubble?.hitZone,
        ].filter(Boolean));
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
        if (speechBubble) {
            scene.tweens.add({
                targets: [speechBubble.bubble, speechBubble.hitZone],
                x,
                y: speechY,
                duration,
                ease: 'Linear',
            });
            scene.tweens.add({
                targets: speechBubble.text,
                x,
                y: speechY - tileSize * 0.02,
                duration,
                ease: 'Linear',
            });
        }
        label.setText(agent.name);
        label.setVisible(false);
    });

    updateSelection(bridge);
}

function updateSelection(bridge: PhaserBridge) {
    for (const [agentId, sprite] of bridge.sprites.entries()) {
        const selected = agentId === bridge.selectedId;
        sprite.setTint(selected ? 0xfff1a8 : 0xffffff);
        sprite.setScale(selected ? AGENT_SPRITE_SELECTED_SCALE : AGENT_SPRITE_BASE_SCALE);
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
    const { t } = useTranslation();
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
                        const loadedMap = await loadWalkableMap(mapInfo, t);
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
                            setLoadingDetail(t('replay.pixel.loading.retry', { attempt, error: toErrorMessage(err) }));
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
                                result: t('replay.pixel.live.callFailed', { error: payload.message ?? t('replay.pixel.live.commandNotCompleted') }),
                            };
                        }
                        return next;
                    });
                }
                if (payload.type === 'error') {
                    messageApi.error(payload.message ?? t('replay.pixel.live.executionFailed'));
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
            value: t('replay.pixel.target.systemMentionValue'),
            label: `@${t('replay.pixel.target.systemMentionValue')}`,
            target: { type: 'society' },
        },
        {
            value: t('replay.pixel.target.allResidentsMentionValue'),
            label: `@${t('replay.pixel.target.allResidentsMentionValue')}`,
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
    ], [profiles, t]);

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

    const promptTargetLabel = describeInteractionTarget(promptTarget, profiles, liveMode, t);

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
            targetLabel: describeInteractionTarget(target, profiles, liveMode, t),
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
            messageApi.success(response.artifact_name ? t('replay.pixel.live.resultSaved', { name: response.artifact_name }) : t('replay.pixel.live.commandDone'));
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : String(err);
            setLiveInteractions((items) => items.map((item) => (
                item.id === pending.id
                    ? { ...item, result: t('replay.pixel.live.callFailed', { error: errorMessage }) }
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
    }, [askTarget, liveBaseUrl, liveMode, livePrompt, liveTargetMentions, messageApi, profiles, promptTargetReady, t, withLiveWorkspace]);

    const frame = useMemo(() => {
        if (!walkableMap) {
            return undefined;
        }
        return buildPixelFrame(profiles, bundle, currentStep, walkableMap, {
            idleAction: formatStatusLabel(undefined, t),
            defaultLocation: walkableMap.displayName,
        });
    }, [bundle, currentStep, profiles, t, walkableMap]);

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
                    <Text>{t('replay.pixel.loading.text')}</Text>
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
                    message={t('replay.pixel.error.title')}
                    description={error}
                />
            </div>
        );
    }

    if (!frame) {
        return (
            <div className="pixel-replay-error">
                <Empty description={t('replay.pixel.error.empty')} />
            </div>
        );
    }

    return (
        <div className="pixel-replay-page">
            {messageContextHolder}
            <PixelTownCanvas
                key={frame.map.mapId}
                frame={frame}
                map={frame.map}
                selectedAgentId={selectedAgentId}
                onSelectAgent={setSelectedAgentId}
                onOpenSetup={() => navigate('/setup')}
                onOpenSkills={() => navigate('/skills')}
            />

            <Card className="pixel-replay-topbar" variant="borderless">
                <Space align="center" wrap>
                    <Button
                        icon={playing ? <PauseOutlined /> : <CaretRightOutlined />}
                        type="primary"
                        onClick={() => setPlaying((value) => !value)}
                    >
                        {playing ? t('replay.pixel.topbar.pause') : t('replay.pixel.topbar.play')}
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
                            {t('replay.pixel.topbar.runStep')}
                        </Button>
                        <Button
                            icon={liveAuto ? <PauseOutlined /> : <CaretRightOutlined />}
                            loading={liveBusy && !liveAuto}
                            disabled={liveBusy || (!liveAuto && !liveWaiting)}
                            onClick={toggleLiveAuto}
                        >
                            {liveAuto ? t('replay.pixel.topbar.pauseAuto') : t('replay.pixel.topbar.auto')}
                        </Button>
                        <Button
                            disabled
                            className={`pixel-live-status-button status-${liveStatus?.status ?? 'offline'}`}
                        >
                            {formatStatusLabel(liveStatus?.status, t, 'offline')}
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
                    <Tag color="blue">{t('replay.pixel.topbar.stepTag', { step: currentStep + 1 })}</Tag>
                    {liveStatus && <Tag color="geekblue">{t('replay.pixel.topbar.liveSteps', { count: liveStatus.step_count })}</Tag>}
                    <Text>{formatTime(bundle?.t ?? timeline[currentIndex]?.t)}</Text>
                    {stepLoading && <Spin size="small" />}
                    <LanguageToggle />
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
                    <Title level={4}>{t('replay.pixel.overview.title')}</Title>
                    <Text type="secondary">
                        {t('replay.pixel.overview.subtitle', { hypothesis: effectiveHypothesisId, experiment: effectiveExperimentId })}
                    </Text>
                    <div className="pixel-replay-stats">
                        <Tag>{t('replay.pixel.overview.residents', { count: info?.agent_count ?? profiles.length })}</Tag>
                        <Tag>{t('replay.pixel.overview.steps', { count: info?.total_steps ?? timeline.length })}</Tag>
                        <Tag color="geekblue">{frame.map.displayName}</Tag>
                        {envSnapshot?.total_messages_sent !== undefined && (
                            <Tag color="green">{t('replay.pixel.overview.messages', { count: Number(envSnapshot.total_messages_sent) || 0 })}</Tag>
                        )}
                        <Tag color={communications.length > 0 ? 'blue' : undefined}>
                            {t('replay.pixel.overview.communications', { count: communications.length })}
                        </Tag>
                        {missingReplayTileCount > 0 && (
                            <Tag color="orange">{t('replay.pixel.overview.missingTiles', { count: missingReplayTileCount })}</Tag>
                        )}
                    </div>
                </Card>

                <Card className="pixel-panel pixel-step-card" variant="borderless">
                    <div className="pixel-panel-content pixel-step-content">
                        <div className="pixel-section-heading">
                            <Text strong>{t('replay.pixel.step.title')}</Text>
                            <Tag color="blue">{t('replay.pixel.step.tag', { step: currentStep + 1 })}</Tag>
                        </div>
                        <div className="pixel-step-summary">
                            <Text type="secondary">{t('replay.pixel.step.phase')}</Text>
                            <Text strong>{formatPhase(envSnapshot?.current_phase, t)}</Text>
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
                        <Text strong>{t('replay.pixel.chat.title')}</Text>
                        <Tag color={communications.length > 0 ? 'blue' : undefined}>
                            {t('replay.pixel.chat.count', { count: communications.length })}
                        </Tag>
                    </div>
                    <div className="pixel-communication-list">
                        {communications.length === 0 ? (
                            <Text type="secondary">{t('replay.pixel.chat.empty')}</Text>
                        ) : communications.map((item, index) => (
                            <div className="pixel-communication-row" key={`${item.sender_name}-${index}`}>
                                <div className="pixel-communication-meta">
                                    <Text strong>{item.sender_name ?? t('replay.pixel.chat.resident')}</Text>
                                    <Tag color={item.type === 'direct' ? 'purple' : 'cyan'}>
                                        {item.type === 'direct' ? t('replay.pixel.chat.direct') : t('replay.pixel.chat.group')}
                                    </Tag>
                                </div>
                                <Text type="secondary">
                                    {item.type === 'direct'
                                        ? t('replay.pixel.chat.sendTo', { name: item.receiver_name ?? t('replay.pixel.chat.resident') })
                                        : t('replay.pixel.chat.sendToGroup', {
                                            name: item.group_name ?? t('replay.pixel.chat.group'),
                                            suffix: item.recipient_count ? t('replay.pixel.chat.recipientCount', { count: item.recipient_count }) : '',
                                        })}
                                </Text>
                                <Text className="pixel-message-text">{item.content ?? ''}</Text>
                            </div>
                        ))}
                    </div>
                </Card>

                <Card className="pixel-panel pixel-residents-card" variant="borderless">
                    <div className="pixel-section-heading">
                        <Space direction="vertical" size={0}>
                            <Text strong>{t('replay.pixel.residents.title')}</Text>
                            <Text type="secondary">{t('replay.pixel.residents.hint')}</Text>
                        </Space>
                        <Button
                            size="small"
                            type="primary"
                            ghost
                            icon={<UserAddOutlined />}
                            onClick={() => setAgentBuilderOpen(true)}
                        >
                            {t('replay.pixel.residents.addAgent')}
                        </Button>
                    </div>
                    {selectedAgent && (
                        <div className="pixel-replay-selected">
                            <Text type="secondary">{t('replay.pixel.residents.selected')}</Text>
                            <Text strong>{selectedAgent.name}</Text>
                            <Text>{selectedAgent.action}</Text>
                            <Text type="secondary">{t('replay.pixel.residents.location', { location: selectedAgent.location })}</Text>
                            <Space size={4} wrap>
                                {selectedAgent.locationId && <Tag>{selectedAgent.locationId}</Tag>}
                                {selectedAgent.movementStatus && (
                                    <Tag color={selectedAgent.movementStatus === 'moving' ? 'blue' : 'green'}>
                                        {formatStatusLabel(selectedAgent.movementStatus, t)}
                                    </Tag>
                                )}
                                <Tag color={selectedAgent.hasReplayTile ? 'geekblue' : 'orange'}>
                                    {t('replay.pixel.residents.tile', { x: selectedAgent.tile.x, y: selectedAgent.tile.y })}
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
                            {selectedAgent.emotion && <Text type="secondary">{t('replay.pixel.residents.emotion', { emotion: selectedAgent.emotion })}</Text>}
                            {selectedAgent.lastMessage && (
                                <Text className="pixel-message-text">{t('replay.pixel.residents.lastReceived', { message: selectedAgent.lastMessage })}</Text>
                            )}
                            <Space size={8} wrap>
                                <Button
                                    size="small"
                                    type="link"
                                    onClick={() => setAgentDetailOpen(true)}
                                >
                                    {t('replay.pixel.residents.viewDetail')}
                                </Button>
                                <Button
                                    size="small"
                                    type="link"
                                    onClick={clearSelectedAgent}
                                >
                                    {t('replay.pixel.residents.clearSelection')}
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
                                    {agent.hasReplayTile
                                        ? t('replay.pixel.residents.tile', { x: agent.tile.x, y: agent.tile.y })
                                        : t('replay.pixel.residents.missingCoords')}
                                </span>
                                {agent.lastMessage && <span className="pixel-agent-location">{t('replay.pixel.residents.lastReceived', { message: agent.lastMessage })}</span>}
                            </div>
                        ))}
                    </div>
                </Card>
            </div>
            <Card className="pixel-live-console" variant="borderless">
                <div className="pixel-live-console-header">
                    <Space size={8} wrap>
                        <Text strong>{t('replay.pixel.live.title')}</Text>
                        <Tag color={liveMode === 'ask' ? 'blue' : 'orange'}>
                            {liveMode === 'ask' ? t('replay.pixel.live.ask') : t('replay.pixel.live.intervene')}
                        </Tag>
                        <Tag>{promptTargetLabel}</Tag>
                    </Space>
                    <Text type="secondary">
                        {liveWaiting
                            ? t('replay.pixel.live.inputHint')
                            : t('replay.pixel.live.status', { status: formatStatusLabel(liveStatus?.status, t, 'offline') })}
                    </Text>
                </div>
                <div className="pixel-live-result-stream">
                    {liveInteractions.length === 0 ? (
                        <div className="pixel-live-empty">
                            <Text type="secondary">{t('replay.pixel.live.empty')}</Text>
                        </div>
                    ) : liveInteractions.slice().reverse().slice(0, 4).map((item) => (
                        <div className="pixel-live-result-card" key={item.id}>
                            <div className="pixel-communication-meta">
                                <Space size={6} wrap>
                                    <Tag color={item.type === 'ask' ? 'blue' : 'orange'}>
                                        {item.type === 'ask' ? t('replay.pixel.live.ask') : t('replay.pixel.live.intervene')}
                                    </Tag>
                                    {item.targetLabel && <Tag>{item.targetLabel}</Tag>}
                                </Space>
                                {item.artifactName && <Text type="secondary">{item.artifactName}</Text>}
                            </div>
                            <Text strong className="pixel-live-prompt">{item.prompt}</Text>
                            <Text className="pixel-live-result-text">
                                {item.result ?? t('replay.pixel.live.waitingResult')}
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
                                { label: t('replay.pixel.live.ask'), value: 'ask' },
                                { label: t('replay.pixel.live.intervene'), value: 'intervene' },
                            ]}
                        />
                        <Text type="secondary" className="pixel-live-target-hint">
                            {liveMode === 'ask'
                                ? describeInteractionTarget(promptTarget, profiles, 'ask', t)
                                : `${describeInteractionTarget(promptTarget, profiles, 'intervene', t)} - ${t('replay.pixel.live.nextStepNote')}`}
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
                            ? t('replay.pixel.live.askPlaceholder')
                            : t('replay.pixel.live.intervenePlaceholder')}
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
                        {t('replay.pixel.live.send')}
                    </Button>
                </div>
            </Card>
            <Drawer
                title={selectedAgent ? t('replay.pixel.drawer.detailTitle', { name: selectedAgent.name }) : t('replay.pixel.drawer.detailTitleFallback')}
                open={agentDetailOpen && Boolean(selectedAgent)}
                onClose={() => setAgentDetailOpen(false)}
                width="min(520px, 92vw)"
                mask={false}
                destroyOnHidden
            >
                {selectedAgent && (
                    <div className="pixel-agent-detail-drawer-content">
                        <div className="pixel-replay-selected compact">
                            <Text type="secondary">{t('replay.pixel.drawer.selectedResident')}</Text>
                            <Text strong>{selectedAgent.name}</Text>
                            <Text>{selectedAgent.action}</Text>
                            <Text type="secondary">{t('replay.pixel.residents.location', { location: selectedAgent.location })}</Text>
                            <Space size={4} wrap>
                                {selectedAgent.locationId && <Tag>{selectedAgent.locationId}</Tag>}
                                {selectedAgent.movementStatus && (
                                    <Tag color={selectedAgent.movementStatus === 'moving' ? 'blue' : 'green'}>
                                        {formatStatusLabel(selectedAgent.movementStatus, t)}
                                    </Tag>
                                )}
                                <Tag color={selectedAgent.hasReplayTile ? 'geekblue' : 'orange'}>
                                    {t('replay.pixel.residents.tile', { x: selectedAgent.tile.x, y: selectedAgent.tile.y })}
                                </Tag>
                            </Space>
                        </div>
                        {agentRuntimeLoadingId === selectedAgent.id && (
                            <Space>
                                <Spin size="small" />
                                <Text type="secondary">{t('replay.pixel.drawer.loadingStatus')}</Text>
                            </Space>
                        )}
                        {renderPlainDetail(t('replay.pixel.drawer.tokenUsage'), formatTokenUsage(selectedAgentRuntime?.token_usage, t))}
                        {renderPlainDetail(t('replay.pixel.drawer.currentStatus'), formatInlineFields(selectedAgentSummary, t('replay.pixel.drawer.noStatus')))}
                        {renderPlainDetail(
                            t('replay.pixel.drawer.interactions'),
                            selectedAgent.availableInteractions.length > 0
                                ? selectedAgent.availableInteractions.map((interaction) => `${interaction.name} (${interaction.id}): ${interaction.description ?? ''}`).join('\n')
                                : t('replay.pixel.drawer.noInteractions'),
                        )}
                        {renderPlainDetail(t('replay.pixel.drawer.profile'), formatInlineFields(selectedProfile?.profile ?? selectedSnapshotProfile, t('replay.pixel.drawer.noProfile')))}
                        {renderPlainDetail(t('replay.pixel.drawer.skillRuntime'), formatInlineFields(selectedSkillRuntimeSummary, t('replay.pixel.drawer.noSkillRuntime')))}
                        {renderPlainDetail(t('replay.pixel.drawer.sessionState'), joinDetailBlocks([
                            ['session_state', formatInlineFields(selectedAgentRuntime?.session_state, t('replay.pixel.drawer.noSessionState'))],
                            ['agent_state_snapshot', formatInlineFields(selectedAgentSnapshot, t('replay.pixel.drawer.noSnapshot'))],
                            ['skill_states', formatInlineFields(selectedSkillStates, t('replay.pixel.drawer.noSkillStates'))],
                        ]))}
                    </div>
                )}
            </Drawer>
            <Drawer
                title={t('replay.pixel.drawer.agentConfig')}
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
                            ? t('replay.pixel.drawer.hotLoadReady')
                            : t('replay.pixel.drawer.hotLoadPending')}
                        description={liveStatus.status === 'waiting'
                            ? t('replay.pixel.drawer.hotLoadReadyDescription')
                            : t('replay.pixel.drawer.hotLoadPendingDescription')}
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
                                messageApi.success(t('replay.pixel.drawer.hotLoadSuccess', { count: result.added_agent_ids.length }));
                            }
                        } else if (liveStatus && liveStatus.status !== 'waiting') {
                            messageApi.warning(t('replay.pixel.drawer.hotLoadWarning'));
                        }
                        await refreshReplayData(true);
                    }}
                />
            </Drawer>
        </div>
    );
}
