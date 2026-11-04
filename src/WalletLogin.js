import { useEffect, useRef, useState } from "react";
import { useTonConnectUI } from "@tonconnect/ui-react";
import { api } from "./api";

function errorMessage(error) {
  if (error?.code === 4001) return "Cancelaste la firma en tu billetera.";
  return error?.message || "No se pudo completar el inicio de sesión.";
}

export default function WalletLogin({ onAuthenticated, onError }) {
  const [tonConnectUI] = useTonConnectUI();
  const [evmPending, setEvmPending] = useState(false);
  const [tonPending, setTonPending] = useState(false);
  const tonChallenge = useRef(null);

  useEffect(() => {
    const unsubscribeWallet = tonConnectUI.onStatusChange(async (wallet) => {
      const payload = tonChallenge.current;
      if (!wallet || !payload) return;

      tonChallenge.current = null;
      setTonPending(false);
      const tonProof = wallet.connectItems?.tonProof;
      if (!tonProof || !("proof" in tonProof)) {
        onError(
          "Esta billetera no permite verificar ton_proof. Prueba otra billetera TON.",
        );
        return;
      }

      try {
        onAuthenticated(await api.authenticateTon(wallet.account, tonProof.proof));
      } catch (error) {
        onError(errorMessage(error));
      }
    }, (error) => onError(errorMessage(error)));
    const unsubscribeModal = tonConnectUI.onModalStateChange((state) => {
      if (state.status === "closed" && tonChallenge.current) {
        tonChallenge.current = null;
        setTonPending(false);
      }
    });

    return () => {
      unsubscribeWallet();
      unsubscribeModal();
    };
  }, [onAuthenticated, onError, tonConnectUI]);

  async function signInWithEvm() {
    setEvmPending(true);
    onError("");
    try {
      const provider = window.ethereum;
      if (!provider?.request) {
        throw new Error(
          "No encontramos una billetera EVM en este navegador. Abre Crypto Go desde MetaMask, Coinbase Wallet u otra billetera compatible.",
        );
      }
      const accounts = await provider.request({ method: "eth_requestAccounts" });
      const address = accounts?.[0];
      if (!address) throw new Error("La billetera no devolvió una dirección.");
      const chainIdHex = await provider.request({ method: "eth_chainId" });
      const chainId = Number.parseInt(chainIdHex, 16);
      if (!Number.isSafeInteger(chainId) || chainId < 1) {
        throw new Error("La red EVM seleccionada no es válida.");
      }
      const challenge = await api.createEvmChallenge(address, chainId);
      const signature = await provider.request({
        method: "personal_sign",
        params: [challenge.message, address],
      });
      onAuthenticated(
        await api.authenticateEvm(address, chainId, challenge, signature),
      );
    } catch (error) {
      onError(errorMessage(error));
    } finally {
      setEvmPending(false);
    }
  }

  async function connectTonWallet() {
    setTonPending(true);
    onError("");
    try {
      if (tonConnectUI.connected) await tonConnectUI.disconnect();
      const challenge = await api.createTonChallenge();
      tonChallenge.current = challenge.payload;
      tonConnectUI.setConnectRequestParameters({
        state: "ready",
        value: { tonProof: challenge.payload },
      });
      await tonConnectUI.openModal();
    } catch (error) {
      tonChallenge.current = null;
      setTonPending(false);
      onError(errorMessage(error));
    }
  }

  return (
    <div className="wallet-login">
      <button
        className="wallet-login-button"
        disabled={evmPending || tonPending}
        onClick={signInWithEvm}
      >
        {evmPending ? "Esperando firma EVM…" : "Conectar billetera EVM"}
      </button>
      <button
        className="wallet-login-button ton-wallet-button"
        disabled={evmPending || tonPending}
        onClick={connectTonWallet}
      >
        {tonPending ? "Esperando Telegram Wallet…" : "Conectar Telegram Wallet"}
      </button>
      <p className="wallet-login-note">
        Solo se solicita una firma de acceso. No se envían transacciones ni se
        cobra gas.
      </p>
    </div>
  );
}
