import { Suspense, useState, type CSSProperties } from "react";
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
    openProfile: (username: string) => `Открыть мой профиль @${username}`,
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
    openProfile: (username: string) => `Open my profile @${username}`,
  },
);

interface NavigationStyle extends CSSProperties {
  "--active-index": number;
  "--compact-active-index": number;
}

const NAVIGATION_ITEMS: readonly NavigationItem[] = [
  { key: "home", icon: "home", to: "/", end: true },
  { key: "library", icon: "book", to: "/library/decks" },
  { key: "catalog", icon: "decks", to: "/catalog" },
  { key: "practice", icon: "practice", to: "/practice" },
  { key: "statistics", icon: "chart" },
  { key: "settings", icon: "settings", to: "/settings" },
];

function isNavigationItemActive(pathname: string, item: NavigationItem): boolean {
  if (!item.to) {
    return false;
  }

  if (item.key === "library" && (pathname === "/library" || pathname.startsWith("/decks/"))) {
    return true;
  }

  if (item.key === "library" && pathname.startsWith("/library/")) {
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
  profile: SidebarProfile | null;
}

function Sidebar({ collapsed, profile }: SidebarProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const { pathname } = useLocation();
  const activeIndex = NAVIGATION_ITEMS.findIndex((item) => isNavigationItemActive(pathname, item));
  const compactActiveIndex = NAVIGATION_ITEMS.filter((item) => item.to).findIndex((item) =>
    isNavigationItemActive(pathname, item),
  );
  const navigationStyle: NavigationStyle = {
    "--active-index": Math.max(activeIndex, 0),
    "--compact-active-index": Math.max(compactActiveIndex, 0),
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
          <span className={styles.profileDetails}>@{profile.username}</span>
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
    </aside>
  );
}

export function AppShell() {
  const messages = useLocalizedMessages(MESSAGES);
  const { user } = useAuth();
  const { pathname } = useLocation();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
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

      <Sidebar collapsed={isSidebarCollapsed} profile={profile} />

      <div className={styles.content}>
        <Suspense fallback={<PageLoader contained tone="light" />}>
          <Outlet />
        </Suspense>
      </div>
    </div>
  );
}
