import type { PropsWithChildren, ReactNode } from "react";

// Rule: `subtitle` must say what the panel actually contains (which sheet/
// field it's built from, what the numbers mean) - never just mechanics like
// a row count or pagination state on its own. "Показано 10 из 101 строк"
// tells a reader nothing about what's IN those 101 rows; lead with that,
// then fold the count in afterward if it's still useful. A reader landing
// on this panel via a bookmark/scroll/screenshot has no other way to learn
// what they're looking at - the page header's own description doesn't
// travel with it. See DomainPage.tsx's mainTablePanel for the pattern
// (content sentence first, mechanics sentence second).
export function Panel({
  title,
  subtitle,
  action,
  className = "",
  children
}: PropsWithChildren<{
  title: string;
  subtitle?: string;
  action?: ReactNode;
  className?: string;
}>) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel__header">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {action ? <div className="panel__action">{action}</div> : null}
      </header>
      <div className="panel__body">{children}</div>
    </section>
  );
}
