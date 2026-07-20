interface PageLoaderProps {
  contained?: boolean;
  tone?: "dark" | "light";
}

export function PageLoader({ contained = false, tone = "dark" }: PageLoaderProps) {
  const className = [
    "page-loader",
    `page-loader--${tone}`,
    contained ? "page-loader--contained" : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div aria-label="Загрузка страницы" className={className} role="status">
      <span aria-hidden="true" className="page-loader__spinner" />
    </div>
  );
}
