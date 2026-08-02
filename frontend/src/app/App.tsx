import { AuthProvider } from "../auth/model/AuthProvider";
import { LocaleProvider } from "../i18n";
import { InitialBootComplete } from "./InitialBootComplete";
import { AppRouter } from "./router/AppRouter";

export function App() {
  return (
    <LocaleProvider>
      <AuthProvider>
        <InitialBootComplete />
        <AppRouter />
      </AuthProvider>
    </LocaleProvider>
  );
}

export default App;
