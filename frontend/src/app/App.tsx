import { AuthProvider } from "../auth/model/AuthProvider";
import { LocaleProvider } from "../i18n";
import { ThemeProvider } from "../theme";
import { InitialBootComplete } from "./InitialBootComplete";
import { KeyboardNavigation } from "./KeyboardNavigation";
import { AppRouter } from "./router/AppRouter";
import { UserPreferencesSync } from "./UserPreferencesSync";

export function App() {
  return (
    <ThemeProvider>
      <KeyboardNavigation />
      <LocaleProvider>
        <AuthProvider>
          <UserPreferencesSync />
          <InitialBootComplete />
          <AppRouter />
        </AuthProvider>
      </LocaleProvider>
    </ThemeProvider>
  );
}

export default App;
