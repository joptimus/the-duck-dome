import { useMemo, useState } from "react";

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderMarkdown(text) {
  const escaped = escapeHtml(String(text || ""));
  return escaped
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/\n/g, "<br />");
}

export default function ChatShell({ channel, messages, onSend, messageError, claudeWorking, claudeFailure }) {
  const [draft, setDraft] = useState("");

  const sortedMessages = useMemo(() => messages || [], [messages]);

  const submit = async (event) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    try {
      await onSend(text);
      setDraft("");
    } catch (_error) {
      // Keep draft content intact when send fails.
    }
  };

  return (
    <section className="chat-shell">
      <div className="chat-shell__timeline">
        {messageError ? <div className="chat-shell__notice">Message sync issue: {messageError}</div> : null}
        {claudeWorking ? (
          <div className="chat-message chat-message--system">
            <div className="chat-message__meta">
              <strong>System</strong>
              <span className="chat-message__working">Claude is working...</span>
            </div>
          </div>
        ) : null}
        {claudeFailure ? (
          <div className="chat-message chat-message--system">
            <div className="chat-message__meta">
              <strong>System</strong>
              <span>Error</span>
            </div>
            <p>Claude failed to execute: {claudeFailure}</p>
          </div>
        ) : null}
        {sortedMessages.length === 0 ? (
          <div className="chat-shell__empty">No messages yet in #{channel?.name || "channel"}.</div>
        ) : (
          sortedMessages.map((message) => (
            <div
              key={message.id}
              className={
                message.sender_type === "assistant" ? "chat-message chat-message--assistant" : "chat-message"
              }
            >
              <div className="chat-message__meta">
                <strong>{message.sender}</strong>
                <span>{message.time || ""}</span>
              </div>
              {message.sender_type === "assistant" ? (
                <p dangerouslySetInnerHTML={{ __html: renderMarkdown(message.text) }} />
              ) : (
                <p>{message.text}</p>
              )}
            </div>
          ))
        )}
      </div>

      <form className="chat-shell__composer" onSubmit={submit}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Message channel... use @name for mentions (placeholder)"
          aria-label="Message composer"
        />
        <button type="submit">Send</button>
      </form>
    </section>
  );
}
