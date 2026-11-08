"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { describeError, getMe, loadStats } from "@/lib/api";
import { KIND_LABELS, SERIES, ruleLabel, seriesKeyForKind } from "@/lib/labels";

const RANGES = [7, 14, 30];
const sum = (counts, kinds) => kinds.reduce((n, kind) => n + (counts?.[kind] ?? 0), 0);

const shortDate = (isoDate) =>
  new Date(`${isoDate}T00:00:00Z`).toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" });

function DailyChart({ daily, days, total }) {
  const W = 640;
  const H = 220;
  const pad = { left: 34, right: 8, top: 10, bottom: 26 };
  const dayTotals = daily.map((d) => SERIES.reduce((n, s) => n + sum(d, s.kinds), 0));
  const top = Math.max(4, Math.ceil(Math.max(0, ...dayTotals) / 4) * 4);
  const bandWidth = (W - pad.left - pad.right) / daily.length;
  const barWidth = Math.max(3, bandWidth * 0.68);
  const y = (value) => pad.top + (H - pad.top - pad.bottom) * (1 - value / top);
  const labelEvery = Math.ceil(daily.length / 7);

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Stacked bar chart of safety events per day. ${total} events in the last ${days} days.`}>
        {[0, top / 2, top].map((tick) => (
          <g key={tick}>
            <line className="gridline" x1={pad.left} x2={W - pad.right} y1={y(tick)} y2={y(tick)} />
            <text x={pad.left - 6} y={y(tick) + 4} textAnchor="end">
              {tick}
            </text>
          </g>
        ))}
        {daily.map((day, i) => {
          const x = pad.left + i * bandWidth + (bandWidth - barWidth) / 2;
          let stacked = 0;
          return (
            <g key={day.date}>
              {SERIES.map((s) => {
                const value = sum(day, s.kinds);
                if (!value) return null;
                const bottom = y(stacked);
                stacked += value;
                const topEdge = y(stacked);
                return (
                  <rect key={s.key} className={`bar bar-${s.key}`} x={x} y={topEdge} width={barWidth} height={bottom - topEdge} rx="1.5">
                    <title>{`${shortDate(day.date)}: ${value} ${s.label.toLowerCase()}`}</title>
                  </rect>
                );
              })}
              {i % labelEvery === 0 && (
                <text x={x + barWidth / 2} y={H - 8} textAnchor="middle">
                  {shortDate(day.date)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <ul className="legend">
        {SERIES.map((s) => (
          <li key={s.key}>
            <span className={`swatch bar-${s.key}`} aria-hidden="true" />
            {s.label}
          </li>
        ))}
      </ul>
      <table className="visually-hidden">
        <caption>Safety events per day</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            {SERIES.map((s) => (
              <th scope="col" key={s.key}>
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {daily.map((d) => (
            <tr key={d.date}>
              <th scope="row">{shortDate(d.date)}</th>
              {SERIES.map((s) => (
                <td key={s.key}>{sum(d, s.kinds)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

export default function SafetyPage() {
  const [days, setDays] = useState(14);
  const [scope, setScope] = useState("me");
  const [isAdmin, setIsAdmin] = useState(false);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getMe()
      .then((me) => setIsAdmin(Boolean(me?.is_admin)))
      .catch(() => setIsAdmin(false));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setStats(null);
    setError(null);
    loadStats(days, scope)
      .then((s) => !cancelled && setStats(s))
      .catch((err) => !cancelled && setError(describeError(err)));
    return () => {
      cancelled = true;
    };
  }, [days, scope]);

  const total = stats ? SERIES.reduce((n, s) => n + sum(stats.totals, s.kinds), 0) : 0;
  const maxRule = stats ? Math.max(1, ...stats.rules.map((r) => r.count)) : 1;

  return (
    <main className="page wide">
      <h1>What the safety layer did</h1>
      <p className="lede">
        Every message passes through checks before it reaches the model, and every reply is checked on the way back.
        This page shows what they caught. Only which rule fired and when is recorded, never what was said. Events are
        kept for 90 days and deleted with your account.
      </p>

      <div className="controls">
        <div className="segmented compact" role="group" aria-label="Time range">
          {RANGES.map((n) => (
            <button key={n} type="button" aria-pressed={days === n} onClick={() => setDays(n)}>
              {n} days
            </button>
          ))}
        </div>
        {isAdmin && (
          <div className="segmented compact" role="group" aria-label="Whose activity">
            <button type="button" aria-pressed={scope === "me"} onClick={() => setScope("me")}>
              My activity
            </button>
            <button type="button" aria-pressed={scope === "all"} onClick={() => setScope("all")}>
              Everyone
            </button>
          </div>
        )}
      </div>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!stats && !error && <p className="empty-line">Loading…</p>}

      {stats && (
        <>
          <ul className="tiles">
            {SERIES.map((s) => (
              <li key={s.key} className="tile">
                <span className={`tile-bar bar-${s.key}`} aria-hidden="true" />
                <strong>{sum(stats.totals, s.kinds)}</strong>
                <span>{s.label}</span>
              </li>
            ))}
          </ul>

          {total === 0 ? (
            <div className="empty">
              <span className="lamp" aria-hidden="true" />
              <div>
                <p>Nothing has been flagged in this period.</p>
                <p className="muted">
                  Try telling Nasha to ignore her instructions, or include an email address, then come back.{" "}
                  <Link href="/">Open the chat</Link>
                </p>
              </div>
            </div>
          ) : (
            <>
              <h2>Per day</h2>
              <DailyChart daily={stats.daily} days={stats.days} total={total} />

              {stats.rules.length > 0 && (
                <>
                  <h2>Top triggers</h2>
                  <ul className="meters">
                    {stats.rules.map((r) => (
                      <li key={`${r.kind}-${r.rule}`}>
                        <span className="meter-label">
                          {ruleLabel(r.rule)}
                          <small>{KIND_LABELS[r.kind]}</small>
                        </span>
                        <span className="meter" aria-hidden="true">
                          <span className={`fill bar-${seriesKeyForKind(r.kind)}`} style={{ width: `${(r.count / maxRule) * 100}%` }} />
                        </span>
                        <span className="meter-count">{r.count}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}

              <h2>Recent events</h2>
              <ol className="events">
                {stats.recent.map((e, i) => (
                  <li key={`${e.created_at}-${i}`}>
                    <time dateTime={e.created_at}>
                      {new Date(e.created_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                    </time>
                    <span>{KIND_LABELS[e.kind] ?? e.kind}</span>
                    <span className="muted">
                      {e.detail
                        ? e.detail
                            .split(",")
                            .map((r) => ruleLabel(r.trim()))
                            .join(", ")
                        : ""}
                    </span>
                  </li>
                ))}
              </ol>
            </>
          )}
        </>
      )}
    </main>
  );
}