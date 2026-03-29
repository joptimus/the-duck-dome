import { useMemo, useState } from "react";

export default function ChatShell({ channel, messages, onSend }) {
  const [draft, setDraft] = useState("");

  const sortedMessages = useMemo(() => messages || [], [messages]);

  const submit = (event) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    onSend(text);
    setDraft("");
  };

  return (
    <section className="chat-shell">
      <div className="chat-shell__timeline">
        {sortedMessages.length === 0 ? (
          <div className="chat-shell__empty">No messages yet in #{channel?.name || "channel"}.</div>
        ) : (
          sortedMessages.map((message) => (
            <div key={message.id} className="chat-message">
              <div className="chat-message__meta">
                <strong>{message.sender}</strong>
                <span>{message.time || ""}</span>
              </div>
              <p>{message.text}</p>
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
