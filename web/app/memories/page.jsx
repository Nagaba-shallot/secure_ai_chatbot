"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { deleteEverything, describeError, forgetMemory, loadMemories } from "@/lib/api";

const formatDate = (iso) => new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" }).format(new Date(iso));

export default function MemoriesPage() {
  const router = useRouter();
  const [memories, setMemories] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    loadMemories()
      .then(setMemories)
      .catch((err) => setError(describeError(err)))
      .finally(() => setLoaded(true));
  }, []);

  async function forget(id) {
    setError(null);
    try {
      await forgetMemory(id);
      setMemories((list) => list.filter((m) => m.id !== id));
    } catch (err) {
      setError(describeError(err));
    }
  }

  async function eraseAll() {
    setError(null);
    try {
      await deleteEverything();
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(describeError(err));
    }
  }

  return (
    <main className="page">
      <h1>What Nasha remembers</h1>
      <p className="lede">
        Nasha picks up lasting details from your chats, like what you&apos;re studying or what you enjoy, so it can talk
        with you naturally. Personal contact details are never saved. Forget anything you don&apos;t want kept.
      </p>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      {loaded && memories.length === 0 && (
        <div className="empty">
          <span className="lamp" aria-hidden="true" />
          <div>
            <p>Nothing remembered yet.</p>
            <p className="muted">
              Lasting details from your chats will show up here. <Link href="/">Start a chat</Link>
            </p>
          </div>
        </div>
      )}

      {memories.length > 0 && (
        <ul className="memory-list">
          {memories.map((m) => (
            <li key={m.id}>
              <span>
                {m.fact}
                <small>Added {formatDate(m.created_at)}</small>
              </span>
              <button type="button" className="ghost" onClick={() => forget(m.id)} aria-label={`Forget: ${m.fact}`}>
                Forget
              </button>
            </li>
          ))}
        </ul>
      )}

      <section className="erase">
        <h2>Erase everything</h2>
        <p>Deletes your messages and memories and ends this session.</p>
        {confirming ? (
          <div className="confirm" role="group" aria-label="Confirm deletion">
            <p>This permanently deletes your messages and memories. It can&apos;t be undone.</p>
            <div className="actions">
              <button type="button" className="danger solid" onClick={eraseAll}>
                Yes, delete everything
              </button>
              <button type="button" className="ghost" onClick={() => setConfirming(false)} autoFocus>
                Keep my data
              </button>
            </div>
          </div>
        ) : (
          <button type="button" className="danger" onClick={() => setConfirming(true)}>
            Delete everything
          </button>
        )}
      </section>
    </main>
  );
}