import { fireEvent, render, screen, within } from '@testing-library/react';
import App from './App';

test('renders the Crypto Hunt map demonstration', () => {
  render(<App />);

  expect(screen.getByRole('heading', { name: /sal a explorar/i })).toBeInTheDocument();
  expect(screen.getByText(/ubicaciones ficticias/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /recoger btc/i })).toBeInTheDocument();
});

test('collecting a discovery updates points and advances to the next one', () => {
  render(<App />);

  fireEvent.click(screen.getByRole('button', { name: /recoger btc/i }));

  expect(screen.getByRole('status')).toHaveTextContent(/BTC añadido a tu colección · \+10 puntos/i);
  expect(screen.getByRole('button', { name: /recoger eth/i })).toBeInTheDocument();
  expect(screen.getByText('1.290')).toBeInTheDocument();
});

test('navigation opens the inventory section', () => {
  render(<App />);

  fireEvent.click(screen.getAllByRole('button', { name: 'Inventario' })[0]);

  expect(screen.getByRole('heading', { name: /inventario/i })).toBeInTheDocument();
  expect(screen.getByText('× 7')).toBeInTheDocument();
});

test('map zoom controls change the zoom and stop at their limits', () => {
  render(<App />);
  const zoomIn = screen.getByRole('button', { name: 'Acercar mapa' });
  const zoomOut = screen.getByRole('button', { name: 'Alejar mapa' });

  fireEvent.click(zoomIn);
  expect(screen.getByText('Zoom 110%')).toBeInTheDocument();

  for (let index = 0; index < 4; index += 1) fireEvent.click(zoomIn);
  expect(screen.getByText('Zoom 150%')).toBeInTheDocument();
  expect(zoomIn).toBeDisabled();

  for (let index = 0; index < 7; index += 1) fireEvent.click(zoomOut);
  expect(screen.getByText('Zoom 80%')).toBeInTheDocument();
  expect(zoomOut).toBeDisabled();
});

test('the logo returns to the map from another section', () => {
  render(<App />);
  fireEvent.click(screen.getAllByRole('button', { name: 'Inventario' })[0]);
  fireEvent.click(screen.getByRole('link', { name: 'Crypto Hunt, inicio' }));

  expect(screen.getByRole('heading', { name: /sal a explorar/i })).toBeInTheDocument();
});

test('the mobile navigation opens each section', () => {
  render(<App />);
  const mobileNavigation = within(screen.getByRole('navigation', { name: 'Navegación móvil' }));

  for (const [label, heading] of [
    ['Inventario', /inventario/i],
    ['Misiones', /misiones/i],
    ['Ranking', /ranking/i],
    ['Perfil', /perfil/i],
  ]) {
    fireEvent.click(mobileNavigation.getByRole('button', { name: label }));
    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
  }
});

test('the location button requests permission and reports the result', () => {
  const getCurrentPosition = jest.fn((success) => success({ coords: { latitude: -0.2, longitude: -78.5 } }));
  Object.defineProperty(navigator, 'geolocation', {
    configurable: true,
    value: { getCurrentPosition },
  });

  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /mi ubicación/i }));

  expect(getCurrentPosition).toHaveBeenCalledWith(
    expect.any(Function),
    expect.any(Function),
    expect.objectContaining({ enableHighAccuracy: false })
  );
  expect(screen.getByRole('status')).toHaveTextContent(/ubicación detectada.*datos de demostración/i);
});

test('selecting a map marker changes the selected treasure', () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /seleccionar ethereum/i }));

  expect(screen.getByRole('button', { name: /recoger eth/i })).toBeInTheDocument();
});

test('the profile avatar and desktop navigation open their sections', () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Abrir perfil' }));
  expect(screen.getByRole('heading', { name: /perfil/i })).toBeInTheDocument();

  fireEvent.click(screen.getAllByRole('button', { name: 'Ranking' })[0]);
  expect(screen.getByRole('heading', { name: /ranking/i })).toBeInTheDocument();
});

test('collecting every available treasure displays the empty state', () => {
  render(<App />);

  for (const ticker of ['BTC', 'ETH', 'SOL']) {
    fireEvent.click(screen.getByRole('button', { name: new RegExp(`recoger ${ticker}`, 'i') }));
  }

  expect(screen.getByText(/los encontraste todos/i)).toBeInTheDocument();
  expect(screen.getByText(/no quedan tesoros en esta zona/i)).toBeInTheDocument();
  expect(screen.getByText('1.415')).toBeInTheDocument();
});

test('the location button reports when permission is denied', () => {
  const getCurrentPosition = jest.fn((success, error) => error({ code: 1 }));
  Object.defineProperty(navigator, 'geolocation', {
    configurable: true,
    value: { getCurrentPosition },
  });

  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /mi ubicación/i }));

  expect(screen.getByRole('status')).toHaveTextContent(/permiso de ubicación denegado/i);
});
