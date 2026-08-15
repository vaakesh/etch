import { useEffect, useId, useRef, useState } from "react";
import { useLongTextPreviewsEnabled } from "../../features/settings/model/useLongTextPreviewsEnabled";
import { defineMessages, useLocalizedMessages } from "../../i18n";
import styles from "./LibraryPage.module.css";

const MESSAGES = defineMessages({ fullText: "Полный текст" }, { fullText: "Full text" });

interface OverflowingCardTextProps {
  className: string;
  label: string;
  language?: string;
  text: string;
}

export function OverflowingCardText({
  className,
  label,
  language,
  text,
}: OverflowingCardTextProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const previewsEnabled = useLongTextPreviewsEnabled();
  const textRef = useRef<HTMLParagraphElement | null>(null);
  const tooltipId = useId();
  const [isOverflowing, setIsOverflowing] = useState(false);

  useEffect(() => {
    if (!previewsEnabled) {
      return;
    }

    const element = textRef.current;

    if (element === null) {
      return;
    }

    const updateOverflow = (): void => {
      const nextIsOverflowing =
        element.scrollHeight > element.clientHeight + 1 ||
        element.scrollWidth > element.clientWidth + 1;

      setIsOverflowing((currentValue) =>
        currentValue === nextIsOverflowing ? currentValue : nextIsOverflowing,
      );
    };

    updateOverflow();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateOverflow);
      return () => window.removeEventListener("resize", updateOverflow);
    }

    const observer = new ResizeObserver(updateOverflow);
    observer.observe(element);

    return () => observer.disconnect();
  }, [previewsEnabled, text]);

  const showFullText = previewsEnabled && isOverflowing;

  return (
    <div className={styles.cardTextOverflow}>
      <p
        aria-describedby={showFullText ? tooltipId : undefined}
        className={className}
        data-overflowing={showFullText}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.currentTarget.blur();
          }
        }}
        ref={textRef}
        tabIndex={showFullText ? 0 : undefined}
      >
        <span className={styles.visuallyHidden}>{label}: </span>
        <span lang={language}>{text}</span>
      </p>
      {showFullText ? (
        <span className={styles.cardTextTooltip} id={tooltipId} role="tooltip">
          <span className={styles.cardTextTooltipLabel}>{messages.fullText}</span>
          <span lang={language}>{text}</span>
        </span>
      ) : null}
    </div>
  );
}
