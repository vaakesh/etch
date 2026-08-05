import { Suspense, useState, type CSSProperties } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  DashboardIcon,
  DeckIllustration,
  type DashboardIconName,
} from "../../components/DashboardVisuals";
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
  },
);

interface NavigationStyle extends CSSProperties {
  "--active-index": number;
}

const NAVIGATION_ITEMS: readonly NavigationItem[] = [
  { key: "home", icon: "home", to: "/", end: true },
  { key: "library", icon: "book", to: "/library" },
  { key: "catalog", icon: "decks" },
  { key: "practice", icon: "practice", to: "/practice" },
  { key: "statistics", icon: "chart" },
  { key: "settings", icon: "settings", to: "/settings" },
];

function isNavigationItemActive(pathname: string, item: NavigationItem): boolean {
  if (!item.to) {
    return false;
  }

  return item.end
    ? pathname === item.to
    : pathname === item.to || pathname.startsWith(`${item.to}/`);
}

function Sidebar({ collapsed }: { collapsed: boolean }) {
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

            return (
              <li key={item.key}>
                {item.to ? (
                  <NavLink
                    aria-label={label}
                    className={({ isActive }) =>
                      isActive
                        ? `${styles.navigationItem} ${styles.navigationItemActive}`
                        : styles.navigationItem
                    }
                    end={item.end}
                    title={collapsed ? label : undefined}
                    to={item.to}
                  >
                    <DashboardIcon className={styles.navigationIcon} name={item.icon} />
                    <span className={styles.navigationLabel}>{label}</span>
                  </NavLink>
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

      <div aria-hidden="true" className={styles.sidebarArtwork}>
        <DeckIllustration className={styles.sidebarIllustration} variant={5} />
        <span className={styles.artBook} />
        <span className={styles.artBookSecondary} />
      </div>
    </aside>
  );
}

export function AppShell() {
  const messages = useLocalizedMessages(MESSAGES);
  const { pathname } = useLocation();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const isLibraryRoute = pathname === "/library" || pathname.startsWith("/library/");
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

      <Sidebar collapsed={isSidebarCollapsed} />

      <div className={styles.content}>
        <Suspense fallback={<PageLoader contained tone="light" />}>
          <Outlet />
        </Suspense>
      </div>
    </div>
  );
}
