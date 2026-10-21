import { useEffect, useId, useRef, useState } from "react";
import { DashboardIcon } from "../../../components/DashboardVisuals";
import { defineMessages, useLocalizedMessages } from "../../../i18n";
import { ASK_MESSAGE_MAX_LENGTH } from "../api/assistant-api";
import { useAssistantChat } from "../model/useAssistantChat";
import styles from "./AssistantChat.module.css";

const MESSAGES = defineMessages(
  {
    open: "Открыть помощника Etch",
    close: "Закрыть помощника Etch",
    title: "Помощник Etch",
    subtitle: "Справка по приложению",
    welcome: "С чем помочь?",
    description: "Подскажу, как работать с карточками, колодами и практикой.",
    suggestions: { importCards: "Как импортировать карточки?", practice: "Как начать практику?" },
    history: "Переписка с помощником",
    you: "Вы",
    assistant: "Etch",
    loading: "Готовлю ответ…",
    input: "Ваш вопрос",
    placeholder: "Спросите о Etch…",
    send: "Отправить вопрос",
    limit: "5 вопросов за 24 часа",
    characters: "символов",
    errors: {
      limit: "Лимит вопросов исчерпан. Попробуйте позже.",
      unavailable: "Помощник сейчас недоступен. Попробуйте чуть позже.",
      timeout: "Ответ занял слишком много времени. Попробуйте позже.",
      invalid: "Не удалось получить ответ. Попробуйте ещё раз позже.",
      network: "Нет связи с сервером. Проверьте подключение.",
      access: "Не удалось отправить вопрос. Проверьте, что вы вошли в аккаунт.",
    },
  },
  {
    open: "Open Etch assistant",
    close: "Close Etch assistant",
    title: "Etch assistant",
    subtitle: "Your guide to the app",
    welcome: "How can I help?",
    description: "Ask me about cards, decks, and practice.",
    suggestions: { importCards: "How do I import cards?", practice: "How do I start practicing?" },
    history: "Assistant conversation",
    you: "You",
    assistant: "Etch",
    loading: "Preparing an answer…",
    input: "Your question",
    placeholder: "Ask about Etch…",
    send: "Send question",
    limit: "5 questions per 24 hours",
    characters: "characters",
    errors: {
      limit: "You have reached the question limit. Please try again later.",
      unavailable: "The assistant is unavailable right now. Please try again later.",
      timeout: "The answer took too long. Please try again later.",
      invalid: "Could not get an answer. Please try again later.",
      network: "Cannot reach the server. Check your connection.",
      access: "Could not send your question. Check that you are signed in.",
    },
  },
);

export function AssistantChat() {
  const copy = useLocalizedMessages(MESSAGES);
  const chat = useAssistantChat();
  const id = useId();
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const historyRef = useRef<HTMLDivElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const length = Array.from(chat.draft).length;

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && historyRef.current) {
      const history = historyRef.current;
      const answer = history.querySelector<HTMLElement>('[data-role="assistant"]:last-child');
      history.scrollTop = answer ? Math.max(0, answer.offsetTop - 20) : history.scrollHeight;
    }
  }, [isOpen, chat.messages, chat.isPending, chat.error]);

  return (
    <div className={styles.widget}>
      <button
        aria-controls={id}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-label={copy.open}
        className={styles.launcher}
        popoverTarget={id}
        ref={launcherRef}
        title={copy.title}
        type="button"
      >
        <DashboardIcon className={styles.icon} name="chat" />
      </button>

      <section
        aria-labelledby={`${id}-title`}
        className={styles.panel}
        id={id}
        onToggle={(event) => setIsOpen(event.newState === "open")}
        popover="auto"
        role="dialog"
      >
        <header className={styles.header}>
          <span aria-hidden="true" className={styles.headerMark}>
            <DashboardIcon className={styles.icon} name="chat" />
          </span>
          <div className={styles.heading}>
            <h2 id={`${id}-title`}>{copy.title}</h2>
            <p>{copy.subtitle}</p>
          </div>
          <button
            aria-label={copy.close}
            className={styles.close}
            onClick={() => launcherRef.current?.focus()}
            popoverTarget={id}
            popoverTargetAction="hide"
            type="button"
          >
            <DashboardIcon className={styles.closeIcon} name="plus" />
          </button>
        </header>

        <div className={styles.history} ref={historyRef}>
          {chat.messages.length === 0 ? (
            <div className={styles.welcome}>
              <DashboardIcon className={styles.welcomeIcon} name="book" />
              <h3>{copy.welcome}</h3>
              <p>{copy.description}</p>
              <div className={styles.suggestions}>
                {Object.values(copy.suggestions).map((question) => (
                  <button
                    className={styles.suggestion}
                    key={question}
                    onClick={() => {
                      chat.setDraft(question);
                      inputRef.current?.focus();
                    }}
                    type="button"
                  >
                    {question}
                    <DashboardIcon className={styles.suggestionIcon} name="chevron" />
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div
            aria-label={copy.history}
            aria-relevant="additions text"
            className={styles.messages}
            role="log"
          >
            {chat.messages.map((message) => (
              <div className={styles.message} data-role={message.role} key={message.id}>
                <span className={styles.author}>
                  {message.role === "user" ? copy.you : copy.assistant}
                </span>
                <p className={styles.bubble}>{message.text}</p>
              </div>
            ))}
          </div>

          {chat.isPending ? (
            <div className={styles.loading} role="status">
              <span aria-hidden="true" className={styles.dots}>
                <i />
                <i />
                <i />
              </span>
              {copy.loading}
            </div>
          ) : null}

          {chat.error ? (
            <p className={styles.error} role="alert">
              {copy.errors[chat.error]}
            </p>
          ) : null}
        </div>

        <form
          className={styles.composer}
          onSubmit={(event) => {
            event.preventDefault();
            void chat.sendMessage();
          }}
        >
          <label className={styles.inputLabel} htmlFor={`${id}-input`}>
            {copy.input}
          </label>
          <div className={styles.inputRow}>
            <textarea
              aria-describedby={`${id}-hint ${id}-count`}
              className={styles.input}
              id={`${id}-input`}
              name="message"
              onChange={(event) =>
                chat.setDraft(
                  Array.from(event.target.value).slice(0, ASK_MESSAGE_MAX_LENGTH).join(""),
                )
              }
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder={copy.placeholder}
              readOnly={chat.isPending}
              ref={inputRef}
              rows={2}
              value={chat.draft}
            />
            <button
              aria-label={copy.send}
              className={styles.send}
              disabled={chat.isPending || !chat.draft.trim()}
              type="submit"
            >
              <DashboardIcon className={styles.sendIcon} name="chevron" />
            </button>
          </div>
          <div className={styles.hints}>
            <span id={`${id}-hint`}>{copy.limit}</span>
            <span
              aria-label={`${length} / ${ASK_MESSAGE_MAX_LENGTH} ${copy.characters}`}
              id={`${id}-count`}
            >
              {length} / {ASK_MESSAGE_MAX_LENGTH}
            </span>
          </div>
        </form>
      </section>
    </div>
  );
}
