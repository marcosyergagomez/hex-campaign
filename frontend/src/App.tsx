import { Navigate, Route, Routes } from "react-router-dom"

import { Gate } from "./Gate"
import { LoginPage } from "./pages/LoginPage"
import { RegisterPage } from "./pages/RegisterPage"

export function App() {
  return (
    <Routes>
      <Route element={<Gate />}>
        <Route index element={<Navigate to="/entrar" replace />} />
        <Route path="/entrar" element={<LoginPage />} />
        <Route path="/alta" element={<RegisterPage />} />
      </Route>
    </Routes>
  )
}
