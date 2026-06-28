import { fireEvent, render, screen } from '@testing-library/react';
import ConfirmDialog from '../ConfirmDialog';

test('renders accessible confirm dialog and handles actions', () => {
  const onConfirm = jest.fn();
  const onCancel = jest.fn();

  render(
    <ConfirmDialog
      open
      title="Удалить запись?"
      description="Действие нельзя отменить."
      confirmLabel="Удалить"
      onConfirm={onConfirm}
      onCancel={onCancel}
      danger
    />
  );

  expect(screen.getByRole('dialog', { name: /удалить запись/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /удалить/i }));
  expect(onConfirm).toHaveBeenCalledTimes(1);

  fireEvent.keyDown(document, { key: 'Escape' });
  expect(onCancel).toHaveBeenCalledTimes(1);
});
