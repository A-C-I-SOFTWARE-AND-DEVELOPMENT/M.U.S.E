import { ShareI18nProvider } from "../vendor/opencode/share/common"
import { MESSAGES } from "./messages"
import Shell from "./Shell"

export default function App() {
  return (
    <ShareI18nProvider messages={MESSAGES}>
      <Shell />
    </ShareI18nProvider>
  )
}
