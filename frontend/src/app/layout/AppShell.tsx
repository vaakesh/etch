import { Suspense, useState, type CSSProperties } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  DashboardIcon,
  DeckIllustration,
  type DashboardIconName,
} from "../../components/DashboardVisuals";
import { PageLoader } from "../PageLoader";
import styles from "./AppShell.module.css";

interface NavigationItem {
  label: string;
  icon: DashboardIconName;
  to?: string;
  end?: boolean;
}

interface NavigationStyle extends CSSProperties {
  "--active-index": number;
}

const NAVIGATION_ITEMS: readonly NavigationItem[] = [
  { label: "Главная", icon: "home", to: "/", end: true },
  { label: "Библиотека", icon: "book", to: "/library" },
  { label: "Каталог", icon: "decks" },
  { label: "Практика", icon: "practice" },
  { label: "Статистика", icon: "chart" },
  { label: "Настройки", icon: "settings" },
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
  const { pathname } = useLocation();
  const activeIndex = NAVIGATION_ITEMS.findIndex((item) => isNavigationItemActive(pathname, item));
  const navigationStyle: NavigationStyle = {
    "--active-index": Math.max(activeIndex, 0),
  };

  return (
    <aside className={styles.sidebar} id="app-sidebar">
      <div className={styles.brand}>
        <span className={styles.brandName}>Etch</span>
      </div>

      <nav
        aria-label="Основная навигация"
        className={styles.navigation}
        data-active={activeIndex >= 0}
        data-active-index={activeIndex >= 0 ? activeIndex : undefined}
        style={navigationStyle}
      >
        <span aria-hidden="true" className={styles.navigationThumb} />
        <ul className={styles.navigationList}>
          {NAVIGATION_ITEMS.map((item) => (
            <li key={item.label}>
              {item.to ? (
                <NavLink
                  aria-label={item.label}
                  className={({ isActive }) =>
                    isActive
                      ? `${styles.navigationItem} ${styles.navigationItemActive}`
                      : styles.navigationItem
                  }
                  end={item.end}
                  title={collapsed ? item.label : undefined}
                  to={item.to}
                >
                  <DashboardIcon className={styles.navigationIcon} name={item.icon} />
                  <span className={styles.navigationLabel}>{item.label}</span>
                </NavLink>
              ) : (
                <span
                  aria-label={item.label}
                  aria-disabled="true"
                  className={styles.navigationItem}
                  title={collapsed ? item.label : "Раздел пока не подключён"}
                >
                  <DashboardIcon className={styles.navigationIcon} name={item.icon} />
                  <span className={styles.navigationLabel}>{item.label}</span>
                </span>
              )}
            </li>
          ))}
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
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const shellClassName = isSidebarCollapsed
    ? `${styles.shell} ${styles.shellCollapsed}`
    : styles.shell;

  return (
    <div className={shellClassName}>
      <button
        aria-controls="app-sidebar"
        aria-expanded={!isSidebarCollapsed}
        aria-label={isSidebarCollapsed ? "Развернуть боковое меню" : "Свернуть боковое меню"}
        className={styles.sidebarToggle}
        onClick={() => setIsSidebarCollapsed((collapsed) => !collapsed)}
        title={isSidebarCollapsed ? "Развернуть боковое меню" : "Свернуть боковое меню"}
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
