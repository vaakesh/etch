import { defineMessages, useLocalizedMessages } from "../i18n";

interface PageLoaderProps {
  contained?: boolean;
  tone?: "dark" | "light";
}

const MESSAGES = defineMessages({ loading: "Загрузка страницы" }, { loading: "Loading page" });

export function PageLoader({ contained = false, tone = "dark" }: PageLoaderProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const className = [
    "page-loader",
    `page-loader--${tone}`,
    contained ? "page-loader--contained" : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div aria-label={messages.loading} className={className} role="status">
      <span aria-hidden="true" className="page-loader__spinner" />
    </div>
  );
}
