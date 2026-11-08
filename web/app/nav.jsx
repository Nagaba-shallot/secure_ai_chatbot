"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AUTH_EVENT, getMe, signOut } from "@/lib/api";

export default function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      getMe()
        .then((m) => !cancelled && setMe(m))
        .catch(() => !cancelled && setMe(null));
    load();
    window.addEventListener(AUTH_EVENT, load);
    return () => {
      cancelled = true;
      window.removeEventListener(AUTH_EVENT, load);
    };
  }, [pathname]);

  async function handleSignOut() {
    await signOut();
    router.push("/");
    router.refresh();
  }

  const link = (href, label) => (
    <Link href={href} aria-current={pathname === href ? "page" : undefined}>
      {label}
    </Link>
  );

  const signedIn = me && !me.anonymous;

  return (
    <header className="topbar">
      <Link href="/" className="brand" aria-label="Nasha, home">
        <span className="lamp" aria-hidden="true" />
        Nasha
      </Link>
      <nav aria-label="Main">
        {link("/", "Chat")}
        {link("/memories", "Memories")}
        {link("/safety", "Safety")}
        {signedIn ? (
          <>
            <span className="account" title={me.email}>
              {me.email}
            </span>
            <button type="button" className="linklike" onClick={handleSignOut}>
              Sign out
            </button>
          </>
        ) : (
          link("/signin", "Sign in")
        )}
      </nav>
    </header>
  );
}