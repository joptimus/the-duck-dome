export default function ChannelHeader({ channel }) {
  if (!channel) {
    return (
      <header className="channel-header">
        <div className="channel-header__main">
          <h1>Select a channel</h1>
        </div>
      </header>
    );
  }

  return (
    <header className="channel-header">
      <div className="channel-header__main">
        <h1>
          {channel.type === "repo" ? "▣" : "#"} {channel.name}
        </h1>
        {channel.type === "repo" && channel.repo_path ? (
          <p className="channel-header__repo-path">{channel.repo_path}</p>
        ) : (
          <p className="channel-header__repo-path channel-header__repo-path--muted">General channel</p>
        )}
      </div>
    </header>
  );
}
