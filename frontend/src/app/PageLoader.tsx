export function PageLoader() {
  return (
    <div aria-label="Загрузка страницы" className="page-loader" role="status">
      <span aria-hidden="true" className="page-loader__spinner" />
    </div>
  );
}
