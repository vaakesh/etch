import {
  Suspense,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type PointerEvent,
  type SyntheticEvent,
} from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/hooks/useAuth";
import { DashboardIcon, type DashboardIconName } from "../../components/DashboardVisuals";
import { defineMessages, useLocalizedMessages } from "../../i18n";
import { PageLoader } from "../PageLoader";
import styles from "./AppShell.module.css";

interface NavigationItem {
  key: keyof (typeof MESSAGES)["ru-RU"]["navigation"];
  icon: DashboardIconName;
  to?: string;
  end?: boolean;
}

const MESSAGES = defineMessages(
  {
    navigation: {
      home: "Главная",
      library: "Библиотека",
      catalog: "Каталог",
      practice: "Практика",
      statistics: "Статистика",
      settings: "Настройки",
    },
    homeAria: "На главную",
    navigationAria: "Основная навигация",
    unavailable: "Раздел пока не подключён",
    expand: "Развернуть боковое меню",
    collapse: "Свернуть боковое меню",
    profile: "Мой профиль",
    openProfile: (username: string) => `Открыть мой профиль @${username}`,
    logout: "Выйти",
    logoutEyebrow: "Аккаунт",
    logoutTitle: "Выйти из Etch?",
    logoutDescription:
      "Сессия на этом устройстве завершится. Ваши колоды и прогресс останутся на месте.",
    logoutCancel: "Остаться",
    logoutConfirm: "Выйти",
    logoutPending: "Выходим…",
  },
  {
    navigation: {
      home: "Home",
      library: "Library",
      catalog: "Catalog",
      practice: "Practice",
      statistics: "Statistics",
      settings: "Settings",
    },
    homeAria: "Go to home",
    navigationAria: "Main navigation",
    unavailable: "This section is not available yet",
    expand: "Expand sidebar",
    collapse: "Collapse sidebar",
    profile: "My profile",
    openProfile: (username: string) => `Open my profile @${username}`,
    logout: "Sign out",
    logoutEyebrow: "Account",
    logoutTitle: "Sign out of Etch?",
    logoutDescription:
      "Your session on this device will end. Your decks and progress will stay right where they are.",
    logoutCancel: "Stay signed in",
    logoutConfirm: "Sign out",
    logoutPending: "Signing out…",
  },
);

interface NavigationStyle extends CSSProperties {
  "--active-index": number;
}

const NAVIGATION_ITEMS: readonly NavigationItem[] = [
  { key: "home", icon: "home", to: "/", end: true },
  { key: "library", icon: "book", to: "/library" },
  { key: "catalog", icon: "decks", to: "/catalog" },
  { key: "practice", icon: "practice", to: "/practice" },
  { key: "statistics", icon: "chart" },
  { key: "settings", icon: "settings", to: "/settings" },
];

function isNavigationItemActive(pathname: string, item: NavigationItem): boolean {
  if (!item.to) {
    return false;
  }

  if (item.to === "/library" && pathname.startsWith("/decks/")) {
    return true;
  }

  return item.end
    ? pathname === item.to
    : pathname === item.to || pathname.startsWith(`${item.to}/`);
}

interface SidebarProfile {
  path: string;
  username: string;
}

interface SidebarProps {
  collapsed: boolean;
  onRequestLogout: () => void;
  profile: SidebarProfile | null;
}

function Sidebar({ collapsed, onRequestLogout, profile }: SidebarProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const { pathname } = useLocation();
  const activeIndex = NAVIGATION_ITEMS.findIndex((item) => isNavigationItemActive(pathname, item));
  const navigationStyle: NavigationStyle = {
    "--active-index": Math.max(activeIndex, 0),
  };

  return (
    <aside className={styles.sidebar} id="app-sidebar">
      <Link aria-label={messages.homeAria} className={styles.brand} to="/">
        <span className={styles.brandName}>Etch</span>
      </Link>

      {profile === null ? null : (
        <Link
          aria-current={pathname === profile.path ? "page" : undefined}
          aria-label={messages.openProfile(profile.username)}
          className={
            pathname === profile.path
              ? `${styles.profileCard} ${styles.profileCardActive}`
              : styles.profileCard
          }
          title={messages.openProfile(profile.username)}
          to={profile.path}
        >
          <span aria-hidden="true" className={styles.profileAvatar}>
            {Array.from(profile.username)[0]?.toLocaleUpperCase() ?? "U"}
          </span>
          <span className={styles.profileDetails}>
            <span>{messages.profile}</span>
            <strong>@{profile.username}</strong>
          </span>
          <DashboardIcon className={styles.profileChevron} name="chevron" />
        </Link>
      )}

      <nav
        aria-label={messages.navigationAria}
        className={styles.navigation}
        data-active={activeIndex >= 0}
        data-active-index={activeIndex >= 0 ? activeIndex : undefined}
        style={navigationStyle}
      >
        <span aria-hidden="true" className={styles.navigationThumb} />
        <ul className={styles.navigationList}>
          {NAVIGATION_ITEMS.map((item) => {
            const label = messages.navigation[item.key];
            const isItemActive = isNavigationItemActive(pathname, item);

            return (
              <li className={item.to ? undefined : styles.navigationUnavailable} key={item.key}>
                {item.to ? (
                  <Link
                    aria-current={isItemActive ? "page" : undefined}
                    aria-label={label}
                    className={
                      isItemActive
                        ? `${styles.navigationItem} ${styles.navigationItemActive}`
                        : styles.navigationItem
                    }
                    title={collapsed ? label : undefined}
                    to={item.to}
                  >
                    <DashboardIcon className={styles.navigationIcon} name={item.icon} />
                    <span className={styles.navigationLabel}>{label}</span>
                  </Link>
                ) : (
                  <span
                    aria-label={label}
                    aria-disabled="true"
                    className={styles.navigationItem}
                    title={collapsed ? label : messages.unavailable}
                  >
                    <DashboardIcon className={styles.navigationIcon} name={item.icon} />
                    <span className={styles.navigationLabel}>{label}</span>
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </nav>

      <div className={styles.sidebarFooter}>
        <button
          aria-haspopup="dialog"
          aria-label={messages.logout}
          className={styles.logoutButton}
          onClick={onRequestLogout}
          title={messages.logout}
          type="button"
        >
          <DashboardIcon className={styles.logoutIcon} name="logout" />
          <span className={styles.logoutLabel}>{messages.logout}</span>
        </button>
      </div>
    </aside>
  );
}

interface LogoutDialogProps {
  isPending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

function LogoutDialog({ isPending, onClose, onConfirm }: LogoutDialogProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;

    if (dialog !== null && !dialog.open) {
      dialog.showModal();
    }
  }, []);

  function closeDialog(): void {
    if (!isPending) {
      dialogRef.current?.close();
    }
  }

  function handleBackdropPointerDown(event: PointerEvent<HTMLDialogElement>): void {
    if (event.target === event.currentTarget) {
      closeDialog();
    }
  }

  function handleCancel(event: SyntheticEvent<HTMLDialogElement>): void {
    if (isPending) {
      event.preventDefault();
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onConfirm();
  }

  return (
    <dialog
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      aria-modal="true"
      className={styles.logoutDialog}
      onCancel={handleCancel}
      onClose={onClose}
      onPointerDown={handleBackdropPointerDown}
      ref={dialogRef}
    >
      <form className={styles.logoutDialogShell} onSubmit={handleSubmit}>
        <div className={styles.logoutDialogBody}>
          <span aria-hidden="true" className={styles.logoutDialogMark}>
            <DashboardIcon name="logout" />
          </span>
          <span className={styles.logoutDialogEyebrow}>{messages.logoutEyebrow}</span>
          <h2 id={titleId}>{messages.logoutTitle}</h2>
          <p id={descriptionId}>{messages.logoutDescription}</p>
        </div>

        <div className={styles.logoutDialogActions}>
          <button
            autoFocus
            className={styles.logoutDialogCancel}
            disabled={isPending}
            onClick={closeDialog}
            type="button"
          >
            {messages.logoutCancel}
          </button>
          <button className={styles.logoutDialogConfirm} disabled={isPending} type="submit">
            {isPending ? messages.logoutPending : messages.logoutConfirm}
          </button>
        </div>
      </form>
    </dialog>
  );
}

export function AppShell() {
  const messages = useLocalizedMessages(MESSAGES);
  const { logout, user } = useAuth();
  const { pathname } = useLocation();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isLogoutDialogOpen, setIsLogoutDialogOpen] = useState(false);
  const [isLogoutPending, setIsLogoutPending] = useState(false);
  const profile =
    user === null
      ? null
      : {
          path: `/users/${encodeURIComponent(user.username)}`,
          username: user.username,
        };
  const isLibraryRoute =
    pathname === "/catalog" ||
    pathname === "/library" ||
    pathname.startsWith("/library/") ||
    pathname.startsWith("/decks/");
  const shellClassName = [
    styles.shell,
    isSidebarCollapsed ? styles.shellCollapsed : null,
    isLibraryRoute ? styles.shellLibrary : null,
  ]
    .filter((className) => className !== null)
    .join(" ");

  function handleLogout(): void {
    setIsLogoutPending(true);
    void logout().catch(() => {
      setIsLogoutPending(false);
    });
  }

  return (
    <div className={shellClassName}>
      <button
        aria-controls="app-sidebar"
        aria-expanded={!isSidebarCollapsed}
        aria-label={isSidebarCollapsed ? messages.expand : messages.collapse}
        className={styles.sidebarToggle}
        onClick={() => setIsSidebarCollapsed((collapsed) => !collapsed)}
        title={isSidebarCollapsed ? messages.expand : messages.collapse}
        type="button"
      >
        <DashboardIcon className={styles.sidebarToggleIcon} name="chevron" />
      </button>

      <Sidebar
        collapsed={isSidebarCollapsed}
        onRequestLogout={() => setIsLogoutDialogOpen(true)}
        profile={profile}
      />

      <div className={styles.content}>
        <Suspense fallback={<PageLoader contained tone="light" />}>
          <Outlet />
        </Suspense>
      </div>

      {isLogoutDialogOpen ? (
        <LogoutDialog
          isPending={isLogoutPending}
          onClose={() => setIsLogoutDialogOpen(false)}
          onConfirm={handleLogout}
        />
      ) : null}
    </div>
  );
}
