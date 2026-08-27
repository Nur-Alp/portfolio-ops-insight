export function PageFrame({
  title,
  eyebrow,
  description,
  meta,
  headerAside,
  className,
  onClick,
  onKeyDown,
  children
}: React.PropsWithChildren<{
  title: string;
  eyebrow: string;
  description: string;
  meta?: React.ReactNode;
  headerAside?: React.ReactNode;
  className?: string;
  onClick?: React.MouseEventHandler<HTMLDivElement>;
  onKeyDown?: React.KeyboardEventHandler<HTMLDivElement>;
}>) {
  return (
    <div className={`page-stack${className ? ` ${className}` : ""}`} onClick={onClick} onKeyDown={onKeyDown}>
      <header className={`page-heading${headerAside ? " page-heading--with-aside" : ""}`}>
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        {meta ? <div className="page-heading__meta">{meta}</div> : null}
        {headerAside ? <div className="page-heading__aside">{headerAside}</div> : null}
      </header>
      {children}
    </div>
  );
}
