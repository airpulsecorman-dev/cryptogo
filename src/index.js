import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { TonConnectUIProvider } from '@tonconnect/ui-react';

const appBaseUrl = new URL(
  process.env.PUBLIC_URL || "/",
  window.location.origin,
);
if (!appBaseUrl.pathname.endsWith("/")) appBaseUrl.pathname += "/";
const manifestUrl = new URL("tonconnect-manifest.json", appBaseUrl).toString();

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <TonConnectUIProvider manifestUrl={manifestUrl}>
      <App />
    </TonConnectUIProvider>
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
