export type AutoApprovePolicy = "none" | "tool" | "all";

export interface ToolPermission {
  key: string;
  label: string;
  description: string;
  icon: string;
  enabled: boolean;
  highRisk?: boolean;
}

export interface AgentPermissions {
  tools: ToolPermission[];
  autoApprove: AutoApprovePolicy;
  maxLoops: number;
}

const DEFAULT_TOOLS: ToolPermission[] = [
  {
    key: "bash",
    label: "Terminal / bash",
    description: "Run shell commands",
    icon: "TerminalIcon",
    enabled: true,
    highRisk: true,
  },
  {
    key: "write_file",
    label: "Write files",
    description: "Create and modify files",
    icon: "EditIcon",
    enabled: true,
    highRisk: true,
  },
  {
    key: "read_file",
    label: "Read files",
    description: "View file contents",
    icon: "EyeIcon",
    enabled: true,
    highRisk: false,
  },
  {
    key: "web_search",
    label: "Web search",
    description: "Search the internet",
    icon: "SearchIcon",
    enabled: false,
    highRisk: false,
  },
];

export function getDefaultAgentPermissions(): AgentPermissions {
  return {
    tools: DEFAULT_TOOLS.map((tool) => ({ ...tool })),
    autoApprove: "none",
    maxLoops: 25,
  };
}

function normalizeTool(tool: Partial<ToolPermission>, fallback?: ToolPermission): ToolPermission {
  return {
    key: String(tool?.key || fallback?.key || "tool"),
    label: String(tool?.label || fallback?.label || tool?.key || "Tool"),
    description: String(tool?.description || fallback?.description || ""),
    icon: String(tool?.icon || fallback?.icon || "BoltIcon"),
    enabled: Boolean(tool?.enabled ?? fallback?.enabled),
    highRisk: Boolean(tool?.highRisk ?? fallback?.highRisk),
  };
}

export function clampMaxLoops(value: unknown): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return 25;
  }
  return Math.min(100, Math.max(1, Math.round(parsed)));
}

export function normalizeAgentPermissions(value: Partial<AgentPermissions> | null | undefined): AgentPermissions {
  const defaults = getDefaultAgentPermissions();
  const tools = Array.isArray(value?.tools) && value.tools.length > 0
    ? value.tools.map((tool) => {
        const fallback = defaults.tools.find((item) => item.key === tool?.key);
        return normalizeTool(tool, fallback);
      })
    : defaults.tools;

  const autoApprove = value?.autoApprove === "tool" || value?.autoApprove === "all"
    ? value.autoApprove
    : "none";

  return {
    tools,
    autoApprove,
    maxLoops: clampMaxLoops(value?.maxLoops ?? defaults.maxLoops),
  };
}

export function buildPermissionsPayload(permissions: AgentPermissions) {
  return {
    tools: permissions.tools.map((tool) => ({
      key: tool.key,
      enabled: tool.enabled,
    })),
    autoApprove: permissions.autoApprove,
    maxLoops: permissions.maxLoops,
  };
}
