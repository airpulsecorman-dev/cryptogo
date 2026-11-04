import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import WalletLogin from "./WalletLogin";
import { api } from "./api";

let mockStatusChangeHandler;
const mockTonConnectUI = {
  connected: false,
  disconnect: jest.fn(),
  setConnectRequestParameters: jest.fn(),
  openModal: jest.fn(),
  onStatusChange: jest.fn((handler) => {
    mockStatusChangeHandler = handler;
    return jest.fn();
  }),
  onModalStateChange: jest.fn(() => jest.fn()),
};

jest.mock("@tonconnect/ui-react", () => ({
  useTonConnectUI: () => [mockTonConnectUI],
}));

jest.mock("./api", () => ({
  api: {
    createEvmChallenge: jest.fn(),
    authenticateEvm: jest.fn(),
    createTonChallenge: jest.fn(),
    authenticateTon: jest.fn(),
  },
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockStatusChangeHandler = null;
  mockTonConnectUI.onStatusChange.mockImplementation((handler) => {
    mockStatusChangeHandler = handler;
    return jest.fn();
  });
  mockTonConnectUI.onModalStateChange.mockImplementation(() => jest.fn());
  mockTonConnectUI.connected = false;
  api.createEvmChallenge.mockResolvedValue({
    nonce: "f".repeat(64),
    message: "Crypto Go sign-in message",
  });
  api.authenticateEvm.mockResolvedValue({ id: "evm-player" });
  api.createTonChallenge.mockResolvedValue({ payload: "single-use-ton-payload" });
  api.authenticateTon.mockResolvedValue({ id: "ton-player" });
});

test("authenticates EVM wallets with a signed challenge and no transaction", async () => {
  const walletAddress = "0x1234567890123456789012345678901234567890";
  const providerRequest = jest.fn(({ method }) => {
    if (method === "eth_requestAccounts") return [walletAddress];
    if (method === "eth_chainId") return "0x1";
    if (method === "personal_sign") return "0xsignature";
    throw new Error(`Unexpected wallet method: ${method}`);
  });
  Object.defineProperty(window, "ethereum", {
    configurable: true,
    value: { request: providerRequest },
  });
  const onAuthenticated = jest.fn();
  const onError = jest.fn();

  render(
    <WalletLogin onAuthenticated={onAuthenticated} onError={onError} />,
  );
  fireEvent.click(screen.getByRole("button", { name: /billetera evm/i }));

  await waitFor(() =>
    expect(onAuthenticated).toHaveBeenCalledWith({ id: "evm-player" }),
  );
  expect(api.createEvmChallenge).toHaveBeenCalledWith(walletAddress, 1);
  expect(api.authenticateEvm).toHaveBeenCalledWith(
    walletAddress,
    1,
    expect.objectContaining({ nonce: "f".repeat(64) }),
    "0xsignature",
  );
  expect(providerRequest.mock.calls.map(([request]) => request.method)).toEqual([
    "eth_requestAccounts",
    "eth_chainId",
    "personal_sign",
  ]);
  expect(onError).toHaveBeenCalledWith("");
});

test("requests a TON proof challenge before opening the wallet picker", async () => {
  const onAuthenticated = jest.fn();
  const onError = jest.fn();
  render(
    <WalletLogin onAuthenticated={onAuthenticated} onError={onError} />,
  );
  fireEvent.click(
    screen.getByRole("button", { name: /conectar telegram wallet/i }),
  );

  await waitFor(() => expect(mockTonConnectUI.openModal).toHaveBeenCalled());
  expect(mockTonConnectUI.setConnectRequestParameters).toHaveBeenCalledWith({
    state: "ready",
    value: { tonProof: "single-use-ton-payload" },
  });

  const wallet = {
    account: {
      address: "0:wallet-address",
      chain: "-239",
      publicKey: "a".repeat(64),
      walletStateInit: "wallet-state-init",
    },
    connectItems: {
      tonProof: {
        proof: {
          timestamp: 1,
          domain: { lengthBytes: 14, value: "localhost:3000" },
          payload: "single-use-ton-payload",
          signature: "wallet-proof",
        },
      },
    },
  };
  await act(async () => mockStatusChangeHandler(wallet));

  await waitFor(() =>
    expect(api.authenticateTon).toHaveBeenCalledWith(
      wallet.account,
      wallet.connectItems.tonProof.proof,
    ),
  );
  expect(onAuthenticated).toHaveBeenCalledWith({ id: "ton-player" });
  expect(onError).toHaveBeenCalledWith("");
});

test("reports when no EVM wallet is installed", async () => {
  delete window.ethereum;
  const onError = jest.fn();
  render(
    <WalletLogin onAuthenticated={jest.fn()} onError={onError} />,
  );
  fireEvent.click(screen.getByRole("button", { name: /billetera evm/i }));

  await waitFor(() =>
    expect(onError).toHaveBeenCalledWith(
      expect.stringMatching(/no encontramos una billetera evm/i),
    ),
  );
});
