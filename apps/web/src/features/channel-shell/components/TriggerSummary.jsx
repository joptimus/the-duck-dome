export default function TriggerSummary({ summary, hasData, error }) {
  return (
    <section className="trigger-summary" aria-label="Trigger summary">
      <h3>Trigger Summary</h3>
      {error ? <div className="trigger-summary__error">Unable to load trigger data.</div> : null}
      {!error && !hasData ? (
        <div className="trigger-summary__empty">No runtime data yet for this channel.</div>
      ) : null}
      {!error && hasData ? (
        <div className="trigger-summary__grid">
          <article className="trigger-card">
            <div className="trigger-card__label">Pending triggers</div>
            <div className="trigger-card__value">{summary.pending}</div>
          </article>
          <article className="trigger-card">
            <div className="trigger-card__label">Claimed triggers</div>
            <div className="trigger-card__value">{summary.claimed}</div>
          </article>
          <article className="trigger-card">
            <div className="trigger-card__label">Failed triggers</div>
            <div className="trigger-card__value">{summary.failed}</div>
          </article>
        </div>
      ) : null}
    </section>
  );
}
