export type DashboardIconName =
  | "home"
  | "decks"
  | "book"
  | "practice"
  | "chart"
  | "settings"
  | "plus"
  | "chevron"
  | "target"
  | "flame"
  | "gauge"
  | "calendar"
  | "clock";

interface DashboardIconProps {
  name: DashboardIconName;
  className?: string;
}

export function DashboardIcon({ name, className }: DashboardIconProps) {
  let content;

  switch (name) {
    case "home":
      content = (
        <>
          <path d="m3 10 9-7 9 7" />
          <path d="M5.5 9.5V21h13V9.5M9.5 21v-7h5v7" />
        </>
      );
      break;
    case "decks":
      content = (
        <>
          <path d="M4 6.5h16v13H4z" />
          <path d="M7 3.5h10M8.5 10h7" />
          <path d="m9 10 1.3 2h3.4L15 10" />
        </>
      );
      break;
    case "book":
      content = (
        <>
          <path d="M3.5 5.5c3.4-1.2 6-.6 8.5 1.4v13c-2.5-2-5.1-2.6-8.5-1.4z" />
          <path d="M20.5 5.5c-3.4-1.2-6-.6-8.5 1.4v13c2.5-2 5.1-2.6 8.5-1.4z" />
          <path d="M6.5 9h2.7M6.5 12h2.7M14.8 9h2.7M14.8 12h2.7" />
        </>
      );
      break;
    case "practice":
      content = (
        <>
          <path d="m4 20 4.2-1 11-11a2.1 2.1 0 0 0-3-3l-11 11z" />
          <path d="m14.8 6.5 3 3M4 20l3-3" />
        </>
      );
      break;
    case "chart":
      content = (
        <>
          <path d="M5 20V10M12 20V4M19 20v-7" />
          <rect x="3" y="8" width="4" height="12" rx="2" />
          <rect x="10" y="2" width="4" height="18" rx="2" />
          <rect x="17" y="11" width="4" height="9" rx="2" />
        </>
      );
      break;
    case "settings":
      content = (
        <>
          <circle cx="12" cy="12" r="3.2" />
          <path d="M19.3 13.4c.1-.5.1-1 0-1.5l2-1.5-2-3.5-2.4 1a8 8 0 0 0-1.4-.8L15.2 4h-4l-.4 3.1a8 8 0 0 0-1.4.8L7 6.9l-2 3.5 2 1.5a7 7 0 0 0 0 1.5l-2 1.5 2 3.5 2.4-1a8 8 0 0 0 1.4.8l.4 2.8h4l.4-2.8a8 8 0 0 0 1.4-.8l2.4 1 2-3.5z" />
        </>
      );
      break;
    case "plus":
      content = <path d="M12 5v14M5 12h14" />;
      break;
    case "chevron":
      content = <path d="m9 5 7 7-7 7" />;
      break;
    case "target":
      content = (
        <>
          <circle cx="11" cy="13" r="8" />
          <circle cx="11" cy="13" r="4" />
          <path d="m11 13 8-8M16 5h3v3" />
        </>
      );
      break;
    case "flame":
      content = (
        <path d="M13.2 2.8c.4 3.8-2.6 4.8-2.6 7.4 0 1.3.8 2.2 1.9 2.6-.3-2.5 1.4-3.6 2.2-5.7 2.9 2.4 4.3 5.1 4.3 7.9a7 7 0 0 1-14 0c0-3.8 2.1-7.1 6.3-10.2 0 2.1.6 3.5 1.9 4.2.7-1.7.7-3.8 0-6.2Z" />
      );
      break;
    case "gauge":
      content = (
        <>
          <path d="M4 16a8 8 0 0 1 16 0" />
          <path d="M7 16h10M12 14l4.2-4.2" />
          <circle cx="12" cy="14" r="1.4" />
          <path d="M6.4 11.2 5 10.5M9 8.4l-.7-1.3M15 8.4l.7-1.3M17.6 11.2l1.4-.7" />
        </>
      );
      break;
    case "calendar":
      content = (
        <>
          <rect height="15.5" rx="3" width="17" x="3.5" y="5.5" />
          <path d="M8 3.5v4M16 3.5v4M3.5 10h17" />
          <path d="m8.3 15.4 2.1 2.1 4.4-4.5" />
        </>
      );
      break;
    case "clock":
      content = (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 6.5V12l4 2.5" />
        </>
      );
      break;
  }

  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.7"
      viewBox="0 0 24 24"
    >
      {content}
    </svg>
  );
}

interface DeckIllustrationProps {
  className?: string;
  variant: number;
}

const ink = "var(--illustration-ink, #18313a)";
const teal = "var(--illustration-teal, #72aaa5)";
const paleTeal = "var(--illustration-pale-teal, #dbe9e5)";
const coral = "var(--illustration-coral, #ee8b64)";
const cream = "var(--illustration-cream, #f4eadb)";
const paper = "var(--illustration-paper, #fffdf8)";

export function DeckIllustration({ className, variant }: DeckIllustrationProps) {
  const commonProps = {
    stroke: ink,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 1.7,
  };

  let content;

  switch (variant % 6) {
    case 0:
      content = (
        <>
          <path
            d="M22 79c20-10 35-8 50 3 15-11 30-13 50-3v34c-18-8-34-7-50 4-16-11-32-12-50-4Z"
            fill={paper}
            {...commonProps}
          />
          <path
            d="M72 82v35M31 88c14-5 25-3 34 3M31 96c14-5 25-3 34 3M113 88c-14-5-25-3-34 3M113 96c-14-5-25-3-34 3"
            {...commonProps}
          />
          <path
            d="M104 75c2-23 9-40 21-52M112 59c8-3 14-8 16-15M112 58c-6-4-9-9-9-15M120 43c7-3 11-7 13-13M121 43c-5-3-8-7-8-12"
            {...commonProps}
          />
          <ellipse cx="104" cy="73" rx="7" ry="3" fill={paleTeal} stroke={ink} strokeWidth="1.4" />
        </>
      );
      break;
    case 1:
      content = (
        <>
          <rect x="35" y="50" width="72" height="64" rx="8" fill={paper} {...commonProps} />
          <path
            d="M51 50v-9c0-6 5-10 11-10h18c6 0 11 4 11 10v9M48 55v54M94 55v54"
            {...commonProps}
          />
          <path d="M35 69h72M43 66v9M99 66v9" {...commonProps} />
          <path d="M87 46h9v58h-9" fill={coral} opacity=".85" />
          <path
            d="M119 105c0-13 8-21 20-21 7 0 13 5 13 12 0 10-10 17-25 17h-13"
            fill={cream}
            {...commonProps}
          />
          <path
            d="M127 81c5-12 12-19 23-22M131 72c5 0 9 2 12 6M138 66c0-6 2-11 6-15"
            {...commonProps}
          />
        </>
      );
      break;
    case 2:
      content = (
        <>
          <path
            d="M74 112C50 96 35 79 35 61c0-14 9-24 22-24 9 0 15 5 19 13 4-8 10-13 19-13 13 0 22 10 22 24 0 18-16 35-43 51Z"
            fill={coral}
            {...commonProps}
          />
          <circle cx="61" cy="67" r="2.2" fill={ink} />
          <circle cx="91" cy="67" r="2.2" fill={ink} />
          <path
            d="M64 82c7 6 16 6 23 0M47 31l-2-8M43 27l-8-2M116 41l5-8M119 39l8 1M119 93l8 5M121 91l6-3"
            {...commonProps}
          />
          <path
            d="m132 54 2 5 5 2-5 2-2 5-2-5-5-2 5-2Z"
            fill={paleTeal}
            stroke={ink}
            strokeWidth="1.2"
          />
        </>
      );
      break;
    case 3:
      content = (
        <>
          <path d="M28 99h83l10 15H18Z" fill={paleTeal} {...commonProps} />
          <rect x="36" y="49" width="69" height="52" rx="4" fill={paper} {...commonProps} />
          <rect
            x="45"
            y="58"
            width="51"
            height="34"
            rx="2"
            fill={paleTeal}
            stroke={ink}
            strokeWidth="1.4"
          />
          <path
            d="M55 82V72M66 82V66M77 82V75M88 82V62"
            stroke={teal}
            strokeLinecap="round"
            strokeWidth="3"
          />
          <path
            d="M121 105h23M129 104V87M129 93c-7 0-11-5-12-11 7 0 11 4 12 11ZM130 97c5-5 10-5 15-2-4 6-9 7-15 2Z"
            {...commonProps}
          />
          <path d="M121 105h17l-2 10h-13Z" fill={cream} {...commonProps} />
        </>
      );
      break;
    case 4:
      content = (
        <>
          <path d="m61 23 13 8-25 43-13-8z" fill={paper} {...commonProps} />
          <path d="m53 37 13 8M45 63l13 8M55 75c18 8 28 22 27 42M34 117h77" {...commonProps} />
          <path d="M74 77c20 5 31 18 31 40" {...commonProps} />
          <path d="M70 96c-14 0-22 8-22 21" {...commonProps} />
          <path d="M43 117h68l-5 8H48Z" fill={paleTeal} {...commonProps} />
          <path
            d="M115 59h14v11l7 37c1 6-3 10-9 10h-10c-6 0-10-4-9-10l7-37Z"
            fill={paper}
            {...commonProps}
          />
          <path d="M112 99h20" stroke={teal} strokeWidth="4" />
          <circle cx="122" cy="92" r="2" fill={teal} />
        </>
      );
      break;
    default:
      content = (
        <>
          <path
            d="M76 105V34M75 66c-15-9-22-21-20-35 15 7 22 19 20 35ZM77 53c13-7 20-17 20-30-14 5-21 15-20 30ZM75 86c-17-7-27-18-29-32 17 4 27 15 29 32ZM77 77c16-5 26-14 30-28-17 2-27 12-30 28ZM76 102c15-4 26-12 31-25-16 1-27 9-31 25Z"
            fill={paleTeal}
            {...commonProps}
          />
          <path d="M54 101h45l-5 29H59Z" fill={cream} {...commonProps} />
          <path d="M48 130h58" {...commonProps} />
        </>
      );
      break;
  }

  return (
    <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 160 140">
      {content}
    </svg>
  );
}
