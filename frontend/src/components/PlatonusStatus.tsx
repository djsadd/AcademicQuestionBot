import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchPlatonusSession,
  fetchStudentAcademicCalendar,
  PlatonusSessionStatus,
} from "../api/platonus";

function formatAge(seconds: number | null) {
  if (seconds === null) return "unknown";
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m ${remainder}s`;
}

function formatTimestamp(epoch: number | null) {
  if (!epoch) return "unknown";
  return new Date(epoch * 1000).toLocaleString();
}

export function PlatonusStatus() {
  const [status, setStatus] = useState<PlatonusSessionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [personId, setPersonId] = useState("20458");
  const [cardResponse, setCardResponse] = useState<string | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);
  const [cardLoading, setCardLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPlatonusSession();
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load status.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const tokenState = useMemo(() => {
    if (!status) return "unknown";
    return status.token_present ? "active" : "missing";
  }, [status]);

  const loadStudentAcademicCalendar = useCallback(async () => {
    if (!personId.trim()) {
      setCardError("Enter a person id.");
      return;
    }
    setCardLoading(true);
    setCardError(null);
    setCardResponse(null);
    try {
      const data = await fetchStudentAcademicCalendar(personId.trim(), "ru");
      setCardResponse(JSON.stringify(data, null, 2));
    } catch (err) {
      setCardError(err instanceof Error ? err.message : "Failed to load student card.");
    } finally {
      setCardLoading(false);
    }
  }, [personId]);

  return (
    <section className="feature-section">
      <div className="feature-section__header">
        <div>
          <p className="eyebrow">Platonus</p>
          <h2>Session monitor</h2>
          <p className="muted">
            Background login refresh status, token presence, and last login time.
          </p>
        </div>
        <span className="feature-section__status">
          {tokenState === "active" ? "TOKEN OK" : "TOKEN MISSING"}
        </span>
      </div>

      <div className="panel">
        <div className="status-card__header">
          <strong>Current session</strong>
          <button className="ghost" onClick={loadStatus} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {error && <p className="error">Error: {error}</p>}

        {!error && !status && <p className="muted">Loading session status...</p>}

        {status && (
          <div className="doc-meta-grid">
            <div className="status-card">
              <div className="status-card__header">
                <strong>Token</strong>
                <span
                  className={`status-pill ${
                    status.token_present ? "status-success" : "status-failure"
                  }`}
                >
                  {status.token_present ? "Present" : "Missing"}
                </span>
              </div>
              <p className="muted">Last login: {formatTimestamp(status.last_login)}</p>
              <p className="muted">Age: {formatAge(status.age_seconds)}</p>
            </div>

            <div className="status-card">
              <div className="status-card__header">
                <strong>Session meta</strong>
              </div>
              <p className="muted">
                Cookie: {status.cookie_present ? "present" : "missing"}
              </p>
              <p className="muted">SID: {status.sid_present ? "present" : "missing"}</p>
              <p className="muted">
                User agent: {status.user_agent_present ? "present" : "missing"}
              </p>
            </div>

            <div className="status-card">
              <div className="status-card__header">
                <strong>Refresh policy</strong>
              </div>
              <p className="muted">
                Interval: {Math.round(status.refresh_seconds / 60)} minutes
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <div className="status-card__header">
          <strong>Student academic calendar request</strong>
          <button
            className="ghost"
            onClick={loadStudentAcademicCalendar}
            disabled={cardLoading}
          >
            {cardLoading ? "Requesting..." : "Send request"}
          </button>
        </div>
        <div className="actions" style={{ marginTop: "1rem" }}>
          <label className="file-input" style={{ flex: 1 }}>
            <span className="muted">Person ID</span>
            <input
              type="text"
              value={personId}
              onChange={(event) => setPersonId(event.target.value)}
            />
          </label>
        </div>
        {cardError && <p className="error">Error: {cardError}</p>}
        {cardResponse && (
          <pre className="doc-meta__json" style={{ marginTop: "1rem" }}>
            {cardResponse}
          </pre>
        )}
      </div>
    </section>
  );
}
