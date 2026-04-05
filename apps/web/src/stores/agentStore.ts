import { updateAgentPermissions } from "../features/channel-shell/api";
import {
  buildPermissionsPayload,
  clampMaxLoops,
  normalizeAgentPermissions,
  type AgentPermissions,
  type AutoApprovePolicy,
} from "../types/permissions";

type RuntimeAgent = {
  agent_type: string;
  permissions?: AgentPermissions;
};

type StoreAdapter = {
  getAgents: () => RuntimeAgent[];
  setAgents: (updater: (agents: RuntimeAgent[]) => RuntimeAgent[]) => void;
  setError?: (message: string | null) => void;
};

let adapter: StoreAdapter | null = null;

export function configureAgentStore(nextAdapter: StoreAdapter | null) {
  adapter = nextAdapter;
}

function getAdapter(): StoreAdapter | null {
  return adapter;
}

function replacePermissions(agents: RuntimeAgent[], agentKey: string, permissions: AgentPermissions) {
  return agents.map((agent) =>
    agent.agent_type === agentKey
      ? { ...agent, permissions }
      : agent,
  );
}

async function updatePermissions(
  agentKey: string,
  updater: (permissions: AgentPermissions) => AgentPermissions,
) {
  const currentAdapter = getAdapter();
  if (!currentAdapter) {
    return;
  }

  const currentAgent = currentAdapter.getAgents().find((agent) => agent.agent_type === agentKey);
  if (!currentAgent) {
    return;
  }

  const previousPermissions = normalizeAgentPermissions(currentAgent.permissions);
  const nextPermissions = normalizeAgentPermissions(updater(previousPermissions));

  currentAdapter.setAgents((agents) => replacePermissions(agents, agentKey, nextPermissions));

  try {
    const confirmed = await updateAgentPermissions(
      agentKey,
      buildPermissionsPayload(nextPermissions),
      nextPermissions,
    );
    const confirmedPermissions = normalizeAgentPermissions(confirmed || nextPermissions);
    currentAdapter.setAgents((agents) => replacePermissions(agents, agentKey, confirmedPermissions));
    currentAdapter.setError?.(null);
  } catch (error) {
    console.error("Failed to update agent permissions:", error);
    currentAdapter.setAgents((agents) => replacePermissions(agents, agentKey, previousPermissions));
    currentAdapter.setError?.("Failed to update agent permissions");
  }
}

export const agentStore = {
  toggleTool(agentKey: string, toolKey: string) {
    return updatePermissions(agentKey, (permissions) => ({
      ...permissions,
      tools: permissions.tools.map((tool) =>
        tool.key === toolKey
          ? { ...tool, enabled: !tool.enabled }
          : tool,
      ),
    }));
  },

  setAutoApprove(agentKey: string, policy: AutoApprovePolicy) {
    return updatePermissions(agentKey, (permissions) => ({
      ...permissions,
      autoApprove: policy,
    }));
  },

  setMaxLoops(agentKey: string, value: number) {
    return updatePermissions(agentKey, (permissions) => ({
      ...permissions,
      maxLoops: clampMaxLoops(value),
    }));
  },
};
