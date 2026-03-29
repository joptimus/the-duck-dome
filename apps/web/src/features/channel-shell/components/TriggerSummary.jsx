export default function TriggerSummary({ summary, hasData, error }) {
  const counts = summary || { pending: 0, working: 0, completed: 0, failed: 0 };
  return (
    <section className="trigger-summary" aria-label="Trigger summary">
      <h3>Trigger Summary</h3>
      {error ? <div className="trigger-summary__error">Unable to load trigger data.</div> : null}
      {!error && !hasData ? <div className="trigger-summary__empty">No runtime data yet for this channel.</div> : null}
      {!error && hasData ? (
        <div className="trigger-summary__grid">
          <article className="trigger-card">
            <div className="trigger-card__label">Pending triggers</div>
            <div className="trigger-card__value">{counts.pending}</div>
          </article>
          <article className="trigger-card">
            <div className="trigger-card__label">Working triggers</div>
            <div className="trigger-card__value">{counts.working}</div>
          </article>
          <article className="trigger-card">
            <div className="trigger-card__label">Completed triggers</div>
            <div className="trigger-card__value">{counts.completed}</div>
          </article>
          <article className="trigger-card">
            <div className="trigger-card__label">Failed triggers</div>
            <div className="trigger-card__value">{counts.failed}</div>
          </article>
        </div>
      ) : null}
    </section>
  );
}
