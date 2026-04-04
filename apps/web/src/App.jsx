import { useLayoutEffect } from "react";
import ChannelShell from "./features/channel-shell/ChannelShell";
import { applyUiSettings, loadUiSettings } from "./features/settings/uiPreferences";

function App() {
  useLayoutEffect(() => {
    applyUiSettings(loadUiSettings());
  }, []);

  return <ChannelShell />;
}

export default App;
