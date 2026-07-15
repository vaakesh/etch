import { AuthProvider } from "../auth/model/AuthProvider";
import { InitialBootComplete } from "./InitialBootComplete";
import { AppRouter } from "./router/AppRouter";

export function App() {
  return (
    <AuthProvider>
      <InitialBootComplete />
      <AppRouter />
    </AuthProvider>
  );
}

export default App;
