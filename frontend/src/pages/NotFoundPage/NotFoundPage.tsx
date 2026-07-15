import { Link } from "react-router-dom";
import styles from "./NotFoundPage.module.css";

export function NotFoundPage() {
  return (
    <main className={styles.page}>
      <section aria-labelledby="not-found-title" className={styles.content}>
        <p aria-hidden="true" className={styles.code}>
          404
        </p>
        <h1 className={styles.heading} id="not-found-title">
          Страница не найдена
        </h1>
        <p className={styles.description}>
          Возможно, адрес указан с ошибкой или страница была перемещена.
        </p>
        <Link className={styles.homeLink} to="/">
          На главную
        </Link>
      </section>
    </main>
  );
}

export default NotFoundPage;
