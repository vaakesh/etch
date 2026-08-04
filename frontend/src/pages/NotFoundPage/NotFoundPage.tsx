import { Link } from "react-router-dom";
import styles from "./NotFoundPage.module.css";

export function NotFoundPage() {
  return (
    <main className={styles.page}>
      <div aria-hidden="true" className={styles.ambient}>
        <span className={styles.ambientOrb} />
        <span className={styles.ambientLetter}>Aa</span>
        <span className={styles.ambientRule} />
      </div>

      <section aria-labelledby="not-found-title" className={styles.content}>
        <div aria-hidden="true" className={styles.visual}>
          <span className={styles.cardBack} />
          <span className={styles.cardMiddle} />
          <span className={styles.cardFront}>
            <i>4</i>
            <b>0</b>
            <i>4</i>
          </span>
        </div>

        <div className={styles.copy}>
          <span className={styles.eyebrow}>Etch · ошибка 404</span>
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
            <span aria-hidden="true">→</span>
          </Link>
        </div>
      </section>
    </main>
  );
}

export default NotFoundPage;
