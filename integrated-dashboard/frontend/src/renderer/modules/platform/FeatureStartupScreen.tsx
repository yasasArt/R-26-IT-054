import { Icon } from "@garment-counter/components/Icon";
import type { BackendStatus } from "../../../shared/types";

export function FeatureStartupScreen({
  area,
  title,
  message,
  state,
  runtimeLabel,
  onBack,
  onRetry,
}: {
  area: string;
  title: string;
  message: string;
  state: BackendStatus["state"];
  runtimeLabel: string;
  onBack: () => void;
  onRetry?: () => void;
}) {
  const failed = state === "error";

  return (
    <section className={`feature-startup-shell ${failed ? "is-error" : ""}`}>
      <div className="feature-startup-glow" aria-hidden="true" />
      <article className="feature-startup-card" role="status" aria-live="polite">
        <div className="feature-startup-visual" aria-hidden="true">
          <span className="feature-startup-orbit orbit-one" />
          <span className="feature-startup-orbit orbit-two" />
          <span className="feature-startup-core">
            <Icon name={failed ? "warning" : "scan"} size={28} />
          </span>
        </div>

        <span className="platform-eyebrow">{area}</span>
        <h1>{failed ? `${title} needs attention` : `Preparing ${title}`}</h1>
        <p>{message}</p>

        {!failed ? (
          <div className="feature-startup-progress" aria-label="Starting feature services">
            <span />
          </div>
        ) : null}

        <div className="feature-startup-actions">
          {failed && onRetry ? (
            <button type="button" className="platform-primary-button" onClick={onRetry}>
              Retry startup <Icon name="refresh" size={15} />
            </button>
          ) : null}
          <button type="button" className="feature-startup-back" onClick={onBack}>
            <Icon name="arrow-right" className="feature-startup-back-icon" size={15} /> Back to features
          </button>
        </div>

        <small><Icon name="lock" size={13} /> {runtimeLabel}</small>
      </article>
    </section>
  );
}
