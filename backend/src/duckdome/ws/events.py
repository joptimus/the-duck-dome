"""WebSocket event type constants.

Outbound events broadcast to connected clients.
"""

NEW_MESSAGE = "new_message"
MESSAGE_DELETED = "message_deleted"
TRIGGER_STATE_CHANGE = "trigger_state_change"
AGENT_STATUS_CHANGE = "agent_status_change"
TOOL_APPROVAL_UPDATED = "tool_approval_updated"
JOB_UPDATED = "job_updated"
JOB_MESSAGE_ADDED = "job_message_added"
CHANNEL_DELETED = "channel_deleted"
AGENT_MESSAGE_DELTA = "agent_message_delta"
AGENT_TOOL_CALL = "agent_tool_call"
AGENT_TOOL_RESULT = "agent_tool_result"
AGENT_SUBAGENT = "agent_subagent"
AGENT_ERROR = "agent_error"
