import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NotFound from '../NotFound';

test('renders navigation options for unknown route', () => {
  render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <NotFound />
    </MemoryRouter>
  );

  expect(screen.getByRole('heading', { name: /страница не найдена/i })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /вернуться в портфель/i })).toHaveAttribute('href', '/portfolio');
});
