import { useEffect } from "react";
import ChannelShell from "./features/channel-shell/ChannelShell";
import { applyUiSettings, loadUiSettings } from "./features/settings/uiPreferences";

function App() {
  useEffect(() => {
    applyUiSettings(loadUiSettings());
  }, []);

  return <ChannelShell />;
}

export default App;
