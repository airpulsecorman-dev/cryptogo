import { fireEvent, render, screen } from '@testing-library/react';
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
