import { AuthProvider } from "../auth/model/AuthProvider";
import { AppRouter } from "./router/AppRouter";

export function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}

export default App;
