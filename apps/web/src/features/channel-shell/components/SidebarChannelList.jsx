function hashIcon() {
  return <span aria-hidden="true">#</span>;
}

function repoIcon() {
  return <span aria-hidden="true">▣</span>;
}

export default function SidebarChannelList({ channels, activeChannelId, onSelect, onOpenCreate }) {
  return (
    <aside className="channel-sidebar">
      <div className="channel-sidebar__header">
        <h2>Channels</h2>
        <button
          type="button"
          className="channel-sidebar__create"
          onClick={onOpenCreate}
          aria-label="Create channel"
          title="Create channel"
        >
          +
        </button>
      </div>

      <div className="channel-sidebar__list">
        {channels.map((channel) => {
          const active = channel.id === activeChannelId;
          return (
            <button
              key={channel.id}
              type="button"
              className={`channel-row${active ? " channel-row--active" : ""}`}
              onClick={() => onSelect(channel.id)}
            >
              <span className="channel-row__icon">
                {channel.type === "repo" ? repoIcon() : hashIcon()}
              </span>
              <span className="channel-row__name">{channel.name}</span>
              {(channel.unread_count || 0) > 0 ? (
                <span className="channel-row__unread">{channel.unread_count}</span>
              ) : null}
            </button>
          );
        })}
      </div>
    </aside>
  );
}
