import { Navigate, Route, Routes } from "react-router-dom"

import { AppShell } from "./AppShell"
import { Gate } from "./Gate"
import { CampaignDetailPage } from "./pages/CampaignDetailPage"
import { CampaignListPage } from "./pages/CampaignListPage"
import { CreateCampaignPage } from "./pages/CreateCampaignPage"
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
      <Route element={<AppShell />}>
        <Route path="/campanas" element={<CampaignListPage />} />
        <Route path="/campanas/nueva" element={<CreateCampaignPage />} />
        <Route path="/campanas/:id" element={<CampaignDetailPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/entrar" replace />} />
    </Routes>
  )
}
