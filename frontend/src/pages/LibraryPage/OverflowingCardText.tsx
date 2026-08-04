import { useEffect, useId, useRef, useState } from "react";
import styles from "./LibraryPage.module.css";

interface OverflowingCardTextProps {
  className: string;
  label: string;
  language: string;
  text: string;
}

export function OverflowingCardText({
  className,
  label,
  language,
  text,
}: OverflowingCardTextProps) {
  const textRef = useRef<HTMLParagraphElement | null>(null);
  const tooltipId = useId();
  const [isOverflowing, setIsOverflowing] = useState(false);

  useEffect(() => {
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
  }, [text]);

  return (
    <div className={styles.cardTextOverflow}>
      <p
        aria-describedby={isOverflowing ? tooltipId : undefined}
        className={className}
        data-overflowing={isOverflowing}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.currentTarget.blur();
          }
        }}
        ref={textRef}
        tabIndex={isOverflowing ? 0 : undefined}
      >
        <span className={styles.visuallyHidden}>{label}: </span>
        <span lang={language}>{text}</span>
      </p>
      {isOverflowing ? (
        <span className={styles.cardTextTooltip} id={tooltipId} role="tooltip">
          <span className={styles.cardTextTooltipLabel}>Полный текст</span>
          <span lang={language}>{text}</span>
        </span>
      ) : null}
    </div>
  );
}
